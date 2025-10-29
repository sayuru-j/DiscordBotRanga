# Discord Ollama Bot

A Discord bot that integrates with Ollama to provide AI-powered chat using the Mistral 7B model.

## Features

- 🤖 Chat with Mistral AI through Discord
- 💬 Responds to mentions and DMs
- ⚡ Fast responses using local Ollama
- 🛠️ Built-in commands for status checking
- 🔧 Configurable settings

## Prerequisites

- Python 3.8 or higher
- Ollama installed and running
- Mistral 7B model pulled in Ollama
- Discord bot token

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section
4. Create a bot and copy the token
5. Enable "Message Content Intent" in the bot settings
6. Invite the bot to your server with appropriate permissions

### 3. Configure Environment

Create a `.env` file in the project root with the following content:

```env
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_bot_token_here

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral:7b-instruct-q4_0

# Bot Settings
BOT_PREFIX=!
MAX_MESSAGE_LENGTH=2000
```

Replace `your_discord_bot_token_here` with your actual Discord bot token.

### 4. Start Ollama

Make sure Ollama is running and you have the Mistral model:

```bash
ollama serve
ollama pull mistral:7b-instruct-q4_0
```

### 5. Run the Bot

```bash
python bot.py
```

## Usage

### Chatting with the Bot

- **Mention the bot**: `@YourBotName Hello, how are you?`
- **Send a DM**: Direct message the bot
- **Commands**: Use `!help` to see available commands

### Available Commands

- `!ping` - Check bot latency
- `!ollama_status` - Check Ollama connection and available models
- `!help` - Show help message

## Configuration

You can modify the following settings in the `.env` file:

- `DISCORD_TOKEN`: Your Discord bot token
- `OLLAMA_BASE_URL`: Ollama server URL (default: http://localhost:11434)
- `OLLAMA_MODEL`: Model to use (default: mistral:7b-instruct-q4_0)
- `BOT_PREFIX`: Command prefix (default: !)
- `MAX_MESSAGE_LENGTH`: Maximum message length for Discord (default: 2000)

## Troubleshooting

### Bot not responding
- Check if the bot token is correct
- Ensure the bot has "Message Content Intent" enabled
- Verify the bot has proper permissions in your server

### Ollama connection issues
- Make sure Ollama is running (`ollama serve`)
- Check if the model is available (`ollama list`)
- Verify the Ollama URL in your `.env` file

### Model not found
- Pull the model: `ollama pull mistral:7b-instruct-q4_0`
- Check available models: `ollama list`

## File Structure

```
DiscordBotRanga/
├── bot.py              # Main bot file
├── config.py           # Configuration loader
├── requirements.txt    # Python dependencies
├── .env               # Environment variables (create this)
└── README.md          # This file
```

## License

This project is open source and available under the MIT License.
