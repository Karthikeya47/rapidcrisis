"""
logger.py — BigQuery audit log writer
Writes every crisis event to crisis_log table with full pipeline trace.
"""
import os
import uuid
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

GCP_PROJECT = os.getenv("GCP_PROJECT", "project-e82fa8f3-3868-42a9-a35")
BQ_DATASET = os.getenv("BQ_DATASET", "crisis_response")
BQ_LOG_TABLE = "crisis_log"


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
) -> str:
    """
    Write a crisis event row to BigQuery crisis_log table.
    Returns the event_id (UUID) for tracking.
    Falls back to local logging if BigQuery is unavailable.
    """
    event_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    row = {
        "event_id": event_id,
        "timestamp": timestamp,
        "transcript": transcript,
        "crisis_type": crisis_type,
        "location": location,
        "urgency": urgency,
        "staff_type": staff_type,
        "count_requested": count_requested,
        "protocol_matched": protocol_matched,
        "staff_dispatched": staff_dispatched,
        "fcm_sent": fcm_sent,
        "response_ms": response_ms,
        "error": error,
    }

    try:
        _bigquery_insert(row)
    except Exception as e:
        logger.warning(f"BigQuery log failed, logging locally: {e}")
        logger.info(f"[CRISIS LOG] {row}")

    return event_id


def _bigquery_insert(row: dict):
    import json
    from google.cloud import bigquery

    client = bigquery.Client(project=GCP_PROJECT)
    table_ref = f"{GCP_PROJECT}.{BQ_DATASET}.{BQ_LOG_TABLE}"

    # BigQuery requires JSON column as string
    bq_row = dict(row)
    bq_row["staff_dispatched"] = json.dumps(bq_row["staff_dispatched"])

    errors = client.insert_rows_json(table_ref, [bq_row])
    if errors:
        raise RuntimeError(f"BigQuery insert errors: {errors}")
    logger.info(f"Crisis event logged to BigQuery: {row['event_id']}")
