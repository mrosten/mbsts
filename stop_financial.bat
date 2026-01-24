@echo off
echo Stopping Financial Tracker...

REM Kill all python.exe processes running financial app
taskkill /FI "WINDOWTITLE eq *financial*" /F /T 2>nul

REM Alternative: kill by image name if window title doesn't work
taskkill /FI "IMAGENAME eq python.exe" /FI "MEMUSAGE gt 1000" /F 2>nul

echo Financial Tracker stopped.
echo Check logs\financial.log for final output.
pause
