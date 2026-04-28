"""
cloud_sql_staff.py — Cloud SQL (PostgreSQL) staff schedule queries
Uses Cloud SQL Python Connector with pg8000 for serverless connections.
Falls back gracefully when credentials/instance unavailable.
"""
import os
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Cloud SQL configuration ─────────────────────────────────
CLOUDSQL_INSTANCE = os.getenv("CLOUDSQL_INSTANCE", "")  # e.g. "project:region:instance"
CLOUDSQL_DB = os.getenv("CLOUDSQL_DB", "crisis_response")
CLOUDSQL_USER = os.getenv("CLOUDSQL_USER", "crisis_admin")
CLOUDSQL_PASSWORD = os.getenv("CLOUDSQL_PASSWORD", "")

# Re-use the StaffMember dataclass from staff_finder
from staff_finder import StaffMember


def is_cloudsql_configured() -> bool:
    """Check if Cloud SQL credentials are available."""
    return bool(CLOUDSQL_INSTANCE and CLOUDSQL_PASSWORD)


def _get_connection():
    """
    Create a Cloud SQL connection using the Cloud SQL Python Connector.
    This handles IAM auth and SSL automatically on Cloud Run.
    """
    from google.cloud.sql.connector import Connector

    connector = Connector()
    conn = connector.connect(
        CLOUDSQL_INSTANCE,
        "pg8000",
        user=CLOUDSQL_USER,
        password=CLOUDSQL_PASSWORD,
        db=CLOUDSQL_DB,
    )
    return conn


def find_staff_cloudsql(staff_type: str, count: int) -> list[StaffMember]:
    """
    Query Cloud SQL PostgreSQL for on-shift staff matching the required role.
    Returns a list of StaffMember objects.

    Cloud SQL is used for real-time transactional staff data (shift check-ins,
    live availability updates) while BigQuery handles analytics and audit logs.
    """
    if not is_cloudsql_configured():
        raise RuntimeError("Cloud SQL not configured — CLOUDSQL_INSTANCE or CLOUDSQL_PASSWORD missing")

    conn = None
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)

        cursor.execute(
            """
            SELECT staff_id, name, role, department, fcm_token
            FROM staff_schedules
            WHERE on_shift = TRUE
              AND role = %s
              AND shift_start <= %s
              AND shift_end >= %s
              AND fcm_token IS NOT NULL
            ORDER BY shift_start ASC
            LIMIT %s
            """,
            (staff_type, now, now, count),
        )

        rows = cursor.fetchall()
        staff = [
            StaffMember(
                staff_id=row[0],
                name=row[1],
                role=row[2],
                department=row[3],
                fcm_token=row[4],
            )
            for row in rows
        ]

        if not staff:
            logger.warning(f"No on-shift {staff_type} in Cloud SQL, broadening to any role")
            cursor.execute(
                """
                SELECT staff_id, name, role, department, fcm_token
                FROM staff_schedules
                WHERE on_shift = TRUE
                  AND shift_start <= %s
                  AND shift_end >= %s
                  AND fcm_token IS NOT NULL
                ORDER BY shift_start ASC
                LIMIT %s
                """,
                (now, now, count),
            )
            rows = cursor.fetchall()
            staff = [
                StaffMember(
                    staff_id=row[0],
                    name=row[1],
                    role=row[2],
                    department=row[3],
                    fcm_token=row[4],
                )
                for row in rows
            ]

        logger.info(f"Cloud SQL returned {len(staff)} staff for role={staff_type}")
        return staff

    except Exception as e:
        logger.error(f"Cloud SQL query failed: {e}")
        raise
    finally:
        if conn:
            conn.close()
