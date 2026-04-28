"""
staff_finder.py — Query BigQuery/Cloud SQL for on-shift staff
Returns matched staff sorted by role relevance.
"""
import os
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

GCP_PROJECT = os.getenv("GCP_PROJECT", "project-e82fa8f3-3868-42a9-a35")
BQ_DATASET = os.getenv("BQ_DATASET", "crisis_response")
BQ_TABLE = "staff_schedules"

# ────────────────────────────────────────────────────────────
# Mock in-memory staff pool (for local dev without BigQuery)
# ────────────────────────────────────────────────────────────
MOCK_STAFF = [
    {"staff_id": "S001", "name": "Dr. Arjun Mehta",    "role": "trauma_surgeon",    "department": "ER",  "fcm_token": "mock_token_S001", "on_shift": True},
    {"staff_id": "S002", "name": "Dr. Priya Sharma",   "role": "trauma_surgeon",    "department": "OR",  "fcm_token": "mock_token_S002", "on_shift": True},
    {"staff_id": "S003", "name": "Dr. Ravi Kumar",     "role": "cardiologist",      "department": "ICU", "fcm_token": "mock_token_S003", "on_shift": True},
    {"staff_id": "S004", "name": "Nurse Lakshmi Nair", "role": "nurse",             "department": "ER",  "fcm_token": "mock_token_S004", "on_shift": True},
    {"staff_id": "S005", "name": "Nurse Deepa Rao",    "role": "nurse",             "department": "ICU", "fcm_token": "mock_token_S005", "on_shift": True},
    {"staff_id": "S006", "name": "Dr. Suresh Iyer",    "role": "anesthesiologist",  "department": "OR",  "fcm_token": "mock_token_S006", "on_shift": True},
    {"staff_id": "S007", "name": "Dr. Meena Pillai",   "role": "icu_doctor",        "department": "ICU", "fcm_token": "mock_token_S007", "on_shift": True},
    {"staff_id": "S008", "name": "Paramedic Arun Das", "role": "paramedic",         "department": "ER",  "fcm_token": "mock_token_S008", "on_shift": True},
]


@dataclass
class StaffMember:
    staff_id: str
    name: str
    role: str
    department: str
    fcm_token: str

    def to_dict(self) -> dict:
        return {
            "staff_id": self.staff_id,
            "name": self.name,
            "role": self.role,
            "department": self.department,
            "fcm_token": self.fcm_token,
        }


def find_available_staff(staff_type: str, count: int) -> list[StaffMember]:
    """
    Find on-shift staff matching the required role.
    Tries BigQuery first; falls back to mock data.
    """
    try:
        return _bigquery_find(staff_type, count)
    except Exception as e:
        logger.warning(f"BigQuery unavailable, using mock staff: {e}")
        return _mock_find(staff_type, count)


def _bigquery_find(staff_type: str, count: int) -> list[StaffMember]:
    from google.cloud import bigquery

    client = bigquery.Client(project=GCP_PROJECT)
    now = datetime.now(timezone.utc).isoformat()

    query = f"""
        SELECT staff_id, name, role, department, fcm_token
        FROM `{GCP_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`
        WHERE on_shift = TRUE
          AND role = @role
          AND shift_start <= @now
          AND shift_end >= @now
          AND fcm_token IS NOT NULL
        ORDER BY shift_start ASC
        LIMIT @limit
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("role", "STRING", staff_type),
            bigquery.ScalarQueryParameter("now", "STRING", now),
            bigquery.ScalarQueryParameter("limit", "INT64", count),
        ]
    )

    results = client.query(query, job_config=job_config).result()
    staff = []
    for row in results:
        staff.append(StaffMember(
            staff_id=row.staff_id,
            name=row.name,
            role=row.role,
            department=row.department,
            fcm_token=row.fcm_token,
        ))

    if not staff:
        # Fallback: find any on-shift general_doctor
        logger.warning(f"No on-shift {staff_type} found in BigQuery, broadening search")
        return _mock_find("general_doctor", count)

    return staff


def _mock_find(staff_type: str, count: int) -> list[StaffMember]:
    matched = [
        s for s in MOCK_STAFF
        if s["role"] == staff_type and s["on_shift"]
    ]
    # Fallback to any on-shift staff
    if not matched:
        matched = [s for s in MOCK_STAFF if s["on_shift"]]

    return [
        StaffMember(
            staff_id=s["staff_id"],
            name=s["name"],
            role=s["role"],
            department=s["department"],
            fcm_token=s["fcm_token"],
        )
        for s in matched[:count]
    ]
