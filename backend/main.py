"""
main.py — FastAPI server for Rapid Crisis Response.

Pipeline:  voice/text -> Nemotron Super agent (tool calls: protocol + staff) -> pager alerts -> audit log
           then, in the background, Nemotron Ultra reviews the dispatch against the whole hospital
Also serves the web dashboard at "/".
"""
import logging
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import run_crisis_agent, nemotron_enabled, NEBIUS_MODEL
from dispatcher import dispatch_alerts, inbox, clear_inboxes
from limits import RateLimiter
from logger import log_crisis_event, recent_events, mark_resolved, clear_events
from review import (NEBIUS_REVIEW_MODEL, build_situation, clear_reviews, complete_review, get_review,
                    review_enabled, start_review)
from staff_finder import claim, find_available_staff, roster, release_event, reset_availability

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# Public-demo guards: every character and every call is billed on Token Factory.
MAX_TRANSCRIPT_CHARS = 500
MAX_LOCATION_CHARS = 100
TEAM_MARGIN = 2   # people allowed beyond the protocol's minimum team
dispatch_limiter = RateLimiter(int(os.getenv("DISPATCH_LIMIT_PER_MINUTE", "5")), 60)
review_limiter = RateLimiter(int(os.getenv("REVIEW_LIMIT_PER_HOUR", "60")), 3600)
RESET_TOKEN = os.getenv("RESET_TOKEN")  # if set, POST /reset needs header X-Reset-Token


def _client_ip(request: Request) -> str:
    """Caller's address; behind a proxy (Render, Nebius) the first X-Forwarded-For entry."""
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = f"NVIDIA {NEBIUS_MODEL} via Nebius Token Factory" if nemotron_enabled() else "offline rules (set NEBIUS_API_KEY)"
    logger.info(f"🚑 Rapid Crisis Response starting — brain: {engine}")
    if review_enabled():
        logger.info(f"Dispatch reviews: NVIDIA {NEBIUS_REVIEW_MODEL}")
    if nemotron_enabled():
        from agent import _make_client
        _make_client()  # warm up: import SDK and open the client before the first emergency
    yield


app = FastAPI(title="Rapid Crisis Response API", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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
    engine: str
    follow_up: Optional[str] = None
    reasoning: str = ""
    warnings: list[str] = []
    trace: list[dict] = []
    review: str = "off"                 # "pending" while Nemotron Ultra reviews, "off" without a model


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "crisis-response-backend",
        "engine": "nemotron" if nemotron_enabled() else "rules",
        "model": NEBIUS_MODEL if nemotron_enabled() else None,
        "review_model": NEBIUS_REVIEW_MODEL if review_enabled() else None,
    }


def _claim_team(team: list, event_id: str) -> list:
    """Lock the agent's chosen staff to this event. Anyone a simultaneous dispatch took in the
    meantime is replaced by another free person of the same role, if there is one."""
    claimed = set(claim([s.staff_id for s in team], event_id))
    final = [s for s in team if s.staff_id in claimed]
    for lost in (s for s in team if s.staff_id not in claimed):
        for sub in find_available_staff(lost.role, 1, exclude=claimed):
            if claim([sub.staff_id], event_id):
                claimed.add(sub.staff_id)
                final.append(sub)
    return final


