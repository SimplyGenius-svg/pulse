import os
import threading
from flask import Flask, request, jsonify
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import openai
from datetime import datetime, timedelta
import json
import firebase_admin
from firebase_admin import credentials, firestore
from collections import defaultdict

# Import firebase utilities
from src.services.firebase_utils import (
    get_user, create_or_update_user, mute_user, unmute_user, update_user_digest_config,
    add_kudos, get_recent_kudos, get_open_blockers, get_latest_team_digest, get_latest_trends,
    get_user_messages
)

# Load environment variables
load_dotenv()

# Initialize Firebase
if not firebase_admin._apps:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    else:
        firebase_admin.initialize_app()

db = firestore.client()

# Initialize Flask app
flask_app = Flask(__name__)

# Initialize Slack app
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Initialize OpenAI
from openai import OpenAI
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Channel mapping based on role
ROLE_CHANNEL_MAPPING = {
    "software": ["software", "team"],
    "mechanical": ["mechanical", "team"],
    "electrical": ["electrical", "team"]
}

def get_channel_messages(channel_id, hours_back=24):
    """Get recent messages from a specific channel"""
    try:
        # Calculate timestamp for X hours ago
        since_time = datetime.now() - timedelta(hours=hours_back)
        since_ts = since_time.timestamp()
        
        print(f"🔍 DEBUG: Fetching messages from channel {channel_id} since {since_time}")
        
        # Use Slack API to get messages
        result = slack_app.client.conversations_history(
            channel=channel_id,
            oldest=str(since_ts),
            limit=100
        )
        
        if not result["ok"]:
            print(f"❌ DEBUG: Failed to fetch messages: {result.get('error')}")
            return []
        
        messages = result["messages"]
        print(f"✅ DEBUG: Retrieved {len(messages)} messages from channel {channel_id}")
        
        # Filter out bot messages and format for GPT
        formatted_messages = []
        for msg in messages:
            if not msg.get("bot_id") and msg.get("text"):
                # Get user info
                user_id = msg.get("user")
                user_name = "Unknown"
                if user_id:
                    try:
                        user_info = slack_app.client.users_info(user=user_id)
                        if user_info["ok"]:
                            user_name = user_info["user"]["real_name"] or user_info["user"]["name"]
                    except:
                        pass
                
                timestamp = datetime.fromtimestamp(float(msg["ts"]))
                formatted_messages.append({
                    "user": user_name,
                    "text": msg["text"],
                    "timestamp": timestamp.strftime("%m/%d %H:%M")
                })
        
        return formatted_messages
    except Exception as e:
        print(f"❌ DEBUG: Error fetching messages: {e}")
        return []

def get_dm_conversations(user_id, hours_back=24):
    """Get recent DM conversations for a user"""
    try:
        print(f"🔍 DEBUG: Fetching DM conversations for user {user_id}")
        
        # Get list of DM channels
        result = slack_app.client.conversations_list(
            types="im",
            limit=50
        )
        
        if not result["ok"]:
            return []
        
        dm_summaries = []
        since_time = datetime.now() - timedelta(hours=hours_back)
        since_ts = since_time.timestamp()
        
        for channel in result["channels"]:
            try:
                # Get messages from this DM
                history = slack_app.client.conversations_history(
                    channel=channel["id"],
                    oldest=str(since_ts),
                    limit=20
                )
                
                if history["ok"] and history["messages"]:
                    # Get the other user's name
                    other_user = channel["user"]
                    user_info = slack_app.client.users_info(user=other_user)
                    other_name = "Unknown"
                    if user_info["ok"]:
                        other_name = user_info["user"]["real_name"] or user_info["user"]["name"]
                    
                    # Format messages
                    formatted_msgs = []
                    for msg in history["messages"]:
                        if msg.get("text"):
                            sender = "You" if msg.get("user") == user_id else other_name
                            timestamp = datetime.fromtimestamp(float(msg["ts"]))
                            formatted_msgs.append(f"{sender} ({timestamp.strftime('%m/%d %H:%M')}): {msg['text']}")
                    
                    if formatted_msgs:
                        dm_summaries.append({
                            "partner": other_name,
                            "messages": formatted_msgs[-10:]  # Last 10 messages
                        })
            except Exception as e:
                print(f"⚠️ DEBUG: Error processing DM channel: {e}")
                continue
        
        return dm_summaries
    except Exception as e:
        print(f"❌ DEBUG: Error fetching DMs: {e}")
        return []

