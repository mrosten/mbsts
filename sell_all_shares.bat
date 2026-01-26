@echo off
set "url=%~1"

if "%url%"=="" (
    set /p url="Enter Polymarket URL: "
)

if "%url%"=="" (
    echo Error: URL is required.
    pause
    exit /b
)

echo.
echo Scanning holdings and preparing to sell all shares for:
echo %url%
echo.

python sell_all_shares.py --url "%url%" --force

echo.
echo Process complete.
if "%~1"=="" pause
