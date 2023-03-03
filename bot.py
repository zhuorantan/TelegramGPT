import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message as TGMessage, Update
from telegram.ext import CallbackQueryHandler, filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler
from gpt import GPTClient
from models import Conversation

class Bot:
  def __init__(self, gpt: GPTClient, chat_id: str|None, conversation_timeout: int):
    self.__gpt = gpt
    self.__chat_id = chat_id
    self.__conversation_timeout = conversation_timeout
    self.__timeout_tasks = {}

  def run(self, token: str):
    app = ApplicationBuilder().token(token).concurrent_updates(True).build()

    app.add_handler(CommandHandler('start', self.__start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.__reply))
    app.add_handler(CallbackQueryHandler(self.__resume))
    app.add_handler(CommandHandler('new', self.__new_conversation))

    app.run_polling()

  async def __start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      logging.warning(f"Start command received but ignored because it doesn't have a chat")
      return

    if not self.__check_chat(update.effective_chat.id):
      return

    await context.bot.send_message(chat_id=update.effective_chat.id, text="Start by sending me a message!")

    logging.info(f"Start command executed for chat {update.effective_chat.id}")

  async def __reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
      logging.warning(f"Update received but ignored because it doesn't have a message")
      return

    chat_id = update.message.chat_id

    if not self.__check_chat(chat_id):
      return

    message = await context.bot.send_message(chat_id=chat_id, text="Generating response...")
    text, conversation = await self.__gpt.complete(chat_id, update.message.text)
    await context.bot.edit_message_text(chat_id=chat_id, message_id=message.id, text=text)

    self.__add_timeout_task(conversation, message, text, context.bot)

    logging.info(f"Replied chat {chat_id} with text '{text}'")

  async def __resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      logging.warning(f"Resume command received but ignored because it doesn't have a chat")
      return

    chat_id = update.effective_chat.id

    if not self.__check_chat(chat_id):
      return

    query = update.callback_query
    if not query or not query.data:
      return

    await query.answer()

    conversation_id = int(query.data.split("_")[1])
    conversation = self.__gpt.resume(chat_id, conversation_id)
    if not conversation:
      await context.bot.send_message(chat_id=chat_id, text="Failed to find that conversation. Try sending a new message.")
      return

    text = f"Resuming conversation \"{conversation.title}\":"
    message = await context.bot.send_message(chat_id=chat_id, text=text)

    self.__add_timeout_task(conversation, message, text, context.bot)

    logging.info(f"Resumed conversation {conversation_id} for chat {chat_id}")

  def __add_timeout_task(self, conversation: Conversation, message: TGMessage, text: str, bot):
    if message.chat_id in self.__timeout_tasks:
      self.__timeout_tasks[message.chat_id].cancel()

    self.__timeout_tasks[message.chat_id] = asyncio.create_task(self.__timeout_task(conversation, message, text, bot))

  async def __timeout_task(self, conversation: Conversation, message: TGMessage, text: str, bot):
    await asyncio.sleep(self.__conversation_timeout)

    del self.__timeout_tasks[message.chat_id]
    self.__gpt.start_new(message.chat_id)

    new_text = text + f"\n\nThis conversation is timed out and it was about \"{conversation.title}\". A new conversation has started."
    resume_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Resume this conversation", callback_data=f"resume_{conversation.id}")]])

    await bot.edit_message_text(chat_id=message.chat_id, message_id=message.id, text=new_text, reply_markup=resume_markup)

    logging.info(f"Conversation {conversation.id} timed out")

  async def __new_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      logging.warning(f"New command received but ignored because it doesn't have a chat")
      return

    if not self.__check_chat(update.effective_chat.id):
      return

    self.__gpt.start_new(update.effective_chat.id)

    await context.bot.send_message(chat_id=update.effective_chat.id, text="Starting a new conversation.")

    logging.info(f"Started a new conversation for chat {update.effective_chat.id}")

  def __check_chat(self, chat_id: int):
    if self.__chat_id and chat_id != self.__chat_id:
      logging.info(f"Message received for chat {chat_id} but ignored because it's not the configured chat")
      return False

    return True
