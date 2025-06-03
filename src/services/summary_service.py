import openai
import os
from datetime import datetime, timedelta
import pytz
from config import GPT_MODEL, MAX_TOKENS, TEMPERATURE

class SummaryService:
    def __init__(self, message_service, user_service):
        self.message_service = message_service
        self.user_service = user_service
        openai.api_key = os.getenv("OPENAI_API_KEY")

    def generate_summary(self, user_id):
        """Generate a personalized summary for a user"""
        # Get user profile and interests
        user = self.user_service.get_user(user_id)
        interests = self.user_service.get_user_interests(user_id)
        
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Get relevant messages
        messages = self._get_relevant_messages(user_id, interests)
        # Get DMs received by the user
        dms_received = self.message_service.get_received_dms(user_id)
        
        if not messages and not dms_received:
            return "No new updates to summarize in the last 24 hours."

        # Prepare context for GPT-4
        context = self._prepare_context(user, interests, messages, dms_received)
        
        # Generate summary using GPT-4
        summary = self._generate_gpt_summary(context)
        
        return summary

    def _get_relevant_messages(self, user_id, interests):
        """Get messages relevant to the user's interests"""
        messages = []
        
        # Get messages from user's channels
        user = self.user_service.get_user(user_id)
        for channel_id in user.get("channels", []):
            messages.extend(self.message_service.get_channel_messages(channel_id))
        
        # Get messages from followed users
        followed_users = interests.get("followed_users", []) if interests else []
        for followed_user in followed_users:
            messages.extend(self.message_service.get_user_messages(followed_user))
        
        # Filter messages by topics of interest
        if interests and interests.get("topics"):
            filtered_messages = []
            for message in messages:
                if any(topic.lower() in message.get("text", "").lower() 
                      for topic in interests["topics"]):
                    filtered_messages.append(message)
            messages = filtered_messages
        
        return messages

    def _prepare_context(self, user, interests, messages, dms_received):
        """Prepare context for GPT-4"""
        context = {
            "user": {
                "name": user.get("name", ""),
                "team": user.get("team", ""),
                "interests": interests.get("topics", []) if interests else []
            },
            "messages": [],
            "dms_received": []
        }
        
        for message in messages:
            context["messages"].append({
                "text": message.get("text", ""),
                "channel": message.get("channel_id", ""),
                "user": message.get("user_id", ""),
                "timestamp": message.get("timestamp", ""),
                "type": message.get("type", ""),
                "files": message.get("files", [])
            })
        for dm in dms_received:
            context["dms_received"].append({
                "text": dm.get("text", ""),
                "sender": dm.get("user_id", ""),
                "timestamp": dm.get("timestamp", "")
            })
        
        return context

    def _generate_gpt_summary(self, context):
        """Generate summary using GPT-4"""
        prompt = self._create_prompt(context)
        
        response = openai.ChatCompletion.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes Slack messages for EV engineering team members."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE
        )
        
        return response.choices[0].message.content

    def _create_prompt(self, context):
        """Create prompt for GPT-4"""
        user = context["user"]
        messages = context["messages"]
        dms_received = context.get("dms_received", [])
        
        prompt = f"""Please create a personalized daily summary for {user['name']} from the EV engineering team ({user['team']}).
        
User's interests: {', '.join(user['interests'])}

Here are the relevant messages from the last 24 hours:\n"""
        
        for message in messages:
            prompt += f"""
Channel: {message['channel']}
User: {message['user']}
Time: {message['timestamp']}
Type: {message['type']}
Content: {message['text']}
"""
            if message['files']:
                prompt += "Files:\n"
                for file in message['files']:
                    prompt += f"- {file['name']} ({file['type']})\n"
        if dms_received:
            prompt += "\nHere are the direct messages you received in the last 24 hours:\n"
            for dm in dms_received:
                prompt += f"Sender: {dm['sender']}\nTime: {dm['timestamp']}\nContent: {dm['text']}\n"
        prompt += """
Please create a concise, well-organized summary that:
1. Highlights key updates related to the user's interests
2. Mentions important mentions or direct interactions
3. Notes any CAD or document uploads
4. Groups updates by topic or channel
5. Includes a section summarizing DMs received
6. Maintains a professional but friendly tone

Format the summary in a clear, readable way with appropriate sections and bullet points."""
        return prompt 