"""
Gmail Inbox Tracking Job
Collects email statistics every 5 minutes
"""
import time
from collections import Counter
from example_sprout_apps.gmail_tracker.gmail_api import get_gmail_service
from example_sprout_apps.gmail_tracker.data import classes as db

async def track_inbox_stats():
    """Track Gmail inbox statistics"""
    print(f"\n[{time.strftime('%H:%M:%S')}] Collecting Gmail stats...")
    
    try:
        # Get Gmail service
        service = get_gmail_service()
        
        # Get profile info
        profile = service.users().getProfile(userId='me').execute()
        total_messages = profile.get('messagesTotal', 0)
        
        # Get label info for counts
        labels = service.users().labels().list(userId='me').execute().get('labels', [])
        
        unread_count = 0
        inbox_count = 0
        starred_count = 0
        
        for label in labels:
            if label['id'] == 'INBOX':
                inbox_count = label.get('messagesTotal', 0)
                unread_count = label.get('messagesUnread', 0)
            elif label['id'] == 'STARRED':
                starred_count = label.get('messagesTotal', 0)
        
        # Save stats
        timestamp = int(time.time())
        stats = db.EmailStats(timestamp)
        await stats.set(
            timestamp=timestamp,
            total_messages=total_messages,
            unread_count=unread_count,
            inbox_count=inbox_count,
            starred_count=starred_count
        )
        
        print(f"  📊 Total: {total_messages} | Inbox: {inbox_count} | Unread: {unread_count} | Starred: {starred_count}")
        
        # Track top senders (last 50 messages in inbox)
        messages_result = service.users().messages().list(
            userId='me',
            labelIds=['INBOX'],
            maxResults=50
        ).execute()
        
        messages = messages_result.get('messages', [])
        senders = []
        
        for msg in messages:
            msg_data = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From']
            ).execute()
            
            headers = msg_data.get('payload', {}).get('headers', [])
            for header in headers:
                if header['name'] == 'From':
                    senders.append(header['value'])
        
        # Count and save top senders
        sender_counts = Counter(senders)
        for sender, count in sender_counts.most_common(10):
            # Parse email
            if '<' in sender:
                name = sender.split('<')[0].strip()
                email = sender.split('<')[1].strip('>')
            else:
                name = sender
                email = sender
            
            sender_obj = db.TopSender(email)
            await sender_obj.set(
                sender_email=email,
                sender_name=name,
                message_count=count,
                last_seen=timestamp
            )
        
        print(f"  ✅ Top sender: {sender_counts.most_common(1)[0][0] if sender_counts else 'None'}")
        
    except FileNotFoundError as e:
        print(f"\n❌ Gmail API not configured!")
        print(str(e))
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
