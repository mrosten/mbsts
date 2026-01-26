@echo off
set "url=%~1"

if "%url%"=="" (
    set /p url="Enter Polymarket URL to enquire: "
)

if "%url%"=="" (
    echo Error: URL is required.
    pause
    exit /b
)

python poly_enquiry.py --url "%url%"

echo.
if "%~1"=="" pause
