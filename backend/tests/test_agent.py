"""
tests/test_agent.py — Unit tests for crisis intent parser
"""
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import parse_crisis_intent, CrisisIntent, _mock_parse


class TestMockParse:
    def test_trauma_detection(self):
        intent = _mock_parse("Need two trauma surgeons at Bay 4 immediately")
        assert intent.crisis_type == "trauma"
        assert intent.staff_type == "trauma_surgeon"
        assert intent.count == 2
        assert intent.urgency == "critical"

    def test_cardiac_arrest(self):
        intent = _mock_parse("Code blue in ICU, cardiac arrest")
        assert intent.crisis_type == "cardiac_arrest"
        assert intent.staff_type == "cardiologist"
        assert intent.urgency == "critical"

    def test_fire(self):
        intent = _mock_parse("Fire on floor 3, evacuate now")
        assert intent.crisis_type == "fire"
        assert intent.staff_type == "paramedic"

    def test_default_count_is_one(self):
        intent = _mock_parse("Need a nurse in Room 101")
        assert intent.count == 1

    def test_count_extraction_three(self):
        intent = _mock_parse("Send three nurses to the ward")
        assert intent.count == 3

    def test_respiratory(self):
        intent = _mock_parse("Patient having trouble breathing, need help")
        assert intent.crisis_type == "respiratory"
        assert intent.staff_type == "icu_doctor"


class TestGeminiParseWithMock:
    @patch.dict(os.environ, {}, clear=False)
    def test_falls_back_to_mock_without_api_key(self):
        # Remove API key from environment
        env_backup = {}
        for key in ["GOOGLE_API_KEY", "GEMINI_API_KEY"]:
            if key in os.environ:
                env_backup[key] = os.environ.pop(key)

        try:
            intent = parse_crisis_intent("Trauma patient incoming Bay 2")
            assert isinstance(intent, CrisisIntent)
            assert intent.crisis_type == "trauma"
        finally:
            os.environ.update(env_backup)

    def test_crisis_intent_to_dict(self):
        intent = CrisisIntent(
            crisis_type="trauma",
            location="Bay 4",
            staff_type="trauma_surgeon",
            count=2,
            urgency="critical",
            summary="Test summary",
        )
        d = intent.to_dict()
        assert d["crisis_type"] == "trauma"
        assert d["count"] == 2
        assert "summary" in d
