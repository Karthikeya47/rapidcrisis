"""
review.py — a second opinion on every dispatch from NVIDIA Nemotron 3 Ultra.

Paging has to be fast, so Nemotron 3 Super dispatches the team first (agent.py).
Ultra then looks at the whole hospital in the background (every active emergency,
who is still free, who is off shift) and tells the charge nurse what to do next.
It never delays or changes the dispatch; if it is unavailable the dispatch stands.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Optional

from agent import NEBIUS_BASE_URL, _parse_json

logger = logging.getLogger(__name__)

NEBIUS_REVIEW_MODEL = os.getenv("NEBIUS_REVIEW_MODEL", "nvidia/Nemotron-3-Ultra-550b-a55b")
REVIEW_THINKING = os.getenv("NEBIUS_REVIEW_THINKING", "1") == "1"  # Ultra reasons properly; it runs off the critical path
RISKS = ("low", "medium", "high")

SYSTEM_PROMPT = """You are the senior duty manager of a hospital. Seconds ago a fast triage agent
paged a team for a new emergency. Review that dispatch against the WHOLE hospital situation:
the protocol's minimum team, other active emergencies, which staff are still free, and who is
off shift and could be called in.

Reply with ONLY this JSON (no markdown):
{"risk": "low|medium|high",
 "assessment": "one or two plain sentences on whether the response is adequate and why",
 "actions": ["up to 4 short imperative actions for the charge nurse, most urgent first"]}

Rules: name only staff that appear in the data. Do not restate protocol steps the team will
already follow; focus on gaps, capacity left for the next emergency, and what to prepare.
risk is high if the protocol team is incomplete or the hospital has no cover left for a second
emergency of this kind."""

MAX_STORED = 200   # same as the event log; older reviews are dropped

_lock = threading.Lock()
_reviews: dict[str, dict] = {}   # insertion-ordered, oldest first
_client = None


def review_enabled() -> bool:
    return bool(os.getenv("NEBIUS_API_KEY"))


def _make_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(base_url=NEBIUS_BASE_URL, api_key=os.environ["NEBIUS_API_KEY"],
                         timeout=float(os.getenv("NEBIUS_REVIEW_TIMEOUT", "90")), max_retries=0)
    return _client


def build_situation(event: dict, protocol, team: list[dict], warnings: list[str],
                    roster: list[dict], active_events: list[dict]) -> dict:
    """Everything Ultra needs, as plain data. Staff fields are limited to what a manager would see."""
    def person(s):
        return {"name": s["name"], "role": s["role"], "department": s["department"]}

    return {
        "new_emergency": {k: event.get(k) for k in
                          ("crisis_type", "location", "urgency", "summary", "transcript", "follow_up")},
        "protocol": {"code": protocol.code, "name": protocol.name, "steps": protocol.steps,
                     "minimum_team": protocol.staff_minimum} if protocol else None,
        "team_paged": [person(s) for s in team],
        "dispatch_warnings": warnings,
        "other_active_emergencies": [
            {"crisis_type": e["crisis_type"], "location": e["location"], "urgency": e.get("urgency"),
             "team_size": len(e["staff_dispatched"])}
            for e in active_events if e["event_id"] != event.get("event_id")
        ],
        "free_staff": [person(s) for s in roster if s["status"] == "available"],
        "off_shift_staff": [person(s) for s in roster if s["status"] == "off_shift"],
    }


def run_review(situation: dict, client=None) -> dict:
    """Ask Ultra for its review. Raises on transport errors or unusable output."""
    client = client or _make_client()
    t0 = time.time()
    resp = client.chat.completions.create(
        model=NEBIUS_REVIEW_MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": json.dumps(situation)}],
        temperature=0.2, max_tokens=4000 if REVIEW_THINKING else 600,
        extra_body={"chat_template_kwargs": {"enable_thinking": REVIEW_THINKING}},
    )
    data = _parse_json(resp.choices[0].message.content)
    assessment = str(data.get("assessment") or "").strip()
    if not assessment:
        raise ValueError("Review had no assessment")
    actions = [str(a).strip() for a in (data.get("actions") or []) if str(a).strip()][:4]
    risk = data.get("risk") if data.get("risk") in RISKS else "medium"
    return {"risk": risk, "assessment": assessment, "actions": actions,
            "model": NEBIUS_REVIEW_MODEL, "review_ms": int((time.time() - t0) * 1000)}


def start_review(event_id: str, within_budget: bool = True) -> str:
    """Record the review's starting status and return it: pending, off (no model configured),
    or skipped (hourly review budget used up; the dispatch itself is unaffected)."""
    status = "off" if not review_enabled() else ("pending" if within_budget else "skipped")
    with _lock:
        _reviews[event_id] = {"status": status}
        while len(_reviews) > MAX_STORED:
            del _reviews[next(iter(_reviews))]
    return status


def complete_review(event_id: str, situation: dict, client=None):
    """Run the review and store the outcome. Meant to run in the background after the response."""
    try:
        result = {"status": "done", **run_review(situation, client=client)}
    except Exception as e:
        logger.error(f"Ultra review failed for {event_id}: {e}")
        result = {"status": "failed", "error": type(e).__name__}
    with _lock:
        if event_id in _reviews:   # not if the demo was reset or the entry aged out meanwhile
            _reviews[event_id] = result


def get_review(event_id: str) -> Optional[dict]:
    with _lock:
        r = _reviews.get(event_id)
        return dict(r) if r else None


def clear_reviews():
    with _lock:
        _reviews.clear()
