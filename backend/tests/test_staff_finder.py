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


def test_claim_is_atomic_under_concurrency():
    """Two dispatches claiming the same people at once: each person goes to exactly one event."""
    import threading
    from staff_finder import claim

    wanted = ["S001", "S002", "S004", "S005", "S006"]
    results = {}
    barrier = threading.Barrier(2)

    def go(ev):
        barrier.wait()
        results[ev] = claim(wanted, ev)

    threads = [threading.Thread(target=go, args=(ev,)) for ev in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not set(results["A"]) & set(results["B"])
    assert sorted(results["A"] + results["B"]) == sorted(wanted)


def test_claim_skips_busy_and_off_shift():
    from staff_finder import claim, mark_busy
    mark_busy(["S001"], "other")
    assert claim(["S001", "S002", "S012", "S999"], "ev") == ["S002"]  # busy, off shift, unknown are skipped
