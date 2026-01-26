@echo off
set "url=%~1"

if "%url%"=="" (
    set /p url="Enter Polymarket URL: "
)

set /p outcome="Outcome (up/down): "
set /p sl_price="STOP LOSS Sell Price (e.g. 0.10): "

echo.
echo Starting Watcher...
python watch_and_sell.py --url "%url%" --price %sl_price% --outcome %outcome%

pause
