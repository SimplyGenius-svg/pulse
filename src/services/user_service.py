from google.cloud import firestore
from config import COLLECTIONS
from src.services.role_service import RoleService

class UserService:
    def __init__(self):
        self.db = firestore.Client()
        self.users_collection = self.db.collection(COLLECTIONS["USERS"])
        self.interests_collection = self.db.collection(COLLECTIONS["INTERESTS"])
        self.role_service = RoleService()

    def create_user(self, user_id, user_data):
        """Create or update a user profile"""
        # Get role and set default channels/interests
        role = user_data.get("role", "DEFAULT")
        role_service = RoleService()
        
        # Set default channels and interests based on role
        default_channels = role_service.get_default_channels(role)
        default_interests = role_service.get_default_interests(role)
        
        user = {
            "id": user_id,
            "name": user_data.get("name", ""),
            "email": user_data.get("email", ""),
            "team": user_data.get("team", ""),
            "channels": user_data.get("channels", default_channels),
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        }
        
        self.users_collection.document(user_id).set(user, merge=True)
        
        # Set default interests
        if default_interests:
            self.update_user_interests(user_id, {"topics": default_interests})
        
        # Assign role
        role_service.assign_role(user_id, role)
        
        return user

    def get_user(self, user_id):
        """Get user profile by ID"""
        doc = self.users_collection.document(user_id).get()
        user_data = doc.to_dict() if doc.exists else None
        
        if user_data:
            # Add role information
            role_data = self.role_service.get_user_role(user_id)
            if role_data:
                user_data["role"] = role_data["role"]
                user_data["permissions"] = role_data["permissions"]
        
        return user_data

    def get_all_users(self):
        """Get all user profiles"""
        users = [doc.to_dict() for doc in self.users_collection.stream()]
        
        # Add role information to each user
        for user in users:
            role_data = self.role_service.get_user_role(user["id"])
            if role_data:
                user["role"] = role_data["role"]
                user["permissions"] = role_data["permissions"]
        
        return users

    def update_user_interests(self, user_id, interests):
        """Update user's interests"""
        interest_doc = {
            "user_id": user_id,
            "topics": interests.get("topics", []),
            "followed_users": interests.get("followed_users", []),
            "updated_at": firestore.SERVER_TIMESTAMP
        }
        
        self.interests_collection.document(user_id).set(interest_doc, merge=True)
        return interest_doc

    def get_user_interests(self, user_id):
        """Get user's interests"""
        doc = self.interests_collection.document(user_id).get()
        return doc.to_dict() if doc.exists else None

    def get_users_by_interest(self, topic):
        """Get users interested in a specific topic"""
        query = self.interests_collection.where("topics", "array_contains", topic)
        return [doc.to_dict() for doc in query.stream()]

    def get_followed_users(self, user_id):
        """Get users that a specific user follows"""
        doc = self.interests_collection.document(user_id).get()
        if doc.exists:
            return doc.to_dict().get("followed_users", [])
        return []

    def add_user_to_channel(self, user_id, channel_id):
        """Add a channel to user's channel list if they have permission"""
        if not self.role_service.can_access_channel(user_id, channel_id):
            raise PermissionError(f"User {user_id} does not have permission to access channel {channel_id}")
        
        user_ref = self.users_collection.document(user_id)
        user_ref.update({
            "channels": firestore.ArrayUnion([channel_id]),
            "updated_at": firestore.SERVER_TIMESTAMP
        })

    def remove_user_from_channel(self, user_id, channel_id):
        """Remove a channel from user's channel list"""
        user_ref = self.users_collection.document(user_id)
        user_ref.update({
            "channels": firestore.ArrayRemove([channel_id]),
            "updated_at": firestore.SERVER_TIMESTAMP
        })

    def get_users_by_role(self, role):
        """Get all users with a specific role"""
        return self.role_service.get_users_by_role(role)

    def get_available_roles(self):
        """Get all available roles"""
        return self.role_service.get_available_roles() 