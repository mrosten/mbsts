# Gmail API Setup Instructions

## Step 1: Install Dependencies

Run this command:
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

## Step 2: Get Gmail API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Gmail API**:
   - Click "Enable APIs and Services"
   - Search for "Gmail API"
   - Click Enable

## Step 3: Configure OAuth Consent Screen ⚠️ CRITICAL

**You MUST do this before creating credentials!**

1. Go to "OAuth consent screen" in the left menu
2. Choose **"External"** user type (click Configure)
3. Fill in the App information:
   - **App name**: "Gmail Tracker"
   - **User support email**: Your email address
   - **Developer contact**: Your email address
4. Click "Save and Continue" through Scopes (leave empty)
5. Click "Save and Continue" through Optional info

6. **ADD TEST USERS** (This is why you got Error 403!):
   - Click "+ ADD USERS"
   - Enter YOUR email address (the Gmail you want to track)
   - Click "Add"
   - Click "Save and Continue"

## Step 4: Create Credentials

1. Go to "Credentials" in left menu
2. Click "Create Credentials" → "OAuth client ID"
3. Application type: **Desktop app**
4. Name it: "Gmail Tracker"
5. Click Create
   
6. Download the credentials:
   - Click the download button (⬇️) next to your new OAuth client
   - Save the file as `credentials.json`
   - Place it in: `example_sprout_apps/gmail_tracker/credentials.json`

## Step 5: First Run (One-Time Setup)

Run: `.\run_gmail_tracker.bat`

- A browser will open automatically
- Log into your Gmail account (the one you added as test user!)
- Click "Go to Gmail Tracker (unsafe)" - it's safe, it's your app!
- Click "Allow" to grant access
- The credentials are saved (won't ask again)

## Step 6: View Your Stats

Run: `.\inspect_gmail.bat`

## What It Tracks

- **Total messages** in your account
- **Inbox count** 
- **Unread count**
- **Starred messages**
- **Top 10 senders** (from last 50 inbox messages)

All data is **local** and **private** - nothing is sent anywhere!

## Files Created

- `token.pickle` - Your saved login (don't share this!)
- `gmail.db` - Database with your stats
- `logs/gmail_tracker.log` - Activity log
