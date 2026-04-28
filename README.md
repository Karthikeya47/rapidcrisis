# Rapid Crisis Response 🚨

> Hospital crisis coordination system: Voice → AI → Staff Dispatch

**GCP Project**: `project-e82fa8f3-3868-42a9-a35`

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Flutter App (Android)                                      │
│  ┌─────────────┐   ┌──────────────────────────────────────┐ │
│  │ Press-to-   │──▶│ Cloud STT v2 (audio → text)          │ │
│  │ talk button │   └────────────────┬─────────────────────┘ │
│  └─────────────┘                   │                        │
└────────────────────────────────────┼────────────────────────┘
                                     │ POST /crisis
                                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Cloud Run: crisis-agent                                    │
│                                                             │
│  ① Gemini 1.5 Flash ──── parse transcript → intent JSON    │
│  ② Vertex AI Vector Search ── fetch crisis protocol        │
│  ③ BigQuery / Cloud SQL ──── find on-shift staff           │
│  ④ FCM via firebase-admin ── push to staff phones          │
│  ⑤ BigQuery ──────────────── write audit log               │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼ FCM push
         ┌─────────────────────┐
         │ Staff Android Phone │  🔔 CRISIS ALERT
         └─────────────────────┘
```

---

## Quick Start

### 1. Backend (local dev)

```bash
cd backend
pip install -r requirements.txt

# Run with mock mode (no GCP credentials needed)
uvicorn main:app --reload --port 8080

# Test the pipeline
curl -X POST http://localhost:8080/crisis \
  -H "Content-Type: application/json" \
  -d '{"transcript": "Need two trauma surgeons stat, Bay 4, patient coding"}'
```

### 2. Run tests

```bash
cd backend
pip install pytest
pytest tests/ -v
```

### 3. Flutter app

```bash
cd app

# Install Flutter: https://flutter.dev/docs/get-started/install
flutter pub get

# Run on Android emulator
flutter run

# Build APK
flutter build apk --release
```

---

## Environment Variables (backend)

| Variable | Description | Default |
|---|---|---|
| `GCP_PROJECT` | GCP project ID | `project-e82fa8f3-3868-42a9-a35` |
| `GCP_REGION` | GCP region | `us-central1` |
| `BQ_DATASET` | BigQuery dataset | `crisis_response` |
| `GOOGLE_API_KEY` | Gemini API key | *(mock if absent)* |
| `FIREBASE_CREDENTIALS` | Path to Firebase service account JSON | *(mock if absent)* |
| `VERTEX_INDEX_ENDPOINT` | Vertex AI Matching Engine endpoint | *(mock if absent)* |
| `VERTEX_DEPLOYED_INDEX_ID` | Deployed index ID | *(mock if absent)* |

---

## Deploy to Cloud Run

```bash
cd infra

# Prerequisites: gcloud CLI installed + authenticated
gcloud auth login
gcloud config set project project-e82fa8f3-3868-42a9-a35

# Deploy (enables APIs, builds, deploys)
bash deploy.sh
```

After deployment, update `_backendBaseUrl` in:
`app/lib/services/crisis_agent_service.dart`

---

## Setup Firebase (FCM)

1. Go to [Firebase Console](https://console.firebase.google.com/) → Add project → link to `project-e82fa8f3-3868-42a9-a35`
2. Android app: package `com.crisis.response.app`
3. Download `google-services.json` → place in `app/android/app/`
4. Enable Firebase Cloud Messaging
5. Download service account key → set as `FIREBASE_CREDENTIALS` secret

---

## Setup BigQuery

```bash
# Create dataset
bq mk --dataset project-e82fa8f3-3868-42a9-a35:crisis_response

# Create tables + seed demo staff
bq query --use_legacy_sql=false < infra/bigquery_schema.sql
```

---

## Setup Vertex AI (optional, for real protocol search)

```bash
cd infra
python seed_protocols.py \
  --project project-e82fa8f3-3868-42a9-a35 \
  --region us-central1 \
  --create-index
```

---

## Pipeline Flow

| Step | Component | Action |
|---|---|---|
| 1 | Flutter + Cloud STT | Record voice → transcribe to text |
| 2 | Gemini 1.5 Flash | Extract: crisis type, location, staff needed, urgency |
| 3 | Vertex AI Vector Search | Match transcript to crisis protocol |
| 4 | BigQuery | Query on-shift staff by role + shift time |
| 5 | Cloud Run → FCM | Send high-priority push to matched staff |
| 6 | BigQuery audit | Log complete event with response time |

---

## Mock Mode

The system runs fully without GCP credentials in **mock mode**:
- STT → returns rotating demo transcripts
- Gemini → rule-based keyword extraction  
- Vertex AI → keyword-matched protocol from hardcoded dict
- BigQuery → in-memory mock staff list
- FCM → logs to console instead of sending

---

## Project Structure

```
gsolutionchal/
├── .agent/PRD.md              ← Original product requirements
├── app/                       ← Flutter Android app
│   ├── lib/
│   │   ├── main.dart
│   │   ├── theme.dart
│   │   ├── models/crisis_request.dart
│   │   ├── screens/crisis_screen.dart
│   │   ├── services/
│   │   │   ├── stt_service.dart
│   │   │   ├── crisis_agent_service.dart
│   │   │   └── notification_service.dart
│   │   └── widgets/
│   │       ├── pipeline_status.dart
│   │       └── dispatch_card.dart
│   ├── android/app/src/main/AndroidManifest.xml
│   └── pubspec.yaml
├── backend/                   ← Cloud Run FastAPI backend
│   ├── main.py
│   ├── agent.py               ← Gemini 1.5 Flash
│   ├── protocol_search.py     ← Vertex AI + mock
│   ├── staff_finder.py        ← BigQuery + mock
│   ├── dispatcher.py          ← FCM
│   ├── logger.py              ← BigQuery audit log
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
│       ├── test_agent.py
│       └── test_staff_finder.py
└── infra/
    ├── bigquery_schema.sql    ← Tables + seed data
    ├── deploy.sh              ← Cloud Run deploy
    └── seed_protocols.py      ← Vertex AI seed
```
