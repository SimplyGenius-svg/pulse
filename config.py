import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Slack configuration
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Firestore configuration
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Application configuration
DAILY_SUMMARY_TIME = "09:00"  # 9 AM
SUMMARY_TIMEZONE = "UTC"  # Change this to your team's timezone

# Message types to track
MESSAGE_TYPES = {
    "TEXT": "text",
    "FILE": "file",
    "PIN": "pin",
    "MENTION": "mention"
}

# File types to track
TRACKED_FILE_TYPES = [
    "cad",  # CAD files
    "pdf",  # PDF documents
    "doc",  # Word documents
    "docx",
    "xls",  # Excel files
    "xlsx",
    "ppt",  # PowerPoint files
    "pptx"
]

# GPT-4 configuration
GPT_MODEL = "gpt-4"
MAX_TOKENS = 1000
TEMPERATURE = 0.7

# Database collections
COLLECTIONS = {
    "MESSAGES": "messages",
    "USERS": "users",
    "INTERESTS": "interests",
    "ROLES": "roles"  # New collection for roles
} 