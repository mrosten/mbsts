@echo off
set "url=%~1"

if "%url%"=="" (
    set /p url="Enter Polymarket URL: "
)

python analyze_btc.py --url "%url%"
pause
