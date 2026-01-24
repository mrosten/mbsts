@echo off
echo === Turbindo Tracker Logs ===
echo.
echo [1] Financial Tracker Log
echo [2] Elon Tweet Tracker Log
echo [3] Polytrading Log
echo [4] View all logs (tail)
echo.
choice /C 1234 /N /M "Select log to view: "

if errorlevel 4 goto viewall
if errorlevel 3 goto poly
if errorlevel 2 goto elon
if errorlevel 1 goto financial

:financial
if exist logs\financial.log (
    type logs\financial.log
) else (
    echo No financial log found. Has it been started?
)
pause
exit /b

:elon
if exist logs\elon_tracker.log (
    type logs\elon_tracker.log
) else (
    echo No elon tracker log found. Has it been started?
)
pause
exit /b

:poly
if exist logs\polytrading.log (
    type logs\polytrading.log
) else (
    echo No Polytrading log found. Has it been started?
)
pause
exit /b

:viewall
echo === Financial Log (last 10 lines) ===
if exist logs\financial.log (
    powershell -Command "Get-Content logs\financial.log -Tail 10"
) else (
    echo No financial log found.
)
echo.
echo === Elon Tracker Log (last 10 lines) ===
if exist logs\elon_tracker.log (
    powershell -Command "Get-Content logs\elon_tracker.log -Tail 10"
) else (
    echo No elon tracker log found.
)
echo.
echo === Polytrading Log (last 10 lines) ===
if exist logs\polytrading.log (
    powershell -Command "Get-Content logs\polytrading.log -Tail 10"
) else (
    echo No Polytrading log found.
)
pause
exit /b
