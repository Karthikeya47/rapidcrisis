"""
tests/test_dispatcher.py — Unit tests for FCM dispatch module
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dispatcher import dispatch_alerts, _mock_dispatch, _build_notification_data, DispatchResult
from staff_finder import StaffMember


@pytest.fixture
def mock_staff():
    """Sample staff list for testing dispatch."""
    return [
        StaffMember(
            staff_id="S001",
            name="Dr. Arjun Mehta",
            role="trauma_surgeon",
            department="ER",
            fcm_token="mock_token_S001",
        ),
        StaffMember(
            staff_id="S002",
            name="Dr. Priya Sharma",
            role="trauma_surgeon",
            department="OR",
            fcm_token="mock_token_S002",
        ),
    ]


class TestBuildNotificationData:
    def test_critical_urgency(self):
        data = _build_notification_data("trauma", "Bay 4", "critical", "2 surgeons needed")
        assert "🚨" in data["title"]
        assert "TRAUMA" in data["title"]
        assert "Bay 4" in data["body"]

    def test_high_urgency(self):
        data = _build_notification_data("cardiac_arrest", "ICU", "high", "Cardiologist needed")
        assert "⚠️" in data["title"]
        assert "CARDIAC ARREST" in data["title"]

    def test_medium_urgency(self):
        data = _build_notification_data("respiratory", "Floor 3", "medium", "Breathing issues")
        assert "📢" in data["title"]

    def test_notification_body_format(self):
        data = _build_notification_data("fire", "Floor 5", "critical", "Evacuate now")
        assert "Evacuate now" in data["body"]
        assert "Floor 5" in data["body"]

    def test_all_fields_present(self):
        data = _build_notification_data("trauma", "Bay 1", "critical", "Test")
        required_keys = ["crisis_type", "location", "urgency", "summary", "title", "body"]
        for key in required_keys:
            assert key in data


class TestMockDispatch:
    def test_mock_dispatch_succeeds(self, mock_staff):
        result = _mock_dispatch(mock_staff, "trauma", "Bay 4", "critical", "Test alert")
        assert isinstance(result, DispatchResult)
        assert result.success is True
        assert result.mode == "mock"
        assert len(result.sent_to) == 2
        assert len(result.failed) == 0

    def test_mock_dispatch_includes_all_staff_ids(self, mock_staff):
        result = _mock_dispatch(mock_staff, "trauma", "Bay 4", "critical", "Test")
        assert "S001" in result.sent_to
        assert "S002" in result.sent_to

    def test_empty_staff_list(self):
        result = _mock_dispatch([], "trauma", "Bay 4", "critical", "Test")
        assert result.success is True  # Empty but no errors
        assert len(result.sent_to) == 0


class TestDispatchAlerts:
    def test_dispatch_without_firebase_uses_mock(self, mock_staff):
        """Without FIREBASE_CREDENTIALS, dispatch should use mock mode."""
        result = dispatch_alerts(
            staff_list=mock_staff,
            crisis_type="trauma",
            location="Bay 4",
            urgency="critical",
            summary="2 trauma surgeons needed at Bay 4",
        )
        assert result.mode == "mock"
        assert result.success is True
        assert len(result.sent_to) == 2