def generate_channel_summary(channel_name, messages):
    """Generate AI summary of channel activity"""
    if not messages:
        return f"No recent activity in #{channel_name}"
    
    try:
        # Prepare messages for GPT
        message_text = "\n".join([
            f"[{msg['timestamp']}] {msg['user']}: {msg['text']}"
            for msg in messages[-30:]  # Last 30 messages
        ])
        
        prompt = f"""Analyze the following Slack channel activity from #{channel_name} and provide a concise summary:

{message_text}

Please provide:
1. Key topics/themes discussed
2. Important decisions or action items
3. Notable updates or blockers
4. Overall sentiment/energy

Keep it concise but informative, using clean formatting with bullet points or short paragraphs. Focus on actionable insights."""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes Slack channel activity for team members."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ DEBUG: Error generating summary: {e}")
        return f"Summary unavailable for #{channel_name} (Error: {str(e)})"

def generate_dm_summary(dm_data):
    """Generate AI summary of DM conversations"""
    if not dm_data:
        return "No recent DM activity"
    
    try:
        dm_text = ""
        for dm in dm_data[:5]:  # Top 5 most active DMs
            dm_text += f"\n--- Conversation with {dm['partner']} ---\n"
            dm_text += "\n".join(dm['messages'][-5:])  # Last 5 messages
            dm_text += "\n"
        
        prompt = f"""Analyze the following direct message conversations and provide a brief summary:

{dm_text}

Summarize:
1. Key conversations and their topics
2. Any action items or follow-ups needed
3. Important updates from colleagues

Keep it professional and concise."""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes private conversations professionally."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ DEBUG: Error generating DM summary: {e}")
        return "DM summary unavailable"

def get_channels_for_role(role):
    """Get the appropriate channels for a given role"""
    return ROLE_CHANNEL_MAPPING.get(role, ["team"])

def get_channel_id_by_name(channel_name):
    """Get channel ID from channel name"""
    try:
        print(f"🔍 DEBUG: Looking for channel: {channel_name}")
        result = slack_app.client.conversations_list(
            types="public_channel,private_channel",
            limit=200
        )
        
        if result["ok"]:
            for channel in result["channels"]:
                if channel["name"] == channel_name:
                    print(f"✅ DEBUG: Found channel {channel_name} with ID: {channel['id']}")
                    return channel["id"]
            print(f"❌ DEBUG: Channel {channel_name} not found in conversations list")
        else:
            print(f"❌ DEBUG: Failed to list conversations: {result.get('error')}")
        return None
    except Exception as e:
        print(f"❌ DEBUG: Error finding channel {channel_name}: {e}")
        return None

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    print("🔍 DEBUG: Received HTTP request to /slack/events")
    return SlackRequestHandler(slack_app).handle(request)

@flask_app.route("/health", methods=["GET"])
def health_check():
    print("🔍 DEBUG: Health check requested")
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# Debug: Log all incoming events
@slack_app.middleware
def log_request(body, logger, next):
    print(f"🔍 DEBUG: Incoming request type: {body.get('type', 'unknown')}")
    if 'event' in body:
        print(f"🔍 DEBUG: Event type: {body['event'].get('type', 'unknown')}")
        print(f"🔍 DEBUG: Event data: {body['event']}")
    return next()

