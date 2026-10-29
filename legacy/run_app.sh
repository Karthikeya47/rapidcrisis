#!/bin/bash
# ============================================================
# run_app.sh — Run the Flutter app with secrets injected
# The API key is read from app/.env, NEVER from source code.
# ============================================================

# Load GOOGLE_API_KEY from app/.env
if [ -f "app/.env" ]; then
  export $(grep -v '^#' app/.env | xargs)
else
  echo "[ERROR] app/.env not found."
  echo "Please create it from app/.env.example and add your API key."
  exit 1
fi

if [ -z "$GOOGLE_API_KEY" ]; then
  echo "[ERROR] GOOGLE_API_KEY is empty in app/.env"
  exit 1
fi

echo "[INFO] Launching Flutter app with API key injected via --dart-define..."
cd app && flutter run --dart-define=GOOGLE_API_KEY="$GOOGLE_API_KEY"
