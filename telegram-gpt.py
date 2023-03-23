import argparse
import logging
import os
from bot import BotOptions, WebhookOptions, run
from gpt import GPTClient, GPTOptions
from speech import SpeechClient

logging.basicConfig(
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
  level=logging.INFO,
)

if __name__ == "__main__":
  def get_chat_ids_from_env():
    chat_ids = []

    while True:
      chat_id = os.environ.get('TELEGRAM_GPT_CHAT_ID_' + str(len(chat_ids)))
      if chat_id is None:
        break
      chat_ids.append(int(chat_id))

    if 'TELEGRAM_GPT_CHAT_ID' in os.environ:
      chat_ids.append(int(os.environ['TELEGRAM_GPT_CHAT_ID']))

    return chat_ids

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '--openai-api-key',
    type=str,
    default=os.environ.get('TELEGRAM_GPT_OPENAI_API_KEY'),
    required='TELEGRAM_GPT_OPENAI_API_KEY' not in os.environ,
    help="OpenAI API key (https://platform.openai.com/account/api-keys). If --azure-openai-endpoint is specified, this is the Azure OpenAI Service API key.",
  )
  parser.add_argument(
    '--telegram-token',
    type=str,
    default=os.environ.get('TELEGRAM_GPT_TELEGRAM_TOKEN'),
    required='TELEGRAM_GPT_TELEGRAM_TOKEN' not in os.environ,
    help="Telegram bot token. Get it from https://t.me/BotFather.",
  )

  parser.add_argument(
    '--chat-id',
    action='append',
    type=int,
    default=get_chat_ids_from_env(),
    help= "IDs of Allowed chats. Can be specified multiple times. If not specified, the bot will respond to all chats.",
  )
  parser.add_argument(
    '--conversation-timeout',
    type=int,
    default=int(os.environ['TELEGRAM_GPT_CONVERSATION_TIMEOUT']) if 'TELEGRAM_GPT_CONVERSATION_TIMEOUT' in os.environ else None,
    help="Timeout in seconds for a conversation to expire. If not specified, the bot will keep the conversation alive indefinitely.",
  )
  parser.add_argument(
    '--max-message-count',
    type=int,
    default=int(os.environ['TELEGRAM_GPT_MAX_MESSAGE_COUNT']) if 'TELEGRAM_GPT_MAX_MESSAGE_COUNT' in os.environ else None,
    help="Maximum number of messages to keep in the conversation. Earlier messages will be discarded with this option set. If not specified, the bot will keep all messages in the conversation.",
  )

  parser.add_argument(
    '--data-dir',
    type=str,
    default=os.environ.get('TELEGRAM_GPT_DATA_DIR'),
    help="Directory to store data. If not specified, data won't be persisted.",
  )
  parser.add_argument(
    '--webhook-url',
    type=str,
    default=os.environ.get('TELEGRAM_GPT_WEBHOOK_URL'),
    help="URL for telegram webhook requests. If not specified, the bot will use polling mode.",
  )
  parser.add_argument(
    '--webhook-listen-address',
    type=str,
    default=os.environ.get('TELEGRAM_GPT_WEBHOOK_LISTEN_ADDRESS') or '0.0.0.0:80',
    help="Address to listen for telegram webhook requests in the format of <ip>:<port>. Only valid when --webhook-url is set. If not specified, 0.0.0.0:80 would be used.",
  )

  parser.add_argument(
    '--openai-model-name',
    type=str,
    default=os.environ.get('TELEGRAM_GPT_OPENAI_MODEL_NAME') or 'gpt-3.5-turbo',
    help="Chat completion model name (https://platform.openai.com/docs/models/model-endpoint-compatibility). If --azure-openai-endpoint is specified, this is the Azure OpenAI Service model deployment name. Default to be gpt-3.5-turbo.",
  )
  parser.add_argument(
    '--azure-openai-endpoint',
    type=str,
    default=os.environ.get('TELEGRAM_GPT_AZURE_OPENAI_ENDPOINT'),
    help="Azure OpenAI Service endpoint. Set this option to use Azure OpenAI Service instead of OpenAI API."
  )

  parser.add_argument(
    '--azure-speech-key',
    type=str,
    default=os.environ.get('TELEGRAM_GPT_AZURE_SPEECH_KEY'),
    help="Azure Speech Services API key. Set this option to enable voice messages powered by Azure speech-to-text and text-to-speech services.",
  )
  parser.add_argument(
    '--azure-speech-region',
    type=str,
    default=os.environ.get('TELEGRAM_GPT_AZURE_SPEECH_REGION') or 'westus',
    help="Azure Speech Services region. Default to be westus. Only valid when --azure-speech-key is set.",
  )
  
  args = parser.parse_args()

  gpt_options = GPTOptions(args.openai_api_key, args.openai_model_name, args.azure_openai_endpoint, args.max_message_count)
  logging.info(f"Initializing GPTClient with options: {gpt_options}")
  gpt = GPTClient(options=gpt_options)

  speech = SpeechClient(args.azure_speech_key, args.azure_speech_region) if args.azure_speech_key is not None else None

  webhook_options = WebhookOptions(args.webhook_url, args.webhook_listen_address) if args.webhook_url is not None else None
  bot_options = BotOptions(args.telegram_token, set(args.chat_id), args.conversation_timeout, args.data_dir, webhook_options)
  logging.info(f"Starting bot with options: {bot_options}")

  run(args.telegram_token, gpt, speech, bot_options)
