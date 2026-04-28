"""
tests/test_protocol_search.py — Unit tests for crisis protocol retrieval
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from protocol_search import get_protocol, _mock_protocol, ProtocolResult, PROTOCOLS


class TestMockProtocol:
    def test_trauma_protocol(self):
        result = _mock_protocol("trauma")
        assert isinstance(result, ProtocolResult)
        assert result.name == "Mass Trauma Protocol"
        assert result.code == "MTP-01"
        assert result.source == "mock"
        assert len(result.steps) > 0

    def test_cardiac_arrest_protocol(self):
        result = _mock_protocol("cardiac_arrest")
        assert result.code == "CB-02"
        assert "CPR" in " ".join(result.steps)

    def test_fire_protocol(self):
        result = _mock_protocol("fire")
        assert result.code == "FIRE-03"
        assert "RACE" in result.steps[0]

    def test_respiratory_protocol(self):
        result = _mock_protocol("respiratory")
        assert result.code == "RD-04"

    def test_mass_casualty_protocol(self):
        result = _mock_protocol("mass_casualty")
        assert result.code == "MCI-05"

    def test_chemical_spill_protocol(self):
        result = _mock_protocol("chemical_spill")
        assert result.code == "HAZ-06"

    def test_unknown_type_returns_general(self):
        result = _mock_protocol("unknown")
        assert result.code == "GEN-00"
        assert result.name == "General Emergency Protocol"

    def test_invalid_type_falls_back_to_general(self):
        result = _mock_protocol("nonexistent_crisis")
        assert result.code == "GEN-00"

    def test_all_protocols_have_steps(self):
        for crisis_type in PROTOCOLS:
            result = _mock_protocol(crisis_type)
            assert len(result.steps) > 0, f"Protocol {crisis_type} has no steps"

    def test_all_protocols_have_staff_minimum(self):
        for crisis_type in PROTOCOLS:
            result = _mock_protocol(crisis_type)
            assert len(result.staff_minimum) > 0, f"Protocol {crisis_type} has no staff_minimum"


class TestGetProtocol:
    def test_get_protocol_without_vertex_ai(self):
        """Without Vertex AI config, should fall back to mock."""
        result = get_protocol("trauma", "2 trauma surgeons needed urgently")
        assert isinstance(result, ProtocolResult)
        assert result.source == "mock"
        assert result.code == "MTP-01"

    def test_get_protocol_cardiac(self):
        result = get_protocol("cardiac_arrest", "Code blue cardiac arrest")
        assert result.code == "CB-02"

    def test_get_protocol_returns_steps(self):
        result = get_protocol("fire", "Fire on floor 3")
        assert len(result.steps) > 0
        assert isinstance(result.steps[0], str)
