"""
Gmail API Authentication Helper
"""
import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail API scope - read-only metadata AND sending
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send'
]

def get_gmail_service():
    """
    Authenticate and return Gmail API service
    Uses OAuth 2.0 with local credential caching
    """
    creds = None
    token_path = 'example_sprout_apps/gmail_tracker/token.pickle'
    credentials_path = 'example_sprout_apps/gmail_tracker/credentials.json'
    
    # Load existing credentials
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    
    # Refresh or create new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"Please download credentials.json from Google Cloud Console and place it at:\n"
                    f"{os.path.abspath(credentials_path)}\n\n"
                    f"Instructions:\n"
                    f"1. Go to https://console.cloud.google.com/apis/credentials\n"
                    f"2. Create OAuth 2.0 Client ID (Desktop app)\n"
                    f"3. Download JSON and save as credentials.json"
                )
            
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)
