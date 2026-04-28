"""
tests/test_staff_finder.py — Unit tests for staff finder mock
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from staff_finder import _mock_find, StaffMember


class TestMockFind:
    def test_find_trauma_surgeon(self):
        staff = _mock_find("trauma_surgeon", 2)
        assert len(staff) == 2
        for s in staff:
            assert s.role == "trauma_surgeon"
            assert isinstance(s, StaffMember)

    def test_find_nurse(self):
        staff = _mock_find("nurse", 1)
        assert len(staff) == 1
        assert staff[0].role == "nurse"

    def test_fallback_for_unknown_role(self):
        # Non-existent role should still return staff (general fallback)
        staff = _mock_find("exotic_specialist", 1)
        assert len(staff) >= 1

    def test_count_limit(self):
        staff = _mock_find("nurse", 1)
        assert len(staff) <= 1

    def test_staff_has_fcm_token(self):
        staff = _mock_find("trauma_surgeon", 1)
        assert staff[0].fcm_token is not None
        assert len(staff[0].fcm_token) > 0
