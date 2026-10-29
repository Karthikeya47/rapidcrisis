"""
logger.py — crisis audit log.

Every event is kept in memory for the dashboard and appended to a JSONL
file (AUDIT_LOG_PATH) so there is a durable record of who was sent where.
"""
import json
import logging
import os
import threading
import uuid
from collections import deque
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "crisis_audit.jsonl")

_lock = threading.Lock()
_events: deque = deque(maxlen=200)


def log_crisis_event(
    transcript: str,
    crisis_type: str,
    location: str,
    urgency: str,
    staff_type: str,
    count_requested: int,
    protocol_matched: str,
    staff_dispatched: list[dict],
    fcm_sent: bool,
    response_ms: int,
    error: str = None,
    event_id: str = None,
    extra: dict = None,
) -> str:
    event_id = event_id or str(uuid.uuid4())
    row = {
        "event_id": event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "transcript": transcript,
        "crisis_type": crisis_type,
        "location": location,
        "urgency": urgency,
        "staff_type": staff_type,
        "count_requested": count_requested,
        "protocol_matched": protocol_matched,
        "staff_dispatched": [{k: v for k, v in s.items() if k != "fcm_token"} for s in staff_dispatched],
        "alerts_sent": fcm_sent,
        "response_ms": response_ms,
        "error": error,
        "status": "active",
        **(extra or {}),
    }
    with _lock:
        _events.appendleft(row)
        try:
            with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
        except OSError as e:
            logger.warning(f"Audit file write failed: {e}")
    logger.info(f"[CRISIS LOG] {event_id} {crisis_type} @ {location}")
    return event_id


def recent_events(limit: int = 20) -> list[dict]:
    with _lock:
        return list(_events)[:limit]


def mark_resolved(event_id: str) -> bool:
    with _lock:
        for e in _events:
            if e["event_id"] == event_id:
                e["status"] = "resolved"
                return True
        return False


def clear_events():
    with _lock:
        _events.clear()
