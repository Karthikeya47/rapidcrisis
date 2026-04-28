"""
protocol_search.py — Vertex AI Vector Search for crisis protocols
Falls back to keyword-match mock when Vertex AI credentials are unavailable.
"""
import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

GCP_PROJECT = os.getenv("GCP_PROJECT", "project-e82fa8f3-3868-42a9-a35")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")
VERTEX_INDEX_ENDPOINT = os.getenv("VERTEX_INDEX_ENDPOINT", "")
VERTEX_DEPLOYED_INDEX_ID = os.getenv("VERTEX_DEPLOYED_INDEX_ID", "")

# ────────────────────────────────────────────────────────────
# Hardcoded crisis protocols (used for mock mode + seeding)
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
    source: str  # "vertex_ai" or "mock"


def get_protocol(crisis_type: str, crisis_summary: str) -> ProtocolResult:
    """
    Retrieve the crisis protocol.
    Attempts Vertex AI Vector Search first; falls back to keyword lookup.
    """
    if VERTEX_INDEX_ENDPOINT and VERTEX_DEPLOYED_INDEX_ID:
        try:
            return _vertex_search(crisis_type, crisis_summary)
        except Exception as e:
            logger.warning(f"Vertex AI search failed, using mock: {e}")

    return _mock_protocol(crisis_type)


def _mock_protocol(crisis_type: str) -> ProtocolResult:
    data = PROTOCOLS.get(crisis_type, PROTOCOLS["unknown"])
    return ProtocolResult(
        name=data["name"],
        code=data["code"],
        steps=data["steps"],
        staff_minimum=data["staff_minimum"],
        source="mock",
    )


def _vertex_search(crisis_type: str, crisis_summary: str) -> ProtocolResult:
    """
    Real Vertex AI Vector Search implementation.
    Embeds the crisis summary and finds the nearest protocol vector.
    """
    from google.cloud import aiplatform
    from vertexai.language_models import TextEmbeddingModel

    aiplatform.init(project=GCP_PROJECT, location=GCP_REGION)

    # Get embedding for crisis description
    embed_model = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")
    embeddings = embed_model.get_embeddings([crisis_summary])
    query_vector = embeddings[0].values

    # Query Vertex AI Matching Engine
    index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
        index_endpoint_name=VERTEX_INDEX_ENDPOINT
    )
    results = index_endpoint.find_neighbors(
        deployed_index_id=VERTEX_DEPLOYED_INDEX_ID,
        queries=[query_vector],
        num_neighbors=1,
    )

    if results and results[0]:
        matched_id = results[0][0].id  # Protocol key
        return _mock_protocol(matched_id)

    return _mock_protocol(crisis_type)
