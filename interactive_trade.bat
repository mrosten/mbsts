@echo off
set "url=%~1"

if "%url%"=="" (
    set /p url="Enter Polymarket URL: "
)

echo.
echo Starting Interactive Trader...
python interactive_trade.py --url "%url%"

pause


