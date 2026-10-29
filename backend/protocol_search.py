"""
protocol_search.py — hospital crisis protocol library.
The agent calls this as a tool (lookup_protocol).
"""
import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# Crisis protocols
# ────────────────────────────────────────────────────────────
PROTOCOLS: dict[str, dict] = {
    "trauma": {
        "name": "Mass Trauma Protocol",
        "code": "MTP-01",
        "steps": [
            "Activate trauma bay",
            "Assemble trauma team: 2 surgeons, 1 anesthesiologist, 2 nurses",
            "Notify blood bank for O-negative reserves",
            "Clear Bay 4 / designated trauma bay",
            "Initiate massive transfusion protocol if hemorrhagic shock suspected",
        ],
        "staff_minimum": {"trauma_surgeon": 2, "anesthesiologist": 1, "nurse": 2},
    },
    "cardiac_arrest": {
        "name": "Code Blue — Cardiac Arrest Protocol",
        "code": "CB-02",
        "steps": [
            "Call Code Blue over PA system",
            "Begin CPR immediately",
            "Attach AED / defibrillator",
            "Cardiologist to lead resuscitation",
            "Prepare epinephrine and atropine",
            "Document time of arrest and interventions",
        ],
        "staff_minimum": {"cardiologist": 1, "nurse": 2, "paramedic": 1},
    },
    "fire": {
        "name": "RACE Fire Protocol",
        "code": "FIRE-03",
        "steps": [
            "RACE: Rescue, Alarm, Contain, Extinguish/Evacuate",
            "Call emergency services (fire dept)",
            "Evacuate patients from affected zone",
            "Close all fire doors",
            "Do NOT use elevators",
        ],
        "staff_minimum": {"paramedic": 2, "nurse": 3},
    },
    "respiratory": {
        "name": "Respiratory Distress Protocol",
        "code": "RD-04",
        "steps": [
            "Administer supplemental oxygen immediately",
            "Pulse oximetry and ABG assessment",
            "Prepare intubation kit if SpO2 < 90%",
            "ICU consult",
            "Consider BiPAP/CPAP",
        ],
        "staff_minimum": {"icu_doctor": 1, "nurse": 1},
    },
    "mass_casualty": {
        "name": "Mass Casualty Incident Protocol",
        "code": "MCI-05",
        "steps": [
            "Activate hospital incident command system (HICS)",
            "Triage all incoming casualties using START method",
            "Clear elective procedures",
            "Call all off-duty trauma staff",
            "Establish command post at ED entrance",
        ],
        "staff_minimum": {"trauma_surgeon": 3, "nurse": 5, "paramedic": 3},
    },
    "chemical_spill": {
        "name": "Hazmat / Chemical Exposure Protocol",
        "code": "HAZ-06",
        "steps": [
            "Isolate contaminated area",
            "Activate HAZMAT team",
            "Decontamination shower for exposed persons",
            "PPE Level B minimum for responders",
            "Notify poison control center",
        ],
        "staff_minimum": {"paramedic": 2, "nurse": 2},
    },
    "unknown": {
        "name": "General Emergency Protocol",
        "code": "GEN-00",
        "steps": [
            "Assess situation",
            "Call attending physician",
            "Document observations",
        ],
        "staff_minimum": {"general_doctor": 1},
    },
}


@dataclass
class ProtocolResult:
    name: str
    code: str
    steps: list[str]
    staff_minimum: dict[str, int]
    source: str


def get_protocol(crisis_type: str, crisis_summary: str = "") -> ProtocolResult:
    """Return the hospital protocol for a crisis type (General protocol if unknown)."""
    data = PROTOCOLS.get(crisis_type, PROTOCOLS["unknown"])
    return ProtocolResult(
        name=data["name"],
        code=data["code"],
        steps=data["steps"],
        staff_minimum=data["staff_minimum"],
        source="protocol_library",
    )


# Backwards-compatible alias
_mock_protocol = get_protocol
