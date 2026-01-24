"""
Send Test Email Script
"""
import base64
from email.mime.text import MIMEText
from example_sprout_apps.gmail_tracker.gmail_api import get_gmail_service

def send_test_email():
    print("\n📨 Sending test email...")
    
    try:
        service = get_gmail_service()
        
        # Get user's email address
        profile = service.users().getProfile(userId='me').execute()
        user_email = profile['emailAddress']
        
        print(f"   To: {user_email}")
        
        # Create message
        message = MIMEText("This is a test email sent from your Gmail Tracker app! 🚀\n\nIf you see this, the sending functionality is working.")
        message['to'] = user_email
        message['subject'] = "Test Email from Gmail Tracker"
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        body = {'raw': raw_message}
        
        # Send
        message = service.users().messages().send(userId='me', body=body).execute()
        print(f"✅ Email sent! Message ID: {message['id']}")
        
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        print("\nNote: If you get a 403 error, you need to re-authenticate with the new scopes.")
        print("Try deleting 'example_sprout_apps/gmail_tracker/token.pickle' and running this again.")

if __name__ == "__main__":
    send_test_email()
