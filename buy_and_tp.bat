@echo off
set "url=%~1"

if "%url%"=="" (
    set /p url="Enter Polymarket URL: "
)

set /p outcome="Outcome (up/down): "
set /p shares="Number of shares (default 5): "
if "%shares%"=="" set "shares=5"

set /p buy_p="Buy limit price (default 0.99 for market): "
if "%buy_p%"=="" set "buy_p=0.99"

set /p tp_p="Take PROFIT sell price (e.g. 0.95): "
if "%tp_p%"=="" (
    echo Error: Take Profit price is required.
    pause
    exit /b
)

echo.
echo Preparing Sniper Execution:
echo URL:    %url%
echo Action: BUY %shares% shares of %outcome% @ %buy_p%
echo Goal:   SET TP @ %tp_p%
echo.

python buy_and_tp.py --url "%url%" --outcome %outcome% --shares %shares% --buy_price %buy_p% --tp_price %tp_p%

echo.
echo Operation complete.
pause
