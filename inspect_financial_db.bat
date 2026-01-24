@echo off
set DB_FILE=example_sprout_apps\financial\financial.db

echo Inspecting %DB_FILE%...
echo.
echo == Table List ==
sqlite3 %DB_FILE% ".tables"
echo.
echo == Recent Stock Entries (Last 5) ==
sqlite3 %DB_FILE% -header -column "SELECT symbol, price, datetime(timestamp, 'unixepoch', 'localtime') as time FROM StockTicker ORDER BY timestamp DESC LIMIT 5;"
echo.
pause