# Slack event handlers
@slack_app.event("message")
def handle_message_events(body, logger):
    print(f"🔍 DEBUG: Message event received: {body}")
    event = body.get("event", {})
    
    print(f"🔍 DEBUG: Event details - User: {event.get('user')}, Channel: {event.get('channel')}, Text: {event.get('text', '')[:50]}...")
    
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        print("🔍 DEBUG: Skipping bot message")
        return
    
    # Store message in Firebase
    message_data = {
        "user": event.get("user"),
        "channel": event.get("channel"),
        "text": event.get("text", ""),
        "timestamp": event.get("ts"),
        "thread_ts": event.get("thread_ts"),
        "channel_type": event.get("channel_type", "unknown")
    }
    
    print(f"🔍 DEBUG: Storing message data: {message_data}")
    
    try:
        message_data['created_at'] = firestore.SERVER_TIMESTAMP
        doc_ref = db.collection('messages').add(message_data)
        print(f"✅ DEBUG: Message stored successfully with ID: {doc_ref[1].id}")
    except Exception as e:
        print(f"❌ DEBUG: Error storing message: {e}")
    
    # Update user activity
    user_id = event.get("user")
    if user_id:
        print(f"🔍 DEBUG: Updating activity for user: {user_id}")
        try:
            create_or_update_user(user_id, {
                "last_active": firestore.SERVER_TIMESTAMP,
                "message_count": firestore.Increment(1)
            })
            print(f"✅ DEBUG: User activity updated for: {user_id}")
        except Exception as e:
            print(f"❌ DEBUG: Error updating user activity: {e}")
    else:
        print("⚠️ DEBUG: No user ID found in message event")

# Handle app mentions
@slack_app.event("app_mention")
def handle_app_mention_events(body, logger):
    print(f"🔍 DEBUG: App mention received: {body}")
    event = body.get("event", {})
    
    try:
        # Respond to the mention
        slack_app.client.chat_postMessage(
            channel=event["channel"],
            text=f"👋 Hi <@{event['user']}>! Try `/pulse` to see your profile or `/pulse help` for commands."
        )
        print("✅ DEBUG: Responded to app mention")
    except Exception as e:
        print(f"❌ DEBUG: Error responding to app mention: {e}")

# Handle member joined channel events
@slack_app.event("member_joined_channel")
def handle_member_joined(body, logger):
    print(f"🔍 DEBUG: Member joined channel: {body}")

# Handle member left channel events  
@slack_app.event("member_left_channel")
def handle_member_left(body, logger):
    print(f"🔍 DEBUG: Member left channel: {body}")

# Handle channel created events
@slack_app.event("channel_created")
def handle_channel_created(body, logger):
    print(f"🔍 DEBUG: Channel created: {body}")

