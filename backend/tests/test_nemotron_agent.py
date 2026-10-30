"""
tests/test_nemotron_agent.py — the Nemotron tool-calling loop, using a fake
OpenAI-compatible client (no network), plus availability and fallback behaviour.
"""
import json
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient

from agent import run_crisis_agent
from main import app


def _tool_call(i, name, args):
    return NS(id=f"call_{i}", type="function", function=NS(name=name, arguments=json.dumps(args)))


def _reply(content=None, tool_calls=None):
    return NS(choices=[NS(message=NS(content=content, tool_calls=tool_calls))])


class FakeClient:
    """Plays back a scripted conversation like Nemotron would."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.replies.pop(0)


def test_tool_calling_loop_dispatches_only_returned_staff():
    final = {
        "crisis_type": "trauma", "location": "Bay 4", "urgency": "critical",
        "primary_role": "trauma_surgeon", "count": 2,
        "summary": "Trauma, patient coding — 2 surgeons + anesthesia to Bay 4",
        "staff_ids": ["S001", "S002", "S006", "S999"],  # S999 is invented: must be dropped
        "follow_up_question": None, "reasoning": "Protocol MTP-01 needs anesthesia too.",
    }
    client = FakeClient([
        _reply(tool_calls=[_tool_call(1, "lookup_protocol", {"crisis_type": "trauma"})]),
        _reply(tool_calls=[_tool_call(2, "find_available_staff", {"role": "trauma_surgeon", "count": 2}),
                           _tool_call(3, "find_available_staff", {"role": "anesthesiologist", "count": 1})]),
        _reply(content="```json\n" + json.dumps(final) + "\n```"),
    ])
    ctx = run_crisis_agent("Need two trauma surgeons stat, Bay 4, patient coding", client=client)

    assert ctx.engine == "nemotron"
    assert ctx.protocol.code == "MTP-01"
    assert [s.staff_id for s in ctx.staff_list] == ["S001", "S002", "S006"]
    assert any(t["source"] == "tool: find_available_staff" for t in ctx.trace)
    # tool results were fed back to the model
    assert any(m["role"] == "tool" for m in client.calls[-1]["messages"])


def test_model_failure_falls_back_to_rules():
    class Broken:
        chat = NS(completions=NS(create=lambda **k: (_ for _ in ()).throw(TimeoutError("down"))))

    ctx = run_crisis_agent("Code blue in ICU, cardiac arrest", client=Broken())
    assert ctx.engine == "rules"
    assert ctx.crisis_type == "cardiac_arrest"
    assert any(t["step"] == "Fallback" for t in ctx.trace)


def test_no_double_booking_and_resolve_frees_staff():
    c = TestClient(app)
    first = c.post("/crisis", json={"transcript": "Need two trauma surgeons at Bay 4"}).json()
    ids1 = {s["staff_id"] for s in first["staff_dispatched"]}
    assert ids1 == {"S001", "S002"}

    second = c.post("/crisis", json={"transcript": "Need a trauma surgeon in Bay 7"}).json()
    assert not ids1 & {s["staff_id"] for s in second["staff_dispatched"]}
    assert second["warnings"]  # nobody free -> escalation warning

    freed = c.post(f"/events/{first['event_id']}/resolve").json()["staff_freed"]
    assert set(freed) == ids1
    third = c.post("/crisis", json={"transcript": "Need a trauma surgeon in Bay 7"}).json()
    assert third["staff_dispatched"]


def test_pager_inbox_receives_alert():
    c = TestClient(app)
    r = c.post("/crisis", json={"transcript": "Fire on floor 3, evacuate now"}).json()
    sid = r["staff_dispatched"][0]["staff_id"]
    alerts = c.get(f"/staff/{sid}/inbox").json()["alerts"]
    assert alerts and alerts[0]["event_id"] == r["event_id"]


def test_missing_location_triggers_follow_up():
    c = TestClient(app)
    r = c.post("/crisis", json={"transcript": "Patient not breathing, need help fast"}).json()
    assert r["follow_up"]


def test_fast_path_single_model_call():
    """All tools in one reply -> dispatch without a second model call."""
    client = FakeClient([
        _reply(tool_calls=[
            _tool_call(1, "report_crisis", {"crisis_type": "cardiac_arrest", "location": "ICU Room 7",
                                            "urgency": "critical", "primary_role": "cardiologist", "count": 1,
                                            "summary": "Code Blue ICU Room 7", "follow_up_question": ""}),
            _tool_call(2, "lookup_protocol", {"crisis_type": "cardiac_arrest"}),
            _tool_call(3, "find_available_staff", {"role": "cardiologist", "count": 1}),
            _tool_call(4, "find_available_staff", {"role": "nurse", "count": 2}),
        ]),
    ])
    ctx = run_crisis_agent("Code blue ICU room 7", client=client)
    assert len(client.calls) == 1
    assert ctx.engine == "nemotron" and ctx.protocol.code == "CB-02"
    assert ctx.location == "ICU Room 7" and ctx.follow_up is None
    assert [s.role for s in ctx.staff_list] == ["cardiologist", "nurse", "nurse"]
    assert client.calls[0]["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}


def test_thinking_toggle_rejected_retries_without_it():
    import agent

    class Rejecting(FakeClient):
        def _create(self, **kwargs):
            if "extra_body" in kwargs:
                err = Exception("unknown field chat_template_kwargs")
                err.status_code = 400
                raise err
            return super()._create(**kwargs)

    agent._thinking_flag_ok = True
    client = Rejecting([
        _reply(tool_calls=[
            _tool_call(1, "report_crisis", {"crisis_type": "fire", "location": "Floor 3", "urgency": "critical",
                                            "primary_role": "paramedic", "count": 2, "summary": "Fire floor 3"}),
            _tool_call(2, "find_available_staff", {"role": "paramedic", "count": 2}),
        ]),
    ])
    ctx = run_crisis_agent("Fire on floor 3", client=client)
    assert ctx.engine == "nemotron" and ctx.crisis_type == "fire"
    assert agent._thinking_flag_ok is False
    agent._thinking_flag_ok = True


def test_staff_taken_by_parallel_dispatch_is_replaced():
    """If a simultaneous dispatch claimed someone while the model was thinking, page another free person of that role."""
    from main import _claim_team
    from staff_finder import claim, find_available_staff
    team = find_available_staff("nurse", 2)            # agent picks S004, S005
    claim(["S004"], "parallel-event")                  # ...but S004 is taken meanwhile
    final = _claim_team(team, "ev")
    assert {s.staff_id for s in final} == {"S005", "S010"}
