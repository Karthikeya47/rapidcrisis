@echo off
:: ============================================================
:: run_app.bat — Run the Flutter app with secrets injected
:: The API key is read from app\.env, NEVER from source code.
:: ============================================================

:: Load GOOGLE_API_KEY from app\.env
for /f "usebackq tokens=1,2 delims==" %%A in ("app\.env") do (
    if "%%A"=="GOOGLE_API_KEY" set GOOGLE_API_KEY=%%B
)

if "%GOOGLE_API_KEY%"=="" (
    echo [ERROR] GOOGLE_API_KEY not found in app\.env
    echo Please add your key to app\.env ^(see app\.env.example^)
    exit /b 1
)

echo [INFO] Launching Flutter app with API key injected via --dart-define...
cd app
flutter run --dart-define=GOOGLE_API_KEY=%GOOGLE_API_KEY%
