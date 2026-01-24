@echo off
echo.
echo ========================================
echo   STARTING GMAIL INBOX TRACKER
echo ========================================
echo.

if not exist "logs" mkdir logs

set PYTHONIOENCODING=utf-8
start /MIN cmd /c "python -u example_sprout_apps/gmail_tracker/main.py > logs\gmail_tracker.log 2>&1"

echo ✓ Gmail Tracker started in background
echo.
echo View stats: inspect_gmail.bat
echo View logs:  view_logs.bat
echo Stop:       stop_gmail_tracker.bat
echo.
pause
