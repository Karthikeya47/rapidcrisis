"""
dispatcher.py — deliver crisis alerts to staff.

Alerts go to an in-app pager inbox per staff member; the web dashboard's
"staff phones" panel polls it, so the demo shows phones lighting up live.
A real deployment would plug a push/SMS provider into `_deliver`.
"""
import logging
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_inbox: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))


@dataclass
class DispatchResult:
    success: bool
    sent_to: list[str]  # staff_ids
    failed: list[str]
    mode: str           # "in_app"


def _build_notification_data(crisis_type: str, location: str, urgency: str, summary: str) -> dict:
    urgency_emoji = {"critical": "🚨", "high": "⚠️", "medium": "📢"}.get(urgency, "📢")
    return {
        "crisis_type": crisis_type,
        "location": location,
        "urgency": urgency,
        "summary": summary,
        "title": f"{urgency_emoji} CRISIS ALERT — {crisis_type.replace('_', ' ').upper()}",
        "body": f"{summary} | Location: {location}",
    }


def dispatch_alerts(staff_list: list, crisis_type: str, location: str, urgency: str,
                    summary: str, event_id: str = None) -> DispatchResult:
    return _mock_dispatch(staff_list, crisis_type, location, urgency, summary, event_id)


def _mock_dispatch(staff_list, crisis_type, location, urgency, summary, event_id=None) -> DispatchResult:
    notif = _build_notification_data(crisis_type, location, urgency, summary)
    notif["event_id"] = event_id
    notif["sent_at"] = datetime.now(timezone.utc).isoformat()
    sent_to = []
    with _lock:
        for staff in staff_list:
            _inbox[staff.staff_id].appendleft(dict(notif))
            logger.info(f"[PAGER] → {staff.name} ({staff.role}) | {notif['title']} | {notif['body']}")
            sent_to.append(staff.staff_id)
    return DispatchResult(success=True, sent_to=sent_to, failed=[], mode="in_app")


def inbox(staff_id: str) -> list[dict]:
    with _lock:
        return list(_inbox.get(staff_id, []))


def clear_inboxes():
    with _lock:
        _inbox.clear()
