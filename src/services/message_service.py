from datetime import datetime, timedelta
import pytz
from google.cloud import firestore
from config import COLLECTIONS, MESSAGE_TYPES, TRACKED_FILE_TYPES
from src.advanced.auto_tag_service import AutoTagService

auto_tag_service = AutoTagService()

class MessageService:
    def __init__(self):
        self.db = firestore.Client()
        self.messages_collection = self.db.collection(COLLECTIONS["MESSAGES"])

    def store_message(self, message_data):
        """Store a message in Firestore with metadata and auto-tags"""
        tags = auto_tag_service.tag_message(message_data.get("text", "")) if message_data.get("text") else []
        message = {
            "channel_id": message_data.get("channel"),
            "user_id": message_data.get("user"),
            "recipient_id": message_data.get("recipient"),
            "text": message_data.get("text", ""),
            "timestamp": message_data.get("ts"),
            "thread_ts": message_data.get("thread_ts"),
            "type": self._determine_message_type(message_data),
            "files": self._extract_files(message_data),
            "is_pinned": False,  # Will be updated if message is pinned
            "created_at": datetime.now(pytz.UTC),
            "channel_type": message_data.get("channel_type", "channel"),
            "tags": tags
        }
        
        self.messages_collection.add(message)

    def get_recent_messages(self, hours=24):
        """Get messages from the last 24 hours"""
        cutoff_time = datetime.now(pytz.UTC) - timedelta(hours=hours)
        
        query = self.messages_collection.where(
            "created_at", ">=", cutoff_time
        ).order_by("created_at", direction=firestore.Query.DESCENDING)
        
        return [doc.to_dict() for doc in query.stream()]

    def get_user_messages(self, user_id, hours=24):
        """Get messages from a specific user in the last 24 hours"""
        cutoff_time = datetime.now(pytz.UTC) - timedelta(hours=hours)
        
        query = self.messages_collection.where(
            "user_id", "==", user_id
        ).where(
            "created_at", ">=", cutoff_time
        ).order_by("created_at", direction=firestore.Query.DESCENDING)
        
        return [doc.to_dict() for doc in query.stream()]

    def get_channel_messages(self, channel_id, hours=24):
        """Get messages from a specific channel in the last 24 hours"""
        cutoff_time = datetime.now(pytz.UTC) - timedelta(hours=hours)
        
        query = self.messages_collection.where(
            "channel_id", "==", channel_id
        ).where(
            "created_at", ">=", cutoff_time
        ).order_by("created_at", direction=firestore.Query.DESCENDING)
        
        return [doc.to_dict() for doc in query.stream()]

    def get_received_dms(self, user_id, hours=24):
        """Get DMs received by a user in the last 24 hours"""
        cutoff_time = datetime.now(pytz.UTC) - timedelta(hours=hours)
        query = self.messages_collection.where(
            "recipient_id", "==", user_id
        ).where(
            "channel_type", "==", "im"
        ).where(
            "created_at", ">=", cutoff_time
        ).order_by("created_at", direction=firestore.Query.DESCENDING)
        return [doc.to_dict() for doc in query.stream()]

    def _determine_message_type(self, message_data):
        """Determine the type of message"""
        if message_data.get("files"):
            return MESSAGE_TYPES["FILE"]
        if message_data.get("pinned_to"):
            return MESSAGE_TYPES["PIN"]
        if "<@" in message_data.get("text", ""):
            return MESSAGE_TYPES["MENTION"]
        return MESSAGE_TYPES["TEXT"]

    def _extract_files(self, message_data):
        """Extract file information from message"""
        files = []
        if message_data.get("files"):
            for file in message_data["files"]:
                file_type = file.get("filetype", "").lower()
                if file_type in TRACKED_FILE_TYPES:
                    files.append({
                        "id": file.get("id"),
                        "name": file.get("name"),
                        "type": file_type,
                        "url": file.get("url_private")
                    })
        return files 