import argparse
import logging
import os
from bot import WebhookInfo, run
from gpt import GPTClient
from speech import SpeechClient

logging.basicConfig(
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
  level=logging.INFO,
)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('--openai-api-key', type=str, required=True)
  parser.add_argument('--telegram-token', type=str, required=True)
  parser.add_argument('--chat-id', action='append', type=int)
  parser.add_argument('--conversation-timeout', type=int)
  parser.add_argument('--max-message-count', type=int)
  parser.add_argument('--data-dir', type=str)
  parser.add_argument('--webhook-listen-address', type=str)
  parser.add_argument('--webhook-url', type=str)
  parser.add_argument('--azure-speech-key', type=str)
  parser.add_argument('--azure-speech-region', type=str)
  
  args = parser.parse_args()

  gpt = GPTClient(args.openai_api_key, args.max_message_count)
  speech = SpeechClient(args.azure_speech_key, args.azure_speech_region) if args.azure_speech_key is not None else None
  data_path = os.path.join(args.data_dir, 'data') if args.data_dir is not None else None
  webhook_info = WebhookInfo(args.webhook_listen_address, args.webhook_url) if args.webhook_listen_address is not None else None

  run(args.telegram_token, gpt, speech, args.chat_id, args.conversation_timeout, data_path, webhook_info)
