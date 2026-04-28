"""
main.py — FastAPI Cloud Run entry point for Rapid Crisis Response backend
Orchestrates the full pipeline: Gemini (Function Calling) → Vertex AI → BigQuery → FCM
"""
import os
import time
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import run_crisis_agent
from dispatcher import dispatch_alerts
from logger import log_crisis_event

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚑 Rapid Crisis Response backend starting up (Agentic Mode)")
    yield
    logger.info("🛑 Backend shutting down")

app = FastAPI(
    title="Rapid Crisis Response API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class CrisisRequest(BaseModel):
    transcript: str
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

@app.post("/crisis", response_model=CrisisResponse)
async def handle_crisis(req: CrisisRequest):
    start_ms = time.time()

    if not req.transcript or len(req.transcript.strip()) < 3:
        raise HTTPException(status_code=400, detail="Transcript too short")

    transcript = req.transcript.strip()
    logger.info(f"▶ Processing Crisis: '{transcript}'")

    try:
        # ── Step 1-3: Gemini Agent (Parse + Protocol + Staff) ──
        # Uses Function Calling to orchestrate search tools
        ctx = run_crisis_agent(transcript, req.location_hint)

        # ── Step 4: Dispatch FCM ──────────────────────────────
        dispatch_result = dispatch_alerts(
            staff_list=ctx.staff_list,
            crisis_type=ctx.crisis_type,
            location=ctx.location,
            urgency=ctx.urgency,
            summary=ctx.summary,
        )

        response_ms = int((time.time() - start_ms) * 1000)

        # ── Step 5: Log to BigQuery ───────────────────────────
        event_id = log_crisis_event(
            transcript=transcript,
            crisis_type=ctx.crisis_type,
            location=ctx.location,
            urgency=ctx.urgency,
            staff_type=ctx.staff_type,
            count_requested=ctx.count,
            protocol_matched=ctx.protocol.code if ctx.protocol else "unknown",
            staff_dispatched=[s.to_dict() for s in ctx.staff_list],
            fcm_sent=dispatch_result.success,
            response_ms=response_ms,
        )

        return CrisisResponse(
            event_id=event_id,
            status="dispatched",
            crisis_type=ctx.crisis_type,
            location=ctx.location,
            urgency=ctx.urgency,
            summary=ctx.summary,
            protocol={
                "name": ctx.protocol.name if ctx.protocol else "General",
                "code": ctx.protocol.code if ctx.protocol else "GEN-00",
                "steps": ctx.protocol.steps if ctx.protocol else [],
            },
            staff_dispatched=[
                StaffInfo(staff_id=s.staff_id, name=s.name, role=s.role, department=s.department)
                for s in ctx.staff_list
            ],
            fcm_sent=dispatch_result.success,
            dispatch_mode=dispatch_result.mode,
            response_ms=response_ms,
        )

    except Exception as e:
        logger.exception("Pipeline failed")
        raise HTTPException(status_code=500, detail=str(e))
