from google.cloud import firestore
from config import COLLECTIONS
from src.config.roles import ENGINEERING_ROLES, ROLE_HIERARCHY, CHANNEL_ACCESS_LEVELS

class RoleService:
    def __init__(self):
        self.db = firestore.Client()
        self.roles_collection = self.db.collection(COLLECTIONS["ROLES"])

    def assign_role(self, user_id, role):
        """Assign a role to a user"""
        if role not in ENGINEERING_ROLES:
            raise ValueError(f"Invalid role: {role}")

        role_data = {
            "user_id": user_id,
            "role": role,
            "permissions": ENGINEERING_ROLES[role],
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        }
        
        self.roles_collection.document(user_id).set(role_data, merge=True)
        return role_data

    def get_user_role(self, user_id):
        """Get a user's role"""
        doc = self.roles_collection.document(user_id).get()
        return doc.to_dict() if doc.exists else None

    def can_access_channel(self, user_id, channel):
        """Check if a user can access a channel"""
        role_data = self.get_user_role(user_id)
        if not role_data:
            return False

        role = role_data["role"]
        permissions = ENGINEERING_ROLES[role]

        # Project managers can access all channels
        if role == "PROJECT_MANAGER":
            return True

        # Check if channel is in user's allowed channels
        if channel in permissions["can_access"]:
            return True

        # Check channel access level
        channel_level = CHANNEL_ACCESS_LEVELS.get(channel, 1)
        role_level = ROLE_HIERARCHY.get(role, ROLE_HIERARCHY["DEFAULT"])
        
        return role_level >= channel_level

    def get_default_interests(self, role):
        """Get default interests for a role"""
        if role not in ENGINEERING_ROLES:
            return []
        return ENGINEERING_ROLES[role]["default_interests"]

    def get_default_channels(self, role):
        """Get default channels for a role"""
        if role not in ENGINEERING_ROLES:
            return []
        return ENGINEERING_ROLES[role]["channels"]

    def get_users_by_role(self, role):
        """Get all users with a specific role"""
        query = self.roles_collection.where("role", "==", role)
        return [doc.to_dict() for doc in query.stream()]

    def get_role_hierarchy(self):
        """Get the role hierarchy"""
        return ROLE_HIERARCHY

    def get_available_roles(self):
        """Get all available roles"""
        return list(ENGINEERING_ROLES.keys()) 