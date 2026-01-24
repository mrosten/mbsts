@echo off
echo Stopping Gmail Tracker...
taskkill /FI "WINDOWTITLE eq *gmail_tracker*" /F >nul 2>&1
echo Gmail Tracker stopped.
echo Check logs\gmail_tracker.log for final output.
pause
