# Turbindo (Sprout Framework)

## What is this?
**Turbindo** is the home of **Sprout**, a software engine designed to act as a personal digital assistant or automation robot.

Imagine you have a team of helpers who can do different tasks for you at the same time—like checking your email, organizing your files, and listening for messages—without getting tired or waiting for one task to finish before starting another. That is what Sprout does for computer programs.

It is a "framework," which means it provides the building blocks for developers to create these kinds of smart, multi-tasking applications easily.

## What can it do?
Included in this project are a few examples of what this engine can build:

1.  **Email Synchronizer ("Mailsync")**: A tool designed to automatically connect to your email accounts and keep them updated or organized in the background.
2.  **Bitcoin Tracker ("Financial")**: Monitors Bitcoin prices in real-time and saves them to a database.
3.  **Elon Tweet Tracker**: Tracks tweets from Elon Musk and saves them to a database.
4.  **Gmail Inbox Tracker**: Monitors your Gmail inbox statistics, unread count, and top senders.
5.  **Hello World**: A simple "test drive" application that demonstrates the engine is running correctly by recording basic information.

## For Developers (Technical Details)
The section below contains the technical specifications for programmers who want to work on or extend the project.

### Technical Overview
Sprout is an **asynchronous Python framework** built on `asyncio`. It is designed for I/O-bound applications that need to handle high concurrency (doing many things at once).

### Project Structure
- **sprout/**: The core framework code (the "engine").
- **example_sprout_apps/**: Demo applications.
  - **financial/**: Bitcoin price tracker.
  - **elon_tweet_tracker/**: Elon Musk tweet tracker.
  - **gmail_tracker/**: Gmail inbox statistics tracker.
  - **mailsync/**: Email sync tool.
  - **hello_world/**: Basic demo.

### Restoration Notes
This project was recently restored from a damaged state. Several missing parts of the engine (like the database connector and logging system) were reconstructed.

### Setup for Elon Tweet Tracker

**One-time setup required**: The tweet tracker needs you to login to Twitter once:

1. Run **`login_twitter_manual.bat`**
2. A Chrome window will open
3. Login to Twitter with your credentials
4. Navigate to @elonmusk to verify you see tweets
5. Close the terminal when done

Your login session will be saved and the tracker will use it automatically!

### How to Run It
Run the example applications using the provided scripts:
- `run_hello_world.bat` - Simple test app
- `run_financial.bat` - Tracks BTC price every 20 seconds
- `run_elon_tracker.bat` - Checks for new tweets every 30 seconds
- `run_gmail_tracker.bat` - Tracks Gmail inbox stats every 5 minutes (**Requires OAuth setup - see GMAIL_SETUP.md**)

**The apps run in minimized windows** - they won't block your terminal! You'll see a minimized window in your taskbar, and all output goes to log files.

### Viewing Logs
Since the apps run in the background, check their output in log files:
- **`view_logs.bat`** - Interactive menu to view all logs
- Or check the `logs/` folder directly:
  - `logs/financial.log` - Bitcoin tracker output
  - `logs/elon_tracker.log` - Tweet tracker output
  - `logs/gmail_tracker.log` - Gmail tracker output

### Stopping Applications
To stop running trackers:
- `stop_financial.bat` - Stop the Bitcoin tracker
- `stop_elon_tracker.bat` - Stop the Elon tweet tracker  
- `stop_gmail_tracker.bat` - Stop the Gmail tracker
- `stop_all.bat` - Stop all running trackers

### Managing Data
To manually examine the database (e.g., to see saved prices or tweets), use the helper scripts:
- `inspect_financial_db.bat` - View latest BTC prices with readable timestamps
- `inspect_tweets.bat` - View latest tweets
- `inspect_gmail.bat` - View Gmail inbox statistics (CLI)
- `inspect_gmail_gui.bat` - View Gmail statistics **(GUI Window)**

Or run SQLite commands directly:
```bash
sqlite3 example_sprout_apps/financial/financial.db "SELECT * FROM StockTicker;"
```
