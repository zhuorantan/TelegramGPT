import argparse
import logging
from bot import Bot
from gpt import GPTClient

logging.basicConfig(
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
  level=logging.INFO,
)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('--openai-api-key', type=str, required=True)
  parser.add_argument('--telegram-token', type=str, required=True)
  parser.add_argument('--chat-id', type=int)
  parser.add_argument('--max-message-count', type=int)
  
  args = parser.parse_args()

  gpt = GPTClient(args.openai_api_key, args.max_message_count)

  bot = Bot(gpt, args.chat_id)
  bot.run(args.telegram_token)
