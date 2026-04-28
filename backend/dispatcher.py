"""
dispatcher.py — Send FCM push notifications to dispatched staff
Uses firebase-admin SDK; mock mode logs to stdout when credentials unavailable.
"""
import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS", "")


@dataclass
class DispatchResult:
    success: bool
    sent_to: list[str]  # List of staff_ids
    failed: list[str]
    mode: str  # "fcm" or "mock"


def dispatch_alerts(
    staff_list: list,
    crisis_type: str,
    location: str,
    urgency: str,
    summary: str,
) -> DispatchResult:
    """
    Send FCM push notifications to all matched staff.
    """
    if FIREBASE_CREDENTIALS_PATH and os.path.exists(FIREBASE_CREDENTIALS_PATH):
        return _fcm_dispatch(staff_list, crisis_type, location, urgency, summary)
    else:
        return _mock_dispatch(staff_list, crisis_type, location, urgency, summary)


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


def _fcm_dispatch(staff_list, crisis_type, location, urgency, summary) -> DispatchResult:
    import firebase_admin
    from firebase_admin import credentials, messaging

    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)

    notif_data = _build_notification_data(crisis_type, location, urgency, summary)
    sent_to = []
    failed = []

    for staff in staff_list:
        if not staff.fcm_token or staff.fcm_token.startswith("mock_"):
            logger.warning(f"Skipping mock FCM token for {staff.name}")
            failed.append(staff.staff_id)
            continue
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=notif_data["title"],
                    body=notif_data["body"],
                ),
                data={
                    "crisis_type": crisis_type,
                    "location": location,
                    "urgency": urgency,
                },
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        sound="crisis_alert",
                        channel_id="crisis_dispatch",
                        priority="max",
                        visibility="public",
                    ),
                ),
                token=staff.fcm_token,
            )
            messaging.send(message)
            sent_to.append(staff.staff_id)
            logger.info(f"FCM sent to {staff.name} ({staff.staff_id})")
        except Exception as e:
            logger.error(f"FCM failed for {staff.name}: {e}")
            failed.append(staff.staff_id)

    return DispatchResult(
        success=len(sent_to) > 0,
        sent_to=sent_to,
        failed=failed,
        mode="fcm",
    )


def _mock_dispatch(staff_list, crisis_type, location, urgency, summary) -> DispatchResult:
    """Log-based mock when Firebase credentials are not configured."""
    notif_data = _build_notification_data(crisis_type, location, urgency, summary)
    sent_to = []

    for staff in staff_list:
        logger.info(
            f"[MOCK FCM] → {staff.name} ({staff.role}) | "
            f"Title: {notif_data['title']} | Body: {notif_data['body']}"
        )
        sent_to.append(staff.staff_id)

    return DispatchResult(
        success=True,
        sent_to=sent_to,
        failed=[],
        mode="mock",
    )
