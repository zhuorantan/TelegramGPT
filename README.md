# TelegramGPT

Telegram bot for ChatGPT using [official OpenAI API](https://platform.openai.com/docs/guides/chat).

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

Optionally set `--chat-id` to restrict the bot to a specific chat. You can get your chat ID by sending a message to the bot and going to this URL to view the chat ID:

`https://api.telegram.org/bot<TELEGRAM_TOKEN>/getUpdates`

The chat ID would be the `id` field in the JSON response.

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

> To use proxy, add `-e http_proxy=http://<proxy>:<port>` and `-e https_proxy=http://<proxy>:<port>` to the `docker run` command.
For Docker Compose, add the environment variables to the `environment` section.

## Usage

Simply send a message to the bot and it will reply with a ChatGPT response. To clear current conversation, send command `/clear`.
