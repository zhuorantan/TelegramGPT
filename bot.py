import asyncio
import logging
from dataclasses import dataclass
from gpt import GPTClient
from models import AssistantMessage, Conversation, Role, UserMessage
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ExtBot, PicklePersistence, filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler
from typing import TypedDict, cast

class ChatData(TypedDict):
  conversations: dict[int, Conversation]

@dataclass
class ChatState:
  timeout_task: asyncio.Task|None = None
  current_conversation: Conversation|None = None

class Bot:
  __chat_states: dict[int, ChatState]

  def __init__(self, gpt: GPTClient, chat_ids: list[int], conversation_timeout: int|None):
    self.__gpt = gpt
    self.__chat_ids = set(chat_ids)
    self.__conversation_timeout = conversation_timeout
    self.__chat_states = {}

  def run(self, token: str, data_path: str):
    persistence = PicklePersistence(data_path)
    app = ApplicationBuilder().token(token).persistence(persistence).concurrent_updates(True).post_init(self.__post_init).build()

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
    chat_data = cast(ChatData, context.chat_data)

    if not self.__check_chat(chat_id):
      return

    sent_message = await context.bot.send_message(chat_id=chat_id, text="Generating response...")

    user_message = UserMessage(update.message.id, update.message.text)

    conversation = self.__get_chat_state(chat_id).current_conversation
    if conversation:
      conversation.messages.append(user_message)
    else:
      conversation = self.__create_conversation(chat_id, chat_data, user_message)

    message = await self.__gpt.complete(conversation, user_message, sent_message.id)
    self.__get_chat_state(chat_id).current_conversation = conversation
    
    await context.bot.edit_message_text(chat_id=chat_id, message_id=sent_message.id, text=message.content)

    self.__add_timeout_task(chat_id, context)

    logging.info(f"Replied chat {chat_id} with text '{message}'")

  async def __retry_last_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
      logging.warning(f"Retry commmand received but ignored because it doesn't have a message")
      return

    chat_id = update.message.chat_id

    if not self.__check_chat(chat_id):
      return

    conversation = self.__get_chat_state(chat_id).current_conversation
    if not conversation:
      await context.bot.send_message(chat_id=chat_id, text="No conversation to retry")
      return
      
    sent_message = await context.bot.send_message(chat_id=chat_id, text="Regenerating response...")
    message = await self.__gpt.retry_last_message(conversation, sent_message.id)
    if not message:
      await context.bot.edit_message_text(chat_id=chat_id, message_id=sent_message.id, text="No message to retry")
      return

    await context.bot.edit_message_text(chat_id=chat_id, message_id=sent_message.id, text=message.content)

    self.__add_timeout_task(chat_id, context)

    logging.info(f"Regenerated chat {chat_id} with text '{message}'")

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

    conversation = self.__get_conversation(cast(ChatData, context.chat_data), conversation_id)
    if not conversation:
      await context.bot.send_message(chat_id=chat_id, text="Failed to find that conversation. Try sending a new message.")
      return

    text = f"Resuming conversation \"{conversation.title}\":"
    await context.bot.send_message(chat_id=chat_id, text=text)

    self.__get_chat_state(chat_id).current_conversation = conversation

    self.__add_timeout_task(chat_id, context)

    logging.info(f"Resumed conversation {conversation_id} for chat {chat_id}")

  async def __new_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      logging.warning(f"New command received but ignored because it doesn't have a chat")
      return

    chat_id = update.effective_chat.id

    if not self.__check_chat(chat_id):
      return

    chat_state = self.__get_chat_state(chat_id)

    timeout_job = chat_state.timeout_task
    if timeout_job:
      timeout_job.cancel()
      chat_state.timeout_task = None
    await self.__expire_current_conversation(chat_id, context.bot)

    await context.bot.send_message(chat_id=chat_id, text="Starting a new conversation.")

    logging.info(f"Started a new conversation for chat {chat_id}")

  async def __show_conversation_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      logging.warning(f"New command received but ignored because it doesn't have a chat")
      return

    if not self.__check_chat(update.effective_chat.id):
      return

    conversations = self.__get_all_conversations(cast(ChatData, context.chat_data))
    text = '\n'.join(f"[/resume_{conversation.id}] {conversation.title} ({conversation.started_at:%Y-%m-%d %H:%M})" for conversation in conversations)

    if not text:
      text = "No conversation history"

    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    logging.info(f"Showed conversation history for chat {update.effective_chat.id}")

  def __add_timeout_task(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    chat_state = self.__get_chat_state(chat_id)
      
    last_task = chat_state.timeout_task
    if last_task:
      last_task.cancel()
      chat_state.timeout_task = None

    timeout = self.__conversation_timeout
    if not timeout:
      return

    async def time_out_current_conversation():
      await asyncio.sleep(timeout)
      chat_state.timeout_task = None

      await self.__expire_current_conversation(chat_id, context.bot)

    chat_state.timeout_task = context.application.create_task(time_out_current_conversation())

  async def __expire_current_conversation(self, chat_id: int, bot: ExtBot):
    chat_state = self.__get_chat_state(chat_id)
    current_conversation = chat_state.current_conversation
    if not current_conversation:
      return

    self.__get_chat_state(chat_id).current_conversation = None

    last_message = current_conversation.last_message
    if not last_message or last_message.role != Role.ASSISTANT:
      return
    last_message = cast(AssistantMessage, last_message)

    new_text = last_message.content + f"\n\nThis conversation has expired and it was about \"{current_conversation.title}\". A new conversation has started."
    resume_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Resume this conversation", callback_data=f"resume_{current_conversation.id}")]])
    await bot.edit_message_text(chat_id=chat_id, message_id=last_message.id, text=new_text, reply_markup=resume_markup)

    logging.info(f"Conversation {current_conversation.id} timed out")

  def __check_chat(self, chat_id: int):
    if self.__chat_ids and not chat_id in self.__chat_ids:
      logging.info(f"Message received for chat {chat_id} but ignored because it's not the configured chat")
      return False

    return True

  def __create_conversation(self, chat_id: int, chat_data: ChatData, user_message: UserMessage) -> Conversation:
    if 'conversations' not in chat_data:
      chat_data['conversations'] = {}

    chat_state = self.__get_chat_state(chat_id)
    current_conversation = chat_state.current_conversation
    if current_conversation:
      current_conversation.messages.append(user_message)
      return current_conversation
    else:
      conversations = chat_data['conversations']
      conversation = self.__gpt.new_conversation(len(conversations), user_message)
      conversations[conversation.id] = conversation

      return conversation

  def __get_all_conversations(self, chat_data: ChatData) -> list[Conversation]:
    if 'conversations' not in chat_data:
      chat_data['conversations'] = {}
    return list(chat_data['conversations'].values())

  def __get_conversation(self, chat_data: ChatData, conversation_id: int) -> Conversation|None:
    if 'conversations' not in chat_data:
      chat_data['conversations'] = {}
    return chat_data['conversations'].get(conversation_id)

  def __get_chat_state(self, chat_id: int) -> ChatState:
    if chat_id not in self.__chat_states:
      self.__chat_states[chat_id] = ChatState()
    return self.__chat_states[chat_id]
