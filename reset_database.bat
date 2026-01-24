@echo off
echo.
echo ========================================
echo   RESET TWEET DATABASE
echo ========================================
echo.
echo This will DELETE all tweets!
echo You can run backfill_tweets.bat after
echo to get fresh, clean data.
echo.
pause

python reset_database.py

pause
