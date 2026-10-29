#!/bin/bash
# ============================================================
# deploy.sh — Deploy Rapid Crisis Response backend to Cloud Run
# Project: serene-bastion-494715-f2
# Region:  us-central1
# ============================================================

set -euo pipefail

PROJECT_ID="serene-bastion-494715-f2"
REGION="us-central1"
SERVICE_NAME="crisis-agent"
IMAGE="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Deploying $SERVICE_NAME to Cloud Run..."
echo "   Project: $PROJECT_ID"
echo "   Region:  $REGION"

# ── 1. Authenticate ─────────────────────────────────────────
gcloud config set project "$PROJECT_ID"

# ── 2. Enable required APIs ──────────────────────────────────
echo "Enabling GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  speech.googleapis.com \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  firebaseinstallations.googleapis.com \
  fcm.googleapis.com \
  --project "$PROJECT_ID"

# ── 3. Build & push container ────────────────────────────────
echo "Building container image..."
gcloud builds submit ../backend \
  --tag "$IMAGE" \
  --project "$PROJECT_ID"

# ── 4. Deploy to Cloud Run ───────────────────────────────────
echo "Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --timeout 30 \
  --set-env-vars "GCP_PROJECT=$PROJECT_ID,GCP_REGION=$REGION,BQ_DATASET=crisis_response" \
  --project "$PROJECT_ID"

# ── 5. Get the service URL ───────────────────────────────────
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --platform managed \
  --region "$REGION" \
  --format "value(status.url)" \
  --project "$PROJECT_ID")

echo ""
echo "✅ Deployment complete!"
echo "   Service URL: $SERVICE_URL"
echo "   Health check: $SERVICE_URL/health"
echo ""
echo "📱 Update Flutter app:"
echo "   Set BACKEND_URL=$SERVICE_URL in your build config"
echo "   Or update _backendBaseUrl in crisis_agent_service.dart"

# ── 6. Set Firebase credentials secret ──────────────────────
echo ""
echo "⚠️  Next steps:"
echo "   1. Upload Firebase service account key:"
echo "      gcloud secrets create firebase-key --data-file=./firebase-key.json"
echo "      gcloud run services update $SERVICE_NAME --set-secrets FIREBASE_CREDENTIALS=firebase-key:latest"
echo ""
echo "   2. Set Gemini API key:"
echo "      gcloud secrets create gemini-api-key --data-file=<(echo -n 'YOUR_KEY')"
echo "      gcloud run services update $SERVICE_NAME --set-secrets GOOGLE_API_KEY=gemini-api-key:latest"
echo ""
echo "   3. Run BigQuery schema:"
echo "      bq query --use_legacy_sql=false < bigquery_schema.sql"
