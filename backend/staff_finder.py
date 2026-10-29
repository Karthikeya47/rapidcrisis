"""
staff_finder.py — on-shift staff roster with live availability.

Staff who are dispatched to an emergency are marked busy, so the agent
never sends the same person to two emergencies at once. Resolving an
event frees them again.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

ROLES = [
    "trauma_surgeon", "cardiologist", "anesthesiologist", "icu_doctor",
    "general_doctor", "nurse", "paramedic",
]

# Demo roster (a real deployment would load this from the hospital's shift system)
MOCK_STAFF = [
    {"staff_id": "S001", "name": "Dr. Arjun Mehta",     "role": "trauma_surgeon",   "department": "ER",  "fcm_token": "mock_token_S001", "on_shift": True},
    {"staff_id": "S002", "name": "Dr. Priya Sharma",    "role": "trauma_surgeon",   "department": "OR",  "fcm_token": "mock_token_S002", "on_shift": True},
    {"staff_id": "S003", "name": "Dr. Ravi Kumar",      "role": "cardiologist",     "department": "ICU", "fcm_token": "mock_token_S003", "on_shift": True},
    {"staff_id": "S004", "name": "Nurse Lakshmi Nair",  "role": "nurse",            "department": "ER",  "fcm_token": "mock_token_S004", "on_shift": True},
    {"staff_id": "S005", "name": "Nurse Deepa Rao",     "role": "nurse",            "department": "ICU", "fcm_token": "mock_token_S005", "on_shift": True},
    {"staff_id": "S006", "name": "Dr. Suresh Iyer",     "role": "anesthesiologist", "department": "OR",  "fcm_token": "mock_token_S006", "on_shift": True},
    {"staff_id": "S007", "name": "Dr. Meena Pillai",    "role": "icu_doctor",       "department": "ICU", "fcm_token": "mock_token_S007", "on_shift": True},
    {"staff_id": "S008", "name": "Paramedic Arun Das",  "role": "paramedic",        "department": "ER",  "fcm_token": "mock_token_S008", "on_shift": True},
    {"staff_id": "S009", "name": "Dr. Kavya Reddy",     "role": "general_doctor",   "department": "OPD", "fcm_token": "mock_token_S009", "on_shift": True},
    {"staff_id": "S010", "name": "Nurse Joseph Thomas", "role": "nurse",            "department": "Ward","fcm_token": "mock_token_S010", "on_shift": True},
    {"staff_id": "S011", "name": "Paramedic Neha Singh","role": "paramedic",        "department": "ER",  "fcm_token": "mock_token_S011", "on_shift": True},
    {"staff_id": "S012", "name": "Dr. Farhan Ali",      "role": "cardiologist",     "department": "CCU", "fcm_token": "mock_token_S012", "on_shift": False},
]

_lock = threading.Lock()
_busy: dict[str, str] = {}   # staff_id -> event_id


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

    def public_dict(self) -> dict:
        d = self.to_dict()
        d.pop("fcm_token")
        return d


def _to_member(s: dict) -> StaffMember:
    return StaffMember(s["staff_id"], s["name"], s["role"], s["department"], s["fcm_token"])


def _is_free(s: dict, exclude: Optional[set] = None) -> bool:
    return s["on_shift"] and s["staff_id"] not in _busy and s["staff_id"] not in (exclude or set())


def find_available_staff(staff_type: str, count: int, exclude: Optional[set] = None) -> list[StaffMember]:
    """Free, on-shift staff of the role. Unknown roles fall back to any free doctor/nurse."""
    return _mock_find(staff_type, count, exclude)


def _mock_find(staff_type: str, count: int, exclude: Optional[set] = None) -> list[StaffMember]:
    with _lock:
        matched = [s for s in MOCK_STAFF if s["role"] == staff_type and _is_free(s, exclude)]
        if not matched and staff_type not in ROLES:
            matched = [s for s in MOCK_STAFF if _is_free(s, exclude)]
        if not matched:
            logger.warning(f"No free {staff_type} on shift — escalation needed")
        return [_to_member(s) for s in matched[:max(1, count)]]


def mark_busy(staff_ids: list[str], event_id: str):
    with _lock:
        for sid in staff_ids:
            _busy[sid] = event_id


def release_event(event_id: str) -> list[str]:
    with _lock:
        freed = [sid for sid, ev in _busy.items() if ev == event_id]
        for sid in freed:
            del _busy[sid]
        return freed


def reset_availability():
    with _lock:
        _busy.clear()


def roster(role: Optional[str] = None) -> list[dict]:
    with _lock:
        out = []
        for s in MOCK_STAFF:
            if role and s["role"] != role:
                continue
            status = "off_shift" if not s["on_shift"] else ("busy" if s["staff_id"] in _busy else "available")
            out.append({
                "staff_id": s["staff_id"], "name": s["name"], "role": s["role"],
                "department": s["department"], "status": status, "event_id": _busy.get(s["staff_id"]),
            })
        return out
