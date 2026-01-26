@echo on
setlocal
set PYTHONIOENCODING=utf-8

rem Use specific Project Python (Relative path to root venv)
set "PYTHON_EXE=..\.venv\Scripts\python.exe"

rem Check if it exists
if not exist "%PYTHON_EXE%" (
    echo Venv Python not found at %PYTHON_EXE%
    echo Please run this from the poly_nicegui folder.
    pause
    exit /b 1
)

rem Install/Check Requirements (using the verified python)
echo Checking dependencies...
"%PYTHON_EXE%" -m pip install nicegui requests pandas numpy python-dotenv

rem Run App
echo Starting Polymarket Turbo Trader (NiceGUI)...
cd /d "%~dp0"
"%PYTHON_EXE%" main.py
pause
