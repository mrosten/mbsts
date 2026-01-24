@echo off
set PYTHONPATH=%PYTHONPATH%;%~dp0
python -m example_sprout_apps.mailsync.main --run_app
