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
