@echo off
echo.
echo ========================================
echo   TWEET BACKFILL FROM JAN 20, 2026
echo ========================================
echo.
echo This will collect ALL of Elon's tweets
echo from January 20, 2026 to now.
echo.
echo Includes: posts, quotes, and retweets
echo.
echo This may take a few minutes...
echo.
pause

set PYTHONIOENCODING=utf-8
python backfill_tweets.py

echo.
echo ========================================
echo Backfill complete!
echo ========================================
echo.
echo Run inspect_tweets.bat to see results.
echo.
pause
