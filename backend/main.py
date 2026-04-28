"""
main.py — FastAPI Cloud Run entry point for Rapid Crisis Response backend
Orchestrates the full pipeline: Gemini → Vertex AI → BigQuery → FCM
"""
import os
import time
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent import parse_crisis_intent
from protocol_search import get_protocol
from staff_finder import find_available_staff
from dispatcher import dispatch_alerts
from logger import log_crisis_event

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── App setup ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚑 Rapid Crisis Response backend starting up")
    logger.info(f"GCP Project: {os.getenv('GCP_PROJECT', 'project-e82fa8f3-3868-42a9-a35')}")
    yield
    logger.info("🛑 Backend shutting down")


app = FastAPI(
    title="Rapid Crisis Response API",
    description="Hospital crisis coordination via voice → AI → FCM dispatch",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ────────────────────────────────
class CrisisRequest(BaseModel):
    transcript: str
    caller_id: Optional[str] = None
    location_hint: Optional[str] = None


class StaffInfo(BaseModel):
    staff_id: str
    name: str
    role: str
    department: str


class CrisisResponse(BaseModel):
    event_id: str
    status: str
    crisis_type: str
    location: str
    urgency: str
    summary: str
    protocol: dict
    staff_dispatched: list[StaffInfo]
    fcm_sent: bool
    dispatch_mode: str
    response_ms: int


# ── Health check ─────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "crisis-response-backend"}


# ── Main pipeline endpoint ───────────────────────────────────
@app.post("/crisis", response_model=CrisisResponse)
async def handle_crisis(req: CrisisRequest):
    """
    Full crisis coordination pipeline:
    1. Parse transcript with Gemini 1.5 Flash
    2. Retrieve protocol from Vertex AI
    3. Find on-shift staff from BigQuery
    4. Dispatch FCM alerts via Cloud Run
    5. Log event to BigQuery
    """
    start_ms = time.time()
    error_msg = None

    if not req.transcript or len(req.transcript.strip()) < 3:
        raise HTTPException(status_code=400, detail="Transcript is too short or empty")

    transcript = req.transcript.strip()
    logger.info(f"▶ Crisis request received: '{transcript[:80]}'")

    try:
        # ── Step 1: Parse intent with Gemini ─────────────────
        logger.info("Step 1: Parsing intent with Gemini 1.5 Flash...")
        intent = parse_crisis_intent(transcript)
        logger.info(f"  Intent: {intent.to_dict()}")

        # Override location if hint provided
        if req.location_hint and intent.location == "unknown":
            intent.location = req.location_hint

        # ── Step 2: Get crisis protocol from Vertex AI ────────
        logger.info("Step 2: Fetching crisis protocol...")
        protocol = get_protocol(intent.crisis_type, intent.summary)
        logger.info(f"  Protocol: {protocol.name} ({protocol.code}) [source: {protocol.source}]")

        # ── Step 3: Find available staff from BigQuery ────────
        logger.info(f"Step 3: Finding {intent.count}x {intent.staff_type}...")
        staff_list = find_available_staff(intent.staff_type, intent.count)
        logger.info(f"  Found {len(staff_list)} staff: {[s.name for s in staff_list]}")

        if not staff_list:
            raise HTTPException(
                status_code=503,
                detail=f"No available {intent.staff_type} staff found. Manual coordination required."
            )

        # ── Step 4: Dispatch FCM notifications ────────────────
        logger.info("Step 4: Dispatching FCM alerts...")
        dispatch_result = dispatch_alerts(
            staff_list=staff_list,
            crisis_type=intent.crisis_type,
            location=intent.location,
            urgency=intent.urgency,
            summary=intent.summary,
        )
        logger.info(f"  Dispatched to: {dispatch_result.sent_to} [mode: {dispatch_result.mode}]")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Pipeline error: {e}")
        error_msg = str(e)
        raise HTTPException(status_code=500, detail=f"Crisis pipeline error: {e}")

    finally:
        # ── Step 5: Log to BigQuery (always) ──────────────────
        response_ms = int((time.time() - start_ms) * 1000)
        try:
            event_id = log_crisis_event(
                transcript=transcript,
                crisis_type=getattr(intent, "crisis_type", "unknown"),
                location=getattr(intent, "location", "unknown"),
                urgency=getattr(intent, "urgency", "unknown"),
                staff_type=getattr(intent, "staff_type", "unknown"),
                count_requested=getattr(intent, "count", 0),
                protocol_matched=getattr(protocol, "code", ""),
                staff_dispatched=[s.to_dict() for s in staff_list] if 'staff_list' in dir() else [],
                fcm_sent=getattr(dispatch_result, "success", False) if 'dispatch_result' in dir() else False,
                response_ms=response_ms,
                error=error_msg,
            )
        except Exception as log_err:
            logger.error(f"Logging failed: {log_err}")
            event_id = "log-failed"

    return CrisisResponse(
        event_id=event_id,
        status="dispatched",
        crisis_type=intent.crisis_type,
        location=intent.location,
        urgency=intent.urgency,
        summary=intent.summary,
        protocol={
            "name": protocol.name,
            "code": protocol.code,
            "steps": protocol.steps,
        },
        staff_dispatched=[
            StaffInfo(
                staff_id=s.staff_id,
                name=s.name,
                role=s.role,
                department=s.department,
            )
            for s in staff_list
        ],
        fcm_sent=dispatch_result.success,
        dispatch_mode=dispatch_result.mode,
        response_ms=response_ms,
    )


# ── Staff list endpoint (for Flutter to show available staff) ─
@app.get("/staff")
async def list_staff(role: Optional[str] = None):
    """List currently on-shift staff, optionally filtered by role."""
    from staff_finder import MOCK_STAFF
    staff = MOCK_STAFF if not role else [s for s in MOCK_STAFF if s["role"] == role]
    return {"staff": staff, "count": len(staff)}
