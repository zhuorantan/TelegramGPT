# TelegramGPT

Telegram bot for ChatGPT using [official OpenAI API](https://platform.openai.com/docs/guides/chat). This project is experimental and subject to change.

## Features

- All the powers of ChatGPT
- Conversation history just like the OG ChatGPT
- Resume previous conversations

## Get Started

### 1. Create a Telegram bot

Create a Telegram bot using [@BotFather](https://t.me/BotFather) and get the token.

### 2. Create a OpenAI API key

Go to [OpenAI Dashboard](https://platform.openai.com/account/api-keys) and create a API key.

### 3. Deploy

#### Docker

```bash
docker build -t telegram-gpt github.com/zhuorantan/TelegramGPT#main
docker run --rm telegram-gpt --openai-api-key "<OPENAI_API_KEY>" --telegram-token "<TELEGRAM_TOKEN>"
```

#### Docker Compose

```yaml
services:
  telegram-gpt:
    build: github.com/zhuorantan/TelegramGPT#main
    container_name: telegram-gpt
    restart: unless-stopped
    command:
      - --openai-api-key
      - "<OPENAI_API_KEY>"
      - --telegram-token
      - "<TELEGRAM_TOKEN>"
      - --chat-id
      - "<CHAT_ID>"
```

#### Options

- `--chat-id`

Optionally set `--chat-id` to restrict the bot to a specific chat.
You can get your chat ID by sending a message to the bot and going to this URL to view the chat ID:

`https://api.telegram.org/bot<TELEGRAM_TOKEN>/getUpdates`

The chat ID would be the `id` field in the JSON response.

- `--conversation-timeout`

A timeout in seconds after which a new conversation is automatically started.
Default is not set, which means new conversations won't automatically start.

A resume button would be added to the last message of the previous conversation when a new conversation is started.
Tap the button to resume that conversation.

- `--max-message-count`

Limit the number of messages to be sent to OpenAI API. Default is not set, which is unlimited.


> To use proxy, add `-e http_proxy=http://<proxy>:<port>` and `-e https_proxy=http://<proxy>:<port>` to the `docker run` command.
For Docker Compose, add the environment variables to the `environment` section.

## Usage

Simply send a message to the bot and it will reply with a ChatGPT response.

### Commands

- `/new`: Manually start a new conversation
- `/history`: Show a list of all previous conversations. Tap the command at the beginning of each line to resume a specific conversation.
