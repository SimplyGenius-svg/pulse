# Pulse EV Slack Bot

A personalized daily recap bot for EV engineering teams that summarizes relevant updates from Slack channels and DMs.

## Features

- Daily personalized recaps via DM at 9 AM
- Message storage with metadata in Firestore
- User interest profiles for customized updates
- GPT-4 powered summaries
- Support for mentions, CAD uploads, and pinned messages
- Manual trigger endpoint for on-demand summaries

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/pulse-ev-slackbot.git
cd pulse-ev-slackbot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
OPENAI_API_KEY=your-openai-api-key
GOOGLE_APPLICATION_CREDENTIALS=path/to/firestore-credentials.json
```

4. Set up Firestore:
- Create a new Firestore project in Google Cloud Console
- Download the service account credentials JSON file
- Set the path in GOOGLE_APPLICATION_CREDENTIALS

5. Run the bot:
```bash
python app.py
```

## Project Structure

```
pulse-ev-slackbot/
├── app.py                 # Main application entry point
├── config.py             # Configuration and environment variables
├── requirements.txt      # Project dependencies
├── src/
│   ├── bot/             # Slack bot related code
│   ├── database/        # Firestore database operations
│   ├── services/        # Business logic services
│   └── utils/           # Utility functions
└── tests/               # Test files
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License 