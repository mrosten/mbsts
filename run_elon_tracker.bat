@echo off
echo Starting Elon Tweet Tracker in background...
set PYTHONPATH=%PYTHONPATH%;%~dp0

REM Force UTF-8 encoding for Python output
set PYTHONIOENCODING=utf-8

REM Run in background with window hidden, unbuffered output to log
start /MIN cmd /c "python -u -m example_sprout_apps.elon_tweet_tracker.main --run_app > logs\elon_tracker.log 2>&1"

REM Give it a moment to start
timeout /t 2 /nobreak >nul

echo Elon Tweet Tracker started in background!
echo - Output: logs\elon_tracker.log
echo - Stop: stop_elon_tracker.bat
echo - Data: inspect_tweets.bat
echo.
echo The tracker is running in a minimized window. Check the taskbar.
