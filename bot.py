import logging
from dataclasses import dataclass
from chat import ChatData, ChatManager, ChatState, ChatContext
from gpt import GPTClient
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, PicklePersistence, filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler
from typing import cast

async def __state(_: Update, context: ContextTypes.DEFAULT_TYPE, chat_manager: ChatManager):
  chat_id = chat_manager.context.chat_id

  await context.bot.send_message(chat_id=chat_id, text="Start by sending me a message!")

  logging.info(f"Start command executed for chat {chat_id}")

async def __handle_message(update: Update, _: ContextTypes.DEFAULT_TYPE, chat_manager: ChatManager):
  if not update.message or not update.message.text:
    logging.warning(f"Update received but ignored because it doesn't have a message")
    return

  await chat_manager.handle_message(text=update.message.text)

async def __retry_last_message(_: Update, _context: ContextTypes.DEFAULT_TYPE, chat_manager: ChatManager):
  await chat_manager.retry_last_message()

async def __resume(update: Update, _: ContextTypes.DEFAULT_TYPE, chat_manager: ChatManager):
  conversation_id = None
  query = update.callback_query

  if query and query.data and query.data.startswith('resume_'):
    await query.answer()
    conversation_id = int(query.data.split('_')[1])
  elif update.message and update.message.text and update.message.text.startswith('/resume_'):
    conversation_id = int(update.message.text.split('_')[1])
  else:
    raise Exception("Invalid parameters")

  await chat_manager.resume(conversation_id=conversation_id)

async def __new_conversation(_: Update, _context: ContextTypes.DEFAULT_TYPE, chat_manager: ChatManager):
  await chat_manager.new_conversation()

async def __show_conversation_history(_: Update, _context: ContextTypes.DEFAULT_TYPE, chat_manager: ChatManager):
  await chat_manager.show_conversation_history()

@dataclass
class WebhookInfo:
  listen_address: str
  url: str|None

async def __post_init(app: Application):
  commands = [
    ('new', "Start a new conversation"),
    ('history', "Show previous conversations"),
    ('retry', "Regenerate response for last message"),
  ]
  await app.bot.set_my_commands(commands)
  logging.info("Set command list")

def __create_callback(gpt: GPTClient, allowed_chat_ids: set[int], conversation_timeout: int|None, chat_states: dict[int, ChatState], callback):
  async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      logging.warning(f"Message received but ignored because it doesn't have a chat")
      return

    chat_id = update.effective_chat.id

    if len(allowed_chat_ids) > 0 and not chat_id in allowed_chat_ids:
      logging.info(f"Message received for chat {chat_id} but ignored because it's not the configured chat")
      return

    if chat_id not in chat_states:
      chat_states[chat_id] = ChatState()
    chat_state = chat_states[chat_id]
    chat_data = cast(ChatData, context.chat_data)
    chat_context = ChatContext(chat_id, chat_state, chat_data)

    chat_manager = ChatManager(gpt=gpt, bot=context.bot, context=chat_context, conversation_timeout=conversation_timeout)

    await callback(update, context, chat_manager)

  return handler

def run(token: str, gpt: GPTClient, chat_ids: list[int], conversation_timeout: int|None, data_path: str, webhook_info: WebhookInfo|None):
  allowed_chat_ids = set(chat_ids)
  chat_states = {}

  def create_callback(callback):
    return __create_callback(gpt, allowed_chat_ids, conversation_timeout, chat_states, callback)

  persistence = PicklePersistence(data_path)
  app = ApplicationBuilder().token(token).persistence(persistence).post_init(__post_init).build()

  app.add_handler(CommandHandler('start', create_callback(__state), block=False))
  app.add_handler(MessageHandler(filters.UpdateType.MESSAGE & (~filters.COMMAND), create_callback(__handle_message), block=False))
  app.add_handler(CallbackQueryHandler(create_callback(__resume), pattern=r'^resume_\d+$', block=False))
  app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r'\/resume_\d+'), create_callback(__resume), block=False))
  app.add_handler(CommandHandler('new', create_callback(__new_conversation), block=False))
  app.add_handler(CommandHandler('history', create_callback(__show_conversation_history), block=False))
  app.add_handler(CommandHandler('retry', create_callback(__retry_last_message), block=False))
  app.add_handler(CallbackQueryHandler(create_callback(__retry_last_message), pattern='retry', block=False))

  if webhook_info:
    parts = webhook_info.listen_address.split(':')
    host = parts[0]
    port = int(parts[1] if len(parts) > 1 else 80)
    url = webhook_info.url or f"https://{webhook_info.listen_address}"
    app.run_webhook(host, port, webhook_url=url)
  else:
    app.run_polling()
