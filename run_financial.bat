@echo off
echo Starting Financial Tracker in background...
set PYTHONPATH=%PYTHONPATH%;%~dp0

REM Run in background with window hidden, unbuffered output to log
start /MIN cmd /c "python -u -m example_sprout_apps.financial.main --run_app > logs\financial.log 2>&1"

REM Give it a moment to start
timeout /t 2 /nobreak >nul

echo Financial Tracker started in background!
echo - Output: logs\financial.log
echo - Stop: stop_financial.bat
echo - Data: inspect_financial_db.bat
echo.
echo The tracker is running in a minimized window. Check the taskbar.
