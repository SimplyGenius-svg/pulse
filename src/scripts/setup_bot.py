import os
import sys
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config.roles import ENGINEERING_ROLES
from src.services.user_service import UserService
from src.services.role_service import RoleService

def get_channel_welcome_message(channel):
    messages = {
        "general": "Welcome to the Pulse EV Engineering workspace! 🚗⚡\nPlease join your team channels and set your role and interests with @Pulse.",
        "mechanical": "Welcome to #mechanical! Discuss all things related to mechanical design, CAD, and manufacturing here. Share your latest designs, ask for feedback, or coordinate with the team.",
        "electrical": "Welcome to #electrical! Battery, power electronics, and wiring discussions go here. Share schematics, troubleshooting tips, and updates.",
        "software": "Welcome to #software! Firmware, controls, and code reviews live here. Share your latest commits, ask for help, or discuss new features.",
        "systems": "Welcome to #systems! Systems engineering, integration, and testing discussions.",
        "cad": "Welcome to #cad! Share CAD files, design reviews, and related discussions.",
        "battery": "Welcome to #battery! Battery-specific discussions and updates.",
        "manufacturing": "Welcome to #manufacturing! Manufacturing updates and coordination.",
        "firmware": "Welcome to #firmware! Firmware/software updates and discussions.",
        "project-management": "Project managers and leads: use this channel for planning, milestones, and resource allocation.",
        "announcements": "This channel is for official announcements only. Please do not post here unless you are a project lead.",
        "random": "Share memes, fun stories, or anything off-topic here!"
    }
    return messages.get(channel, f"Welcome to #{channel}!")

def setup_channels(client):
    """Create necessary Slack channels and post welcome messages"""
    channels = set()
    
    # Collect all channels from roles
    for role in ENGINEERING_ROLES.values():
        channels.update(role["channels"])
    
    # Add general channels
    channels.update(["general", "announcements", "random", "systems", "battery", "firmware", "manufacturing", "cad", "project-management"])
    
    created_channels = []
    for channel in channels:
        try:
            # Check if channel exists
            result = client.conversations_list(types="public_channel,private_channel")
            existing_channels = {c["name"]: c["id"] for c in result["channels"]}
            
            if channel not in existing_channels:
                # Create channel
                response = client.conversations_create(name=channel)
                channel_id = response["channel"]["id"]
                created_channels.append(channel)
                print(f"Created channel: #{channel}")
            else:
                channel_id = existing_channels[channel]
                print(f"Channel #{channel} already exists")
            
            # Post welcome message
            welcome_message = get_channel_welcome_message(channel)
            try:
                client.chat_postMessage(channel=channel_id, text=welcome_message)
                print(f"Posted welcome message in #{channel}")
            except SlackApiError as e:
                print(f"Error posting welcome message in #{channel}: {e.response['error']}")
        except SlackApiError as e:
            print(f"Error creating channel #{channel}: {e.response['error']}")
    
    return created_channels

def setup_roles():
    """Initialize roles in the database"""
    role_service = RoleService()
    user_service = UserService()
    
    # Create a test user for each role
    for role in ENGINEERING_ROLES.keys():
        try:
            # Create a test user with the role
            user_data = {
                "name": f"Test {role} User",
                "email": f"test.{role.lower()}@example.com",
                "team": ENGINEERING_ROLES[role]["name"],
                "role": role
            }
            
            # Use a test user ID (you'll need to replace this with actual user IDs)
            test_user_id = f"TEST_{role}"
            user_service.create_user(test_user_id, user_data)
            print(f"Created test user for role: {role}")
            
        except Exception as e:
            print(f"Error setting up role {role}: {str(e)}")

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize Slack client
    client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))
    
    print("Setting up Pulse bot...")
    
    # Create channels
    print("\nCreating channels and posting welcome messages...")
    created_channels = setup_channels(client)
    print(f"Created {len(created_channels)} new channels")
    
    # Setup roles
    print("\nSetting up roles...")
    setup_roles()
    
    print("\nSetup complete! You can now:")
    print("1. Invite the bot to your channels")
    print("2. Add real users with their roles")
    print("3. Start the bot with 'python app.py'")

if __name__ == "__main__":
    main() 