-- ============================================================
-- BigQuery Schema: Rapid Crisis Response
-- Project: serene-bastion-494715-f2
-- Dataset: crisis_response
-- ============================================================

-- Run this in BigQuery console or via bq CLI:
-- bq mk --dataset serene-bastion-494715-f2:crisis_response

-- ────────────────────────────────────────────────────────────
-- Table 1: Staff Schedules
-- Tracks on-shift staff and their FCM tokens for dispatch
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `serene-bastion-494715-f2.crisis_response.staff_schedules` (
  staff_id      STRING    NOT NULL,
  name          STRING    NOT NULL,
  role          STRING    NOT NULL,   -- e.g. "trauma_surgeon", "nurse", "icu_doctor"
  department    STRING,               -- e.g. "ER", "ICU", "OR"
  shift_start   TIMESTAMP NOT NULL,
  shift_end     TIMESTAMP NOT NULL,
  fcm_token     STRING,               -- Firebase Cloud Messaging device token
  on_shift      BOOL      NOT NULL DEFAULT TRUE,
  phone         STRING,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
OPTIONS (
  description = "Staff availability and FCM tokens for crisis dispatch"
);

-- ────────────────────────────────────────────────────────────
-- Table 2: Crisis Event Log
-- High-reliability audit log of every crisis handled
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `serene-bastion-494715-f2.crisis_response.crisis_log` (
  event_id        STRING    NOT NULL,   -- UUID
  timestamp       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  transcript      STRING    NOT NULL,   -- Raw STT output
  crisis_type     STRING,               -- e.g. "trauma", "cardiac_arrest", "fire"
  location        STRING,               -- e.g. "Bay 4", "Floor 3"
  urgency         STRING,               -- "critical" | "high" | "medium"
  staff_type      STRING,               -- Role requested
  count_requested INT64,                -- How many staff needed
  protocol_matched STRING,              -- Protocol name from Vertex AI
  staff_dispatched JSON,                -- Array of {staff_id, name, role}
  fcm_sent        BOOL,
  response_ms     INT64,                -- End-to-end latency in ms
  error           STRING                -- Any error message
)
OPTIONS (
  description = "Audit log of all crisis coordination events"
);

-- ────────────────────────────────────────────────────────────
-- Sample seed data for staff_schedules (for demo/testing)
-- ────────────────────────────────────────────────────────────
INSERT INTO `serene-bastion-494715-f2.crisis_response.staff_schedules`
  (staff_id, name, role, department, shift_start, shift_end, fcm_token, on_shift)
VALUES
  ('S001', 'Dr. Arjun Mehta',     'trauma_surgeon', 'ER',  TIMESTAMP('2026-04-25 06:00:00'), TIMESTAMP('2026-04-25 18:00:00'), 'FCM_TOKEN_S001', TRUE),
  ('S002', 'Dr. Priya Sharma',    'trauma_surgeon', 'OR',  TIMESTAMP('2026-04-25 06:00:00'), TIMESTAMP('2026-04-25 18:00:00'), 'FCM_TOKEN_S002', TRUE),
  ('S003', 'Dr. Ravi Kumar',      'cardiologist',   'ICU', TIMESTAMP('2026-04-25 07:00:00'), TIMESTAMP('2026-04-25 19:00:00'), 'FCM_TOKEN_S003', TRUE),
  ('S004', 'Nurse Lakshmi Nair',  'nurse',          'ER',  TIMESTAMP('2026-04-25 06:00:00'), TIMESTAMP('2026-04-25 14:00:00'), 'FCM_TOKEN_S004', TRUE),
  ('S005', 'Nurse Deepa Rao',     'nurse',          'ICU', TIMESTAMP('2026-04-25 06:00:00'), TIMESTAMP('2026-04-25 14:00:00'), 'FCM_TOKEN_S005', TRUE),
  ('S006', 'Dr. Suresh Iyer',     'anesthesiologist','OR', TIMESTAMP('2026-04-25 08:00:00'), TIMESTAMP('2026-04-25 20:00:00'), 'FCM_TOKEN_S006', TRUE),
  ('S007', 'Dr. Meena Pillai',    'icu_doctor',     'ICU', TIMESTAMP('2026-04-25 06:00:00'), TIMESTAMP('2026-04-25 18:00:00'), 'FCM_TOKEN_S007', TRUE),
  ('S008', 'Paramedic Arun Das',  'paramedic',      'ER',  TIMESTAMP('2026-04-25 06:00:00'), TIMESTAMP('2026-04-25 18:00:00'), 'FCM_TOKEN_S008', TRUE);
