import logging
from dataclasses import dataclass
from gpt import GPTClient
from models import Conversation
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, JobQueue, filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler
from typing import cast

@dataclass
class TimeoutJobData:
  conversation: Conversation
  message_id: int
  text: str

class Bot:
  def __init__(self, gpt: GPTClient, chat_id: str|None, conversation_timeout: int|None):
    self.__gpt = gpt
    self.__chat_id = chat_id
    self.__conversation_timeout = conversation_timeout
    self.__timeout_jobs = {}

  def run(self, token: str):
    app = ApplicationBuilder().token(token).concurrent_updates(True).post_init(self.__post_init).build()

    app.add_handler(CommandHandler('start', self.__start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.__reply))
    app.add_handler(CallbackQueryHandler(self.__resume))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r'\/resume_\d+'), self.__resume))
    app.add_handler(CommandHandler('new', self.__new_conversation))
    app.add_handler(CommandHandler('history', self.__show_conversation_history))
    app.add_handler(CommandHandler('retry', self.__retry_last_message))

    app.run_polling()

  @staticmethod
  async def __post_init(app: Application):
    commands = [
      ('new', "Start a new conversation"),
      ('history', "Show previous conversations"),
      ('retry', "Regenerate response for last message"),
    ]
    await app.bot.set_my_commands(commands)
    logging.info("Set command list")

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

    placeholder_message = await context.bot.send_message(chat_id=chat_id, text="Generating response...")
    message, conversation = await self.__gpt.complete(chat_id, update.message.id, update.message.text)
    sent_message = await context.bot.send_message(chat_id=chat_id, text=message.content)
    await context.bot.delete_message(chat_id=chat_id, message_id=placeholder_message.message_id)
    self.__gpt.assign_message_id(message, sent_message.id)

    self.__add_timeout_task(context.job_queue, chat_id, TimeoutJobData(conversation, sent_message.id, message.content))

    logging.info(f"Replied chat {chat_id} with text '{message}'")

  async def __resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      logging.warning(f"Resume command received but ignored because it doesn't have a chat")
      return

    chat_id = update.effective_chat.id

    if not self.__check_chat(chat_id):
      return

    conversation_id = None
    query = update.callback_query

    if query and query.data and query.data.startswith('resume_'):
      await query.answer()
      conversation_id = int(query.data.split('_')[1])
    elif update.message and update.message.text and update.message.text.startswith('/resume_'):
      conversation_id = int(update.message.text.split('_')[1])
    else:
      raise Exception("Invalid parameters")

    conversation = self.__gpt.resume(chat_id, conversation_id)
    if not conversation:
      await context.bot.send_message(chat_id=chat_id, text="Failed to find that conversation. Try sending a new message.")
      return

    text = f"Resuming conversation \"{conversation.title}\":"
    message = await context.bot.send_message(chat_id=chat_id, text=text)

    self.__add_timeout_task(context.job_queue, chat_id, TimeoutJobData(conversation, message.id, text))

    logging.info(f"Resumed conversation {conversation_id} for chat {chat_id}")

  def __add_timeout_task(self, job_queue: JobQueue|None, chat_id: int, data: TimeoutJobData):
    if chat_id in self.__timeout_jobs:
      if not self.__timeout_jobs[chat_id].removed:
        self.__timeout_jobs[chat_id].schedule_removal()
      del self.__timeout_jobs[chat_id]

    if not job_queue:
      raise Exception("Job Queue not exists")

    if not self.__conversation_timeout:
      return

    self.__timeout_jobs[chat_id] = job_queue.run_once(self.__time_out_conversation, self.__conversation_timeout, data, chat_id=chat_id)

  async def __time_out_conversation(self, context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not context.job.data:
      raise Exception("Invalid parameters")

    chat_id = context.job.chat_id
    data = cast(TimeoutJobData, context.job.data)

    del self.__timeout_jobs[chat_id]
    self.__gpt.start_new(chat_id)

    new_text = data.text + f"\n\nThis conversation has timed out and it was about \"{data.conversation.title}\". A new conversation has started."
    resume_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Resume this conversation", callback_data=f"resume_{data.conversation.id}")]])

    await context.bot.edit_message_text(chat_id=chat_id, message_id=data.message_id, text=new_text, reply_markup=resume_markup)

    logging.info(f"Conversation {data.conversation.id} timed out")

  async def __new_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      logging.warning(f"New command received but ignored because it doesn't have a chat")
      return

    if not self.__check_chat(update.effective_chat.id):
      return

    self.__gpt.start_new(update.effective_chat.id)

    timeout_job = self.__timeout_jobs.get(update.effective_chat.id)
    if timeout_job:
      timeout_job.run(context.application)

    await context.bot.send_message(chat_id=update.effective_chat.id, text="Starting a new conversation.")

    logging.info(f"Started a new conversation for chat {update.effective_chat.id}")

  async def __show_conversation_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      logging.warning(f"New command received but ignored because it doesn't have a chat")
      return

    if not self.__check_chat(update.effective_chat.id):
      return

    conversations = self.__gpt.get_all_conversations(update.effective_chat.id)
    text = '\n'.join(f"[/resume_{conversation.id}] {conversation.title} ({conversation.started_at:%Y-%m-%d %H:%M})" for conversation in conversations)

    if not text:
      text = "No conversation history"

    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    logging.info(f"Showed conversation history for chat {update.effective_chat.id}")

  async def __retry_last_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
      logging.warning(f"Retry commmand received but ignored because it doesn't have a message")
      return

    chat_id = update.message.chat_id

    if not self.__check_chat(chat_id):
      return

    placeholder_message = await context.bot.send_message(chat_id=chat_id, text="Regenerating response...")

    result = await self.__gpt.retry_last_message(chat_id)
    if not result:
      await context.bot.edit_message_text(chat_id=chat_id, message_id=placeholder_message.id, text="No message to retry")
      return
    message, conversation = result

    sent_message = await context.bot.send_message(chat_id=chat_id, text=message.content)
    await context.bot.delete_message(chat_id=chat_id, message_id=placeholder_message.id)
    self.__gpt.assign_message_id(message, sent_message.id)

    self.__add_timeout_task(context.job_queue, chat_id, TimeoutJobData(conversation, sent_message.id, message.content))

    logging.info(f"Regenerated chat {chat_id} with text '{message}'")

  def __check_chat(self, chat_id: int):
    if self.__chat_id and chat_id != self.__chat_id:
      logging.info(f"Message received for chat {chat_id} but ignored because it's not the configured chat")
      return False

    return True
