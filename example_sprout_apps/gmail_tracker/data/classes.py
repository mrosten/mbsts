"""
Gmail Tracker Data Classes
"""
from sprout.database.base_object import AbstractDataTable as DataTable


class EmailStats(DataTable):
    """Tracks email inbox statistics over time"""
    
    @property
    def timestamp(self) -> int:
        return self.data.timestamp
    
    @property
    def total_messages(self) -> int:
        return self.data.total_messages
    
    @property
    def unread_count(self) -> int:
        return self.data.unread_count
    
    @property
    def inbox_count(self) -> int:
        return self.data.inbox_count
    
    @property
    def starred_count(self) -> int:
        return self.data.starred_count


class TopSender(DataTable):
    """Tracks top email senders"""
    
    @property
    def sender_email(self) -> str:
        return self.data.sender_email
    
    @property
    def sender_name(self) -> str:
        return self.data.sender_name
    
    @property
    def message_count(self) -> int:
        return self.data.message_count
    
    @property
    def last_seen(self) -> int:
        return self.data.last_seen
