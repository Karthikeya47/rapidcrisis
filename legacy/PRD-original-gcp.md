# PRD: Rapid Crisis Response

## GOAL
Stop delay. Save time.
Agent hear voice. Agent find staff. Agent send alert.

## CONSTRAINTS
Google tools strictly.

## STACK
GCP.
App: Flutter.
Speech: Cloud STT v2 stream.
Brain: Gemini 1.5 Flash.
Retrieval: Vertex AI Vector Search.
Database: BigQuery. Cloud SQL.
Execute: Cloud Run.
Message: FCM.

## LOGIC PIPELINE
INPUT: App record voice. "Need two trauma surgeons, Bay 4".
TRANSCRIBE: STT convert voice. Output text.
THINK: Gemini parse text. Extract type. Extract urgency.
FIND PROTOCOL: Read Vertex AI. Get protocol.
FIND STAFF: Query BigQuery/Cloud SQL. Get schedules.
DECIDE: Agent match crisis. Match available staff.
DISPATCH: Cloud Run trigger FCM.
OUTPUT: FCM push notification. Phone ring. 
LOG: BigQuery write log.

## DEPLOYMENT
Target: Google Antigravity.
Architecture: Serverless. Decentralize data. High-reliability log.
