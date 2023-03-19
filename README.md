# TelegramGPT

Telegram bot for ChatGPT using [official OpenAI API](https://platform.openai.com/docs/guides/chat). This project is experimental and subject to change.

## Features

- All the powers of ChatGPT
- Conversation history just like the OG ChatGPT
- Restrict bot to specific chats
- Resume previous conversations
- Regenerate response for last message

## Get Started

### 1. Create a Telegram bot

Create a Telegram bot using [@BotFather](https://t.me/BotFather) and get the token.

### 2. Create a OpenAI API key

Go to [OpenAI Dashboard](https://platform.openai.com/account/api-keys) and create a API key.

### 3. Deploy

#### Docker

```bash
docker build -t telegram-gpt github.com/zhuorantan/TelegramGPT#main
docker run --rm -v /path/to/data:/app/data telegram-gpt --openai-api-key "<OPENAI_API_KEY>" --telegram-token "<TELEGRAM_TOKEN>"
```

> Note: If no directory is mapped to `/app/data`, all conversations will be lost after the container is recreated.

#### Docker Compose

```yaml
services:
  telegram-gpt:
    build: github.com/zhuorantan/TelegramGPT#main
    container_name: telegram-gpt
    restart: unless-stopped
    volumes:
      - /path/to/data:/app/data
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

Optionally set `--chat-id` to restrict the bot to specific chats.
To allow multiple chats, set `--chat-id` multiple times.
If no `--chat-id` is set, the bot will accept messages from any chat.

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

- `--data-dir`

Set the directory to store conversation data. If not set, data won't be persisted.

- `--webhook-listen-address`

The address to listen on the local machine for webhook requests in the format of `<host>:<port>`. If not set, the bot will use polling.

To use webhook mode, you need a public domain name. For more information, see [Marvin's Marvellous Guide to All Things Webhook](https://core.telegram.org/bots/webhooks).

- `--webhook-url`

The URL to use for webhook requests. It is only used when `--webhook-listen-address` is set. If not set, the bot will default to `https://<webhook_listen_address>`.

Since Telegram requires https for webhook, you need to use a reverse proxy like [Caddy](https://caddyserver.com/) or [Nginx](https://www.nginx.com/) to handle https traffic.

#### Proxy

To use proxy, add `-e http_proxy=http://<proxy>:<port>` and `-e https_proxy=http://<proxy>:<port>` to the `docker run` command.
For Docker Compose, add the environment variables to the `environment` section.

## Usage

Simply send a message to the bot and it will reply with a ChatGPT response.

### Commands

- `/new`: Manually start a new conversation
- `/history`: Show a list of all previous conversations. Tap the command at the beginning of each line to resume a specific conversation.
- `/retry`: Regenerate response for last message
- `/mode`: Switch conversation mode to a previously defined mode via `/addmode`.
- `/addmode`: Add a new conversation mode. A mode consists of a name and a prompt. The prompt will be used as the system prompt for conversations.
- `/editmodes`: Edit or delete a mode.
