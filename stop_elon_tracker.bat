@echo off
echo Stopping Elon Tweet Tracker...

REM Kill all python.exe processes running elon tracker
taskkill /FI "WINDOWTITLE eq *elon*" /F /T 2>nul

echo Elon Tweet Tracker stopped.
echo Check logs\elon_tracker.log for final output.
pause
