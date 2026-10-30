"""
tests/test_limits.py — public-demo guards: input size, rate limits, team cap,
review budget, reset lock, and error messages that do not leak internals.
"""
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient

import main
import review
from agent import CrisisContext
from limits import RateLimiter
from protocol_search import get_protocol
from staff_finder import find_available_staff


def test_rate_limiter_window_and_keys():
    lim = RateLimiter(2, 60)
    assert lim.allow("a") and lim.allow("a")
    assert not lim.allow("a")
    assert lim.allow("b")  # other callers are unaffected


def test_long_transcript_is_rejected():
    c = TestClient(main.app)
    r = c.post("/crisis", json={"transcript": "x" * (main.MAX_TRANSCRIPT_CHARS + 1)})
    assert r.status_code == 400 and "too long" in r.json()["detail"]


def test_dispatches_are_rate_limited_per_client():
    c = TestClient(main.app)
    limit = main.dispatch_limiter.limit
    for _ in range(limit):
        assert c.post("/crisis", json={"transcript": "Fire on floor 3"}).status_code == 200
    blocked = c.post("/crisis", json={"transcript": "Fire on floor 3"})
    assert blocked.status_code == 429
    # a different device behind the proxy still gets through
    other = c.post("/crisis", json={"transcript": "Fire on floor 3"}, headers={"X-Forwarded-For": "203.0.113.9"})
    assert other.status_code == 200


def test_team_is_capped_at_protocol_size_plus_margin(monkeypatch):
    def page_everyone(transcript, location_hint=None):
        staff = (find_available_staff("nurse", 10) + find_available_staff("paramedic", 10)
                 + find_available_staff("trauma_surgeon", 10))
        return CrisisContext(crisis_type="unknown", location="Lobby", staff_type="general_doctor", count=10,
                             urgency="high", summary="page everyone", protocol=get_protocol("unknown", ""),
                             staff_list=staff, engine="nemotron")

    monkeypatch.setattr(main, "run_crisis_agent", page_everyone)
    r = TestClient(main.app).post("/crisis", json={"transcript": "Page every single person now"}).json()
    cap = 1 + main.TEAM_MARGIN  # general protocol needs 1 person
    assert len(r["staff_dispatched"]) == cap
    assert any("capped" in w for w in r["warnings"])


def test_server_errors_do_not_leak_internals(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db password is hunter2")

    monkeypatch.setattr(main, "run_crisis_agent", boom)
    r = TestClient(main.app).post("/crisis", json={"transcript": "Code blue in ICU"})
    assert r.status_code == 500 and "hunter2" not in r.text


def test_reset_lock_is_opt_in(monkeypatch):
    c = TestClient(main.app)
    assert c.post("/reset").status_code == 200          # open by default for the demo button
    monkeypatch.setattr(main, "RESET_TOKEN", "s3cret")
    assert c.post("/reset").status_code == 403
    assert c.post("/reset", headers={"X-Reset-Token": "wrong"}).status_code == 403
    assert c.post("/reset", headers={"X-Reset-Token": "s3cret"}).status_code == 200


def test_review_budget_skips_review_but_not_dispatch(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    assert review.start_review("ev1", within_budget=True) == "pending"
    assert review.start_review("ev2", within_budget=False) == "skipped"
    monkeypatch.setenv("NEBIUS_API_KEY", "")
    assert review.start_review("ev3", within_budget=False) == "off"


def test_review_store_is_bounded_and_ignores_results_after_reset():
    for i in range(review.MAX_STORED + 5):
        review.start_review(f"ev{i}")
    assert review.get_review("ev0") is None and review.get_review(f"ev{review.MAX_STORED + 4}")

    review.start_review("gone")
    review.clear_reviews()                 # demo reset while Ultra was still thinking
    ok = '{"risk": "low", "assessment": "Fine.", "actions": []}'
    late = NS(chat=NS(completions=NS(create=lambda **k: NS(choices=[NS(message=NS(content=ok))]))))
    review.complete_review("gone", {}, client=late)
    assert review.get_review("gone") is None