@slack_app.command("/pulse")
def pulse_command(ack, body, respond):
    print(f"🔍 DEBUG: /pulse command received: {body}")
    ack()
    
    user_id = body["user_id"]
    text = body.get("text", "").strip()
    args = text.split() if text else []
    subcommand = args[0].lower() if args else ""
    
    print(f"🔍 DEBUG: User {user_id} executed /pulse with subcommand: '{subcommand}'")
    
    # Default behavior: show user profile when no subcommand is provided
    if subcommand == "":
        try:
            print(f"🔍 DEBUG: Getting profile for user: {user_id}")
            profile = get_user(user_id)
            print(f"🔍 DEBUG: Profile data: {profile}")
            
            if not profile:
                print("🔍 DEBUG: No profile found, showing welcome message")
                respond("👋 Welcome! Please run `/pulse setup` to get started.")
                return
            
            tracked_channels = profile.get('tracked_channels', [])
            channel_list = ', '.join([f"#{channel}" for channel in tracked_channels]) if tracked_channels else 'None'
            
            summary = f"""📊 *Your Pulse Profile*

👤 **Personal Info**
• Name: {profile.get('real_name', 'Not set')}
• Role: {profile.get('role', 'Not set')}
• Setup: {'✅ Complete' if profile.get('onboarding_completed') else '❌ Incomplete'}

📺 **Tracking**
• Channels: {channel_list}
• Messages Sent: {profile.get('message_count', 0)}
• Last Active: {profile.get('last_active', 'Never')}

⚙️ **Quick Actions**
• `/pulse setup` - Update your profile
• `/pulse config` - Change settings
• `/pulse help` - View all commands"""
            
            print(f"✅ DEBUG: Sending profile summary to user")
            respond(summary)
        except Exception as e:
            print(f"❌ DEBUG: Error in pulse command: {e}")
    elif subcommand == "setup":
        print("🔍 DEBUG: Starting profile setup")
        start_profile_setup(user_id, respond)
    elif subcommand == "help":
        print("🔍 DEBUG: Showing help text")
        respond(get_help_text())
    elif subcommand == "reset":
        print(f"🔍 DEBUG: Resetting profile for user: {user_id}")
        try:
        # Delete user from Firebase
            user_ref = db.collection('users').document(user_id)
            user_ref.delete()
            respond("✅ Profile deleted! Run `/pulse setup` to start fresh.")
        except Exception as e:
            respond(f"❌ Error: {str(e)}")
    elif subcommand == "me":
        # Keep "me" as alias for the default behavior
        try:
            print(f"🔍 DEBUG: Getting profile for 'me' command: {user_id}")
            profile = get_user(user_id)
            if not profile:
                respond("👋 Welcome! Please run `/pulse setup` to get started.")
                return
            
            tracked_channels = profile.get('tracked_channels', [])
            summary = f"""📊 *Your Profile*
• Name: {profile.get('real_name', 'Not set')}
• Role: {profile.get('role', 'Not set')}
• Tracked Channels: {', '.join(tracked_channels) if tracked_channels else 'None'}
• Messages: {profile.get('message_count', 0)}"""
            
            respond(summary)
        except Exception as e:
            print(f"❌ DEBUG: Error in 'me' command: {e}")
            respond(f"❌ Error: {str(e)}")
    elif subcommand == "update" or subcommand == "summary":
        print(f"🔍 DEBUG: Generating pulse update for user: {user_id}")
        try:
            profile = get_user(user_id)
            if not profile:
                respond("👋 Please run `/pulse setup` first to configure your channels.")
                return
            
            tracked_channels = profile.get('tracked_channels', [])
            if not tracked_channels:
                respond("❌ No channels configured. Run `/pulse setup` to select your role.")
                return
            
            # Show loading message first
            respond("🔄 Generating your pulse update... This may take a moment.")
            
            # Get summaries for tracked channels
            channel_summaries = []
            for channel_name in tracked_channels:
                print(f"🔍 DEBUG: Processing channel: {channel_name}")
                channel_id = get_channel_id_by_name(channel_name)
                if channel_id:
                    messages = get_channel_messages(channel_id, hours_back=24)
                    summary = generate_channel_summary(channel_name, messages)
                    channel_summaries.append(f"📍 **#{channel_name}**\n{summary}\n")
                else:
                    channel_summaries.append(f"📍 **#{channel_name}**\n⚠️ *Channel not found or bot not added to channel*\n")
            
            # Get DM summary
            print(f"🔍 DEBUG: Processing DMs for user: {user_id}")
            dm_data = get_dm_conversations(user_id, hours_back=24)
            dm_summary = generate_dm_summary(dm_data)
            
            # Format the complete update
            pulse_update = f"""📊 **Your Pulse Update**
*Last 24 hours • {datetime.now().strftime('%B %d, %Y at %H:%M')}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏢 **CHANNEL ACTIVITY**

{chr(10).join(channel_summaries)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 **DIRECT MESSAGES**

{dm_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*💡 Use `/pulse channels` or `/pulse dms` for focused updates*"""
            
            # Send the summary (split if too long)
            if len(pulse_update) > 3000:
                # Split into channel and DM parts
                channel_part = f"""📊 **Your Pulse Update - Channel Activity**
*Last 24 hours • {datetime.now().strftime('%B %d, %Y at %H:%M')}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏢 **CHANNEL ACTIVITY**

{chr(10).join(channel_summaries)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
                
                dm_part = f"""📊 **Your Pulse Update - Direct Messages**
