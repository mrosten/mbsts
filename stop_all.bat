@echo off
echo.
echo ========================================
echo   STOPPING ALL TRACKERS
echo ========================================
echo.

echo Stopping Financial Tracker...
taskkill /FI "WINDOWTITLE eq *financial*" /F >nul 2>&1

echo Stopping Elon Tweet Tracker...
taskkill /FI "WINDOWTITLE eq *elon_tracker*" /F >nul 2>&1

echo Stopping Gmail Tracker...
taskkill /FI "WINDOWTITLE eq *gmail_tracker*" /F >nul 2>&1

echo.
echo ✓ All trackers stopped
echo.
pauseck logs\ folder for output.
pause
