@echo off
set PYTHONPATH=%PYTHONPATH%;%~dp0
call .venv\Scripts\activate

start /MIN cmd /c "python -u -m example_sprout_apps.polytrading.main --run_app > logs\polytrading.log 2>&1"

echo Polytrading App started in background. Logs: logs\polytrading.log
