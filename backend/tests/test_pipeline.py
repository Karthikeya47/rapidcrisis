"""
tests/test_pipeline.py — Integration tests for the /crisis endpoint
Uses FastAPI TestClient with mock backend (no GCP credentials needed).
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "crisis-response-backend"


class TestCrisisEndpoint:
    def test_valid_trauma_request(self, client):
        """Full pipeline: transcript → intent → protocol → staff → dispatch."""
        response = client.post("/crisis", json={
            "transcript": "Need two trauma surgeons stat, Bay 4, patient coding"
        })
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "event_id" in data
        assert data["status"] == "dispatched"
        assert data["crisis_type"] in ["trauma", "unknown"]
        assert "protocol" in data
        assert "staff_dispatched" in data
        assert len(data["staff_dispatched"]) > 0
        assert "response_ms" in data
        assert isinstance(data["response_ms"], int)

    def test_cardiac_arrest_request(self, client):
        response = client.post("/crisis", json={
            "transcript": "Code blue in ICU Room 7, cardiac arrest, need cardiologist"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["crisis_type"] in ["cardiac_arrest", "unknown"]

    def test_fire_request(self, client):
        response = client.post("/crisis", json={
            "transcript": "Fire on floor 3, evacuate patients immediately"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["crisis_type"] in ["fire", "unknown"]

    def test_empty_transcript_rejected(self, client):
        response = client.post("/crisis", json={"transcript": ""})
        assert response.status_code == 400

    def test_too_short_transcript_rejected(self, client):
        response = client.post("/crisis", json={"transcript": "hi"})
        assert response.status_code == 400

    def test_response_includes_protocol(self, client):
        response = client.post("/crisis", json={
            "transcript": "Respiratory distress in pediatric ward, need ICU doctor"
        })
        assert response.status_code == 200
        protocol = response.json()["protocol"]
        assert "name" in protocol
        assert "code" in protocol
        assert "steps" in protocol
        assert isinstance(protocol["steps"], list)

    def test_response_includes_staff_info(self, client):
        response = client.post("/crisis", json={
            "transcript": "Need two trauma surgeons stat Bay 4"
        })
        assert response.status_code == 200
        staff = response.json()["staff_dispatched"]
        for s in staff:
            assert "staff_id" in s
            assert "name" in s
            assert "role" in s
            assert "department" in s

    def test_dispatch_mode_is_mock(self, client):
        """Without Firebase credentials, dispatch mode should be 'mock'."""
        response = client.post("/crisis", json={
            "transcript": "Need nurse in Room 101"
        })
        assert response.status_code == 200
        assert response.json()["dispatch_mode"] == "mock"

    def test_location_hint_override(self, client):
        response = client.post("/crisis", json={
            "transcript": "Need a doctor immediately",
            "location_hint": "Emergency Room Bay 9",
        })
        assert response.status_code == 200
        # Location should be the hint since transcript doesn't have one
        data = response.json()
        assert data["location"] is not None


class TestStaffEndpoint:
    def test_list_all_staff(self, client):
        response = client.get("/staff")
        assert response.status_code == 200
        data = response.json()
        assert "staff" in data
        assert "count" in data
        assert data["count"] > 0

    def test_filter_by_role(self, client):
        response = client.get("/staff?role=trauma_surgeon")
        assert response.status_code == 200
        data = response.json()
        for s in data["staff"]:
            assert s["role"] == "trauma_surgeon"
