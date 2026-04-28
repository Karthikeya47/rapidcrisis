-- ============================================================
-- Cloud SQL (PostgreSQL) Schema: Rapid Crisis Response
-- Project: project-e82fa8f3-3868-42a9-a35
-- Database: crisis_response
-- ============================================================
--
-- Setup:
--   1. Create a Cloud SQL PostgreSQL instance:
--      gcloud sql instances create crisis-db \
--        --database-version=POSTGRES_15 \
--        --tier=db-f1-micro \
--        --region=us-central1 \
--        --project=project-e82fa8f3-3868-42a9-a35
--
--   2. Create database:
--      gcloud sql databases create crisis_response \
--        --instance=crisis-db
--
--   3. Create user:
--      gcloud sql users create crisis_admin \
--        --instance=crisis-db \
--        --password=YOUR_SECURE_PASSWORD
--
--   4. Connect and run this schema:
--      gcloud sql connect crisis-db --user=crisis_admin --database=crisis_response
-- ============================================================

-- ────────────────────────────────────────────────────────────
-- Table: Staff Schedules (real-time transactional data)
-- Cloud SQL handles live shift check-ins, availability toggles,
-- and FCM token updates. BigQuery mirrors this for analytics.
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS staff_schedules (
    staff_id      VARCHAR(32)   PRIMARY KEY,
    name          VARCHAR(128)  NOT NULL,
    role          VARCHAR(64)   NOT NULL,
    department    VARCHAR(64),
    shift_start   TIMESTAMPTZ   NOT NULL,
    shift_end     TIMESTAMPTZ   NOT NULL,
    fcm_token     VARCHAR(256),
    on_shift      BOOLEAN       NOT NULL DEFAULT TRUE,
    phone         VARCHAR(20),
    created_at    TIMESTAMPTZ   DEFAULT NOW(),
    updated_at    TIMESTAMPTZ   DEFAULT NOW()
);

-- Index for the primary query pattern: find on-shift staff by role
CREATE INDEX IF NOT EXISTS idx_staff_role_shift
    ON staff_schedules (role, on_shift, shift_start, shift_end);

-- Index for department-based lookups
CREATE INDEX IF NOT EXISTS idx_staff_department
    ON staff_schedules (department, on_shift);

-- ────────────────────────────────────────────────────────────
-- Table: Staff Check-Ins (real-time availability tracking)
-- Tracks when staff clock in/out; used by the dispatch engine
-- to confirm availability before sending FCM alerts.
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS staff_checkins (
    checkin_id    SERIAL        PRIMARY KEY,
    staff_id      VARCHAR(32)   NOT NULL REFERENCES staff_schedules(staff_id),
    action        VARCHAR(16)   NOT NULL CHECK (action IN ('check_in', 'check_out', 'break', 'return')),
    timestamp     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    location      VARCHAR(128),
    notes         TEXT
);

CREATE INDEX IF NOT EXISTS idx_checkins_staff_time
    ON staff_checkins (staff_id, timestamp DESC);

-- ────────────────────────────────────────────────────────────
-- Trigger: Auto-update updated_at on staff_schedules
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_staff_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_staff_updated
    BEFORE UPDATE ON staff_schedules
    FOR EACH ROW
    EXECUTE FUNCTION update_staff_timestamp();

-- ────────────────────────────────────────────────────────────
-- Seed data (matches BigQuery seed for consistency)
-- ────────────────────────────────────────────────────────────
INSERT INTO staff_schedules (staff_id, name, role, department, shift_start, shift_end, fcm_token, on_shift)
VALUES
    ('S001', 'Dr. Arjun Mehta',     'trauma_surgeon',    'ER',  '2026-04-25 06:00:00+00', '2026-04-25 18:00:00+00', 'FCM_TOKEN_S001', TRUE),
    ('S002', 'Dr. Priya Sharma',    'trauma_surgeon',    'OR',  '2026-04-25 06:00:00+00', '2026-04-25 18:00:00+00', 'FCM_TOKEN_S002', TRUE),
    ('S003', 'Dr. Ravi Kumar',      'cardiologist',      'ICU', '2026-04-25 07:00:00+00', '2026-04-25 19:00:00+00', 'FCM_TOKEN_S003', TRUE),
    ('S004', 'Nurse Lakshmi Nair',  'nurse',             'ER',  '2026-04-25 06:00:00+00', '2026-04-25 14:00:00+00', 'FCM_TOKEN_S004', TRUE),
    ('S005', 'Nurse Deepa Rao',     'nurse',             'ICU', '2026-04-25 06:00:00+00', '2026-04-25 14:00:00+00', 'FCM_TOKEN_S005', TRUE),
    ('S006', 'Dr. Suresh Iyer',     'anesthesiologist',  'OR',  '2026-04-25 08:00:00+00', '2026-04-25 20:00:00+00', 'FCM_TOKEN_S006', TRUE),
    ('S007', 'Dr. Meena Pillai',    'icu_doctor',        'ICU', '2026-04-25 06:00:00+00', '2026-04-25 18:00:00+00', 'FCM_TOKEN_S007', TRUE),
    ('S008', 'Paramedic Arun Das',  'paramedic',         'ER',  '2026-04-25 06:00:00+00', '2026-04-25 18:00:00+00', 'FCM_TOKEN_S008', TRUE)
ON CONFLICT (staff_id) DO NOTHING;