# Plain def, not async: the model call is blocking, so FastAPI runs this in a worker thread
# and the dashboard's polling keeps being served while Nemotron thinks.
@app.post("/crisis", response_model=CrisisResponse)
def handle_crisis(req: CrisisRequest, request: Request, background: BackgroundTasks):
    start = time.time()
    transcript = (req.transcript or "").strip()
    if len(transcript) < 3:
        raise HTTPException(status_code=400, detail="Transcript too short")
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        raise HTTPException(status_code=400, detail=f"Transcript too long (max {MAX_TRANSCRIPT_CHARS} characters)")
    if not dispatch_limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many dispatches from this device. Wait a minute")
    location_hint = (req.location_hint or "").strip()[:MAX_LOCATION_CHARS] or None

    logger.info(f"▶ Crisis: '{transcript}'")
    try:
        ctx = run_crisis_agent(transcript, location_hint)
        event_id = str(uuid.uuid4())

        # A request like "page everyone" must not empty the hospital: cap at the protocol team + a margin
        cap_note = None
        team_cap = (sum(ctx.protocol.staff_minimum.values()) if ctx.protocol else 1) + TEAM_MARGIN
        if len(ctx.staff_list) > team_cap:
            ctx.staff_list = ctx.staff_list[:team_cap]
            cap_note = f"Team capped at {team_cap} for this emergency; page more people manually if needed"

        # Lock these staff to this event so they are not double-booked
        ctx.staff_list = _claim_team(ctx.staff_list, event_id)
        dispatch = dispatch_alerts(ctx.staff_list, ctx.crisis_type, ctx.location, ctx.urgency, ctx.summary, event_id)
        ctx.trace.append({"step": "Dispatch", "detail": f"Paged {len(dispatch.sent_to)} staff",
                          "source": "pager", "t_ms": int((time.time() - start) * 1000)})

        warnings = []
        if ctx.protocol:
            have: dict[str, int] = {}
            for s in ctx.staff_list:
                have[s.role] = have.get(s.role, 0) + 1
            missing = [f"{need - have.get(role, 0)} {role.replace('_', ' ')}"
                       for role, need in ctx.protocol.staff_minimum.items() if have.get(role, 0) < need]
            if missing:
                warnings.append(f"Protocol {ctx.protocol.code} full team still needs: {', '.join(missing)}")
        if not ctx.staff_list:
            warnings.insert(0, "No free staff for this role — escalate to the duty manager")
        if cap_note:
            warnings.append(cap_note)

        response_ms = int((time.time() - start) * 1000)
        log_crisis_event(
            transcript=transcript, crisis_type=ctx.crisis_type, location=ctx.location,
            urgency=ctx.urgency, staff_type=ctx.staff_type, count_requested=ctx.count,
            protocol_matched=ctx.protocol.code if ctx.protocol else "GEN-00",
            staff_dispatched=[s.to_dict() for s in ctx.staff_list], fcm_sent=dispatch.success,
            response_ms=response_ms, event_id=event_id,
            extra={"engine": ctx.engine, "summary": ctx.summary, "follow_up": ctx.follow_up},
        )

        # Second opinion from Nemotron Ultra, after the response so paging is never delayed
        review_status = start_review(event_id, within_budget=not review_enabled() or review_limiter.allow("all"))
        if review_status == "pending":
            event = {"event_id": event_id, "crisis_type": ctx.crisis_type, "location": ctx.location,
                     "urgency": ctx.urgency, "summary": ctx.summary, "transcript": transcript,
                     "follow_up": ctx.follow_up}
            situation = build_situation(event, ctx.protocol, [s.public_dict() for s in ctx.staff_list], warnings,
                                        roster(), [e for e in recent_events(200) if e["status"] == "active"])
            background.add_task(complete_review, event_id, situation)

        return CrisisResponse(
            event_id=event_id, status="dispatched", crisis_type=ctx.crisis_type, location=ctx.location,
            urgency=ctx.urgency, summary=ctx.summary,
            protocol={
                "name": ctx.protocol.name if ctx.protocol else "General",
                "code": ctx.protocol.code if ctx.protocol else "GEN-00",
                "steps": ctx.protocol.steps if ctx.protocol else [],
            },
            staff_dispatched=[StaffInfo(**s.public_dict()) for s in ctx.staff_list],
            fcm_sent=dispatch.success, dispatch_mode=dispatch.mode, response_ms=response_ms,
            engine=ctx.engine, follow_up=ctx.follow_up, reasoning=ctx.reasoning,
            warnings=warnings, trace=ctx.trace, review=review_status,
        )
    except Exception as e:
        logger.exception("Pipeline failed")
        # Details stay in the server log; callers get a plain message, not internals
        raise HTTPException(status_code=500, detail="Dispatch failed on the server") from e


@app.get("/staff")
async def list_staff(role: Optional[str] = None):
    staff = roster(role)
    return {"staff": staff, "count": len(staff)}


@app.get("/staff/{staff_id}/inbox")
async def staff_inbox(staff_id: str):
    return {"staff_id": staff_id, "alerts": inbox(staff_id)}


@app.get("/events")
async def events(limit: int = 20):
    return {"events": recent_events(limit)}


@app.get("/events/{event_id}/review")
async def event_review(event_id: str):
    """Nemotron Ultra's second opinion: status pending | done | failed | off."""
    r = get_review(event_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Unknown event")
    return {"event_id": event_id, **r}


@app.post("/events/{event_id}/resolve")
async def resolve(event_id: str):
    freed = release_event(event_id)
    if not mark_resolved(event_id) and not freed:
        raise HTTPException(status_code=404, detail="Unknown event")
    return {"event_id": event_id, "status": "resolved", "staff_freed": freed}


@app.post("/reset")
async def reset(x_reset_token: Optional[str] = Header(default=None)):
    """Reset the demo: everyone available, no events, empty pagers.

    Open by default so the dashboard's "Reset demo" button works. Set RESET_TOKEN to lock it.
    """
    if RESET_TOKEN and not secrets.compare_digest(x_reset_token or "", RESET_TOKEN):
        raise HTTPException(status_code=403, detail="Reset is locked on this server")
    reset_availability()
    clear_events()
    clear_inboxes()
    clear_reviews()
    return {"status": "reset"}


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