*Last 24 hours • {datetime.now().strftime('%B %d, %Y at %H:%M')}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 **DIRECT MESSAGES**

{dm_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*💡 Use `/pulse channels` or `/pulse dms` for focused updates*"""
                
                respond(channel_part)
                respond(dm_part)
            else:
                respond(pulse_update)
                
        except Exception as e:
            print(f"❌ DEBUG: Error generating pulse update: {e}")
            respond(f"❌ Error generating update: {str(e)}")
    
    elif subcommand == "channels":
        print(f"🔍 DEBUG: Showing channel activity for user: {user_id}")
        try:
            profile = get_user(user_id)
            if not profile:
                respond("👋 Please run `/pulse setup` first.")
                return
            
            tracked_channels = profile.get('tracked_channels', [])
            if not tracked_channels:
                respond("❌ No channels configured.")
                return
            
            respond("🔄 Getting channel updates...")
            
            channel_summaries = []
            for channel_name in tracked_channels:
                channel_id = get_channel_id_by_name(channel_name)
                if channel_id:
                    messages = get_channel_messages(channel_id, hours_back=24)
                    summary = generate_channel_summary(channel_name, messages)
                    channel_summaries.append(f"📍 **#{channel_name}**\n{summary}\n")
            
            channels_update = f"""🏢 **Channel Activity Summary**
*Last 24 hours • {datetime.now().strftime('%B %d, %Y at %H:%M')}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{chr(10).join(channel_summaries)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*💡 Use `/pulse update` for full report including DMs*"""
            
            respond(channels_update)
            
        except Exception as e:
            print(f"❌ DEBUG: Error in channels command: {e}")
            respond(f"❌ Error: {str(e)}")
    
    elif subcommand == "dms":
        print(f"🔍 DEBUG: Showing DM summary for user: {user_id}")
        try:
            respond("🔄 Analyzing your direct messages...")
            
            dm_data = get_dm_conversations(user_id, hours_back=24)
            dm_summary = generate_dm_summary(dm_data)
            
            dm_update = f"""💬 **Direct Messages Summary**
*Last 24 hours • {datetime.now().strftime('%B %d, %Y at %H:%M')}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{dm_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*💡 Use `/pulse update` for full report including channels*"""
            
            respond(dm_update)
            
        except Exception as e:
            print(f"❌ DEBUG: Error in DMs command: {e}")
            respond(f"❌ Error: {str(e)}")
    elif subcommand == "config":
        print("🔍 DEBUG: Showing config menu")
        show_config_menu(user_id, respond)
    elif subcommand == "profile":
        print("🔍 DEBUG: Showing user profile")
        show_user_profile(user_id, respond)
    else:
        print(f"🔍 DEBUG: Unknown subcommand: {subcommand}")
        respond(f"Unknown command: `{subcommand}`. Use `/pulse help` for available commands.")

def get_help_text():
    return """🚀 *Pulse Bot Commands*

• `/pulse` - Your complete profile
• `/pulse update` - AI-powered channel & DM summaries
• `/pulse channels` - Channel activity only
• `/pulse dms` - Direct message summaries only
• `/pulse setup` - First-time setup
• `/pulse config` - Manage settings
• `/pulse help` - This help"""

def start_profile_setup(user_id, respond):
    print(f"🔍 DEBUG: Starting profile setup for user: {user_id}")
    setup_blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🚀 Welcome to Pulse Bot!"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*What's your engineering role?*"},
            "accessory": {
                "type": "static_select",
                "placeholder": {"type": "plain_text", "text": "Select your role"},
                "action_id": "setup_role",
                "options": [
                    {"text": {"type": "plain_text", "text": "Software Engineering"}, "value": "software"},
                    {"text": {"type": "plain_text", "text": "Mechanical Engineering"}, "value": "mechanical"},
                    {"text": {"type": "plain_text", "text": "Electrical Engineering"}, "value": "electrical"}
                ]
            }
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "📺 *Channels you'll be tracking:*\n\n• Your role-specific channel\n• Team channel (for all engineering)"}
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Complete Setup"},
                    "style": "primary",
                    "action_id": "complete_setup"
                }
            ]
        }
    ]
    
    respond(blocks=setup_blocks)

def show_config_menu(user_id, respond):
    print(f"🔍 DEBUG: Showing config menu for user: {user_id}")
    profile = get_user(user_id)
    if not profile:
        respond("Please run `/pulse setup` first.")
        return
    
    tracked_channels = profile.get('tracked_channels', [])
    config_blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "⚙️ Your Configuration"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Role:* {profile.get('role', 'Not set')}"},
                {"type": "mrkdwn", "text": f"*Tracked Channels:* {', '.join(tracked_channels) if tracked_channels else 'None'}"}
            ]
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update Role"},
                    "action_id": "config_role"
                }
            ]
        }
    ]
    
    respond(blocks=config_blocks)

def show_user_profile(user_id, respond):
    print(f"🔍 DEBUG: Showing user profile for: {user_id}")
    profile = get_user(user_id)
    if not profile:
        respond("Please run `/pulse setup` first.")
        return
    
    tracked_channels = profile.get('tracked_channels', [])
    
    profile_text = f"""*👤 Profile Information*
• Name: {profile.get('real_name', 'Not set')}
• Role: {profile.get('role', 'Not set')}
• Tracked Channels: {', '.join(tracked_channels) if tracked_channels else 'None'}
• Total Messages: {profile.get('message_count', 0)}
• Setup Complete: {'✅' if profile.get('onboarding_completed') else '❌'}"""
    
    respond(profile_text)

# Action handlers
@slack_app.action("setup_role")
def handle_setup_role(ack, body, respond):
    print(f"🔍 DEBUG: Setup role action received: {body}")
    ack()
    user_id = body["user"]["id"]
    selected_role = body["actions"][0]["selected_option"]["value"]
    
    print(f"🔍 DEBUG: User {user_id} selected role: {selected_role}")
    
    try:
        # Get channels for the selected role
        tracked_channels = get_channels_for_role(selected_role)
        print(f"🔍 DEBUG: Channels for role {selected_role}: {tracked_channels}")
        
        # Update user with role and automatically assigned channels
        create_or_update_user(user_id, {
            "role": selected_role,
            "tracked_channels": tracked_channels
        })
        
        print(f"✅ Updated role for {user_id}: {selected_role}")
        print(f"✅ Auto-assigned channels for {user_id}: {tracked_channels}")
        
        # Show feedback about the channels that will be tracked
        channel_list = ', '.join([f"#{channel}" for channel in tracked_channels])
        respond(f"✅ Role set to **{selected_role}**\n📺 You'll now track: {channel_list}")
        
    except Exception as e:
        print(f"❌ Error updating role: {e}")
        respond(f"❌ Error setting up role: {str(e)}")

@slack_app.action("complete_setup")
def handle_complete_setup(ack, body, respond):
    print(f"🔍 DEBUG: Complete setup action received: {body}")
    ack()
    user_id = body["user"]["id"]
    
    try:
        profile = get_user(user_id)
        print(f"🔍 DEBUG: Profile for completion: {profile}")
        
        if not profile or not profile.get('role'):
            respond("❌ Please select your role first before completing setup.")
            return
        
        create_or_update_user(user_id, {"onboarding_completed": True})
        print(f"✅ DEBUG: Onboarding completed for user: {user_id}")
        
        tracked_channels = profile.get('tracked_channels', [])
        channel_list = ', '.join([f"#{channel}" for channel in tracked_channels])
        
        success_message = f"""🎉 *Setup Complete!*

Your profile is configured:
• Role: {profile.get('role', 'Not set')}
• Tracking: {channel_list}

Try `/pulse` to see your profile!"""
        
        respond(success_message)
    except Exception as e:
        print(f"❌ DEBUG: Setup completion error: {e}")
        respond(f"❌ Setup error: {str(e)}")

@slack_app.action("config_role")
def handle_config_role(ack, body, respond):
    print(f"🔍 DEBUG: Config role action received: {body}")
    ack()
    user_id = body["user"]["id"]
    
    role_blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🔧 Update Your Role"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Select your engineering role:*"},
            "accessory": {
                "type": "static_select",
                "placeholder": {"type": "plain_text", "text": "Choose your role"},
                "action_id": "update_role",
                "options": [
                    {"text": {"type": "plain_text", "text": "Software Engineering"}, "value": "software"},
                    {"text": {"type": "plain_text", "text": "Mechanical Engineering"}, "value": "mechanical"},
                    {"text": {"type": "plain_text", "text": "Electrical Engineering"}, "value": "electrical"}
                ]
            }
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "💡 *Note:* Changing your role will automatically update your tracked channels."}
        }
    ]
    
    respond(blocks=role_blocks)

@slack_app.action("update_role")
def handle_update_role(ack, body, respond):
    print(f"🔍 DEBUG: Update role action received: {body}")
    ack()
    user_id = body["user"]["id"]
    selected_role = body["actions"][0]["selected_option"]["value"]
    
    print(f"🔍 DEBUG: User {user_id} updating to role: {selected_role}")
    
    try:
        # Get channels for the new role
        tracked_channels = get_channels_for_role(selected_role)
        
        # Update user with new role and channels
        create_or_update_user(user_id, {
            "role": selected_role,
            "tracked_channels": tracked_channels
        })
        
        print(f"✅ Updated role for {user_id}: {selected_role}")
        print(f"✅ Updated channels for {user_id}: {tracked_channels}")
        
        channel_list = ', '.join([f"#{channel}" for channel in tracked_channels])
        respond(f"✅ Role updated to **{selected_role}**\n📺 Now tracking: {channel_list}")
        
    except Exception as e:
        print(f"❌ Error updating role: {e}")
        respond(f"❌ Error updating role: {str(e)}")

# Error handling
@slack_app.error
def global_error_handler(error, body, logger):
    print(f"🔍 DEBUG: Global error occurred: {error}")
    print(f"🔍 DEBUG: Error body: {body}")
    logger.exception(f"Error: {error}")
    return f"Sorry, something went wrong: {error}"

if __name__ == "__main__":
    print("🚀 Starting Pulse Bot with Firebase...")
    
    # Debug environment variables (without revealing secrets)
    print(f"🔍 DEBUG: SLACK_BOT_TOKEN present: {bool(os.environ.get('SLACK_BOT_TOKEN'))}")
    print(f"🔍 DEBUG: SLACK_SIGNING_SECRET present: {bool(os.environ.get('SLACK_SIGNING_SECRET'))}")
    print(f"🔍 DEBUG: SLACK_APP_TOKEN present: {bool(os.environ.get('SLACK_APP_TOKEN'))}")
    print(f"🔍 DEBUG: OPENAI_API_KEY present: {bool(os.environ.get('OPENAI_API_KEY'))}")
    
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        exit(1)
    
    try:
        test_query = db.collection('test').limit(1).get()
        print("✅ Firebase connected successfully")
        print(f"🔍 DEBUG: Firebase test query returned {len(list(test_query))} documents")
    except Exception as e:
        print(f"⚠️ Firebase connection warning: {e}")
    
    if os.environ.get("SLACK_APP_TOKEN"):
        print("📡 Starting in Socket Mode...")
        print(f"🔍 DEBUG: Socket Mode Handler initializing...")
        handler = SocketModeHandler(slack_app, os.environ["SLACK_APP_TOKEN"])
        print("🔍 DEBUG: Socket Mode Handler created, starting...")
        handler.start()
        print("🔍 DEBUG: Socket Mode Handler started successfully")
    else:
        print("🌐 Starting in HTTP Mode...")
        print(f"🔍 DEBUG: Starting Flask app on port {int(os.environ.get('PORT', 3000))}")
        flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))