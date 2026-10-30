"""
tests/test_eval.py — the evaluation set is well-formed and the scorer is strict but fair.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "eval"))

from run_eval import load_cases, location_ok, score, team_ok  # noqa: E402
from protocol_search import PROTOCOLS  # noqa: E402


def test_cases_are_well_formed():
    cases = load_cases()
    assert len(cases) >= 40
    assert len({c["id"] for c in cases}) == len(cases)
    for c in cases:
        assert c["crisis_type"] in PROTOCOLS and c["crisis_type"] != "unknown"
        assert c["location"] is None or (isinstance(c["location"], list) and c["location"])


def test_location_matching():
    assert location_ok("Bay 6", ["bay 6"])
    assert not location_ok("Bay 4", ["bay 6"])          # a correction must be followed
    assert location_ok("ward six", ["ward 6"])          # number words count
    assert not location_ok("Bay 46", ["bay 4"])         # whole words only
    assert location_ok("unknown", None)                 # nothing was said: unknown is right
    assert not location_ok("Lobby", None)               # ...and inventing a place is wrong


def test_team_must_cover_protocol_roles():
    assert team_ok(["trauma_surgeon", "trauma_surgeon", "anesthesiologist", "nurse"], "trauma")
    assert not team_ok(["trauma_surgeon"], "trauma")


def test_score_needs_all_three():
    case = {"crisis_type": "respiratory", "location": ["icu"]}
    assert score(case, "respiratory", "ICU", ["icu_doctor", "nurse"])["all"]
    assert not score(case, "respiratory", "ICU", ["icu_doctor"])["all"]
    assert not score(case, "trauma", "ICU", ["icu_doctor", "nurse"])["all"]
