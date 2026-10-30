"""
tests/test_review.py — the Nemotron Ultra second opinion, using a fake
OpenAI-compatible client (no network).
"""
import json
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient

import review
from main import app
from protocol_search import get_protocol
from staff_finder import mark_busy, roster


class FakeClient:
    def __init__(self, content=None, error=None):
        self.content, self.error, self.calls = content, error, []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return NS(choices=[NS(message=NS(content=self.content))])


def _situation():
    mark_busy(["S003", "S004"], "ev1")
    mark_busy(["S001", "S002"], "ev0")
    event = {"event_id": "ev1", "crisis_type": "cardiac_arrest", "location": "ICU room 7", "urgency": "critical",
             "summary": "Cardiac arrest", "transcript": "Code blue ICU 7", "follow_up": None}
    team = [s for s in roster() if s["staff_id"] in {"S003", "S004"}]
    active = [{"event_id": "ev0", "crisis_type": "trauma", "location": "Bay 4", "urgency": "critical",
               "staff_dispatched": [{}, {}]},
              {"event_id": "ev1", "crisis_type": "cardiac_arrest", "location": "ICU room 7", "urgency": "critical",
               "staff_dispatched": [{}, {}]}]
    return review.build_situation(event, get_protocol("cardiac_arrest", ""), team, ["needs 1 nurse"], roster(), active)


def test_situation_describes_whole_hospital():
    s = _situation()
    assert s["protocol"]["code"] == "CB-02"
    assert {p["name"] for p in s["team_paged"]} == {"Dr. Ravi Kumar", "Nurse Lakshmi Nair"}
    # the new emergency itself is not listed among the "other" emergencies
    assert [e["location"] for e in s["other_active_emergencies"]] == ["Bay 4"]
    free = {p["name"] for p in s["free_staff"]}
    assert "Dr. Ravi Kumar" not in free and "Dr. Arjun Mehta" not in free and "Nurse Deepa Rao" in free
    assert [p["name"] for p in s["off_shift_staff"]] == ["Dr. Farhan Ali"]
    assert "fcm_token" not in json.dumps(s)


def test_review_parses_model_output_and_uses_ultra():
    out = {"risk": "high", "assessment": "Team is one nurse short.",
           "actions": ["Call in Dr. Farhan Ali", "Page Nurse Deepa Rao", "a", "b", "c"]}
    client = FakeClient(content="```json\n" + json.dumps(out) + "\n```")
    r = review.run_review(_situation(), client=client)
    assert r["risk"] == "high" and r["assessment"] == "Team is one nurse short."
    assert len(r["actions"]) == 4
    assert client.calls[0]["model"] == review.NEBIUS_REVIEW_MODEL
    assert "Ultra" in review.NEBIUS_REVIEW_MODEL


def test_review_normalises_bad_risk():
    client = FakeClient(content=json.dumps({"risk": "extreme", "assessment": "ok", "actions": "not a list"}))
    r = review.run_review(_situation(), client=client)
    assert r["risk"] == "medium"


def test_failed_review_is_stored_not_raised():
    review.start_review("ev1")
    review.complete_review("ev1", _situation(), client=FakeClient(error=TimeoutError("slow")))
    assert review.get_review("ev1") == {"status": "failed", "error": "TimeoutError"}

    review.complete_review("ev1", _situation(), client=FakeClient(content="no json here"))
    assert review.get_review("ev1")["status"] == "failed"


def test_completed_review_is_served_by_api():
    c = TestClient(app)
    ev = c.post("/crisis", json={"transcript": "Code blue in ICU room 7"}).json()
    assert ev["review"] == "off"  # no model key in tests
    assert c.get(f"/events/{ev['event_id']}/review").json()["status"] == "off"

    review.complete_review(ev["event_id"], _situation(),
                           client=FakeClient(content=json.dumps({"risk": "low", "assessment": "Fine.", "actions": []})))
    got = c.get(f"/events/{ev['event_id']}/review").json()
    assert got["status"] == "done" and got["risk"] == "low"
    assert c.get("/events/nope/review").status_code == 404
