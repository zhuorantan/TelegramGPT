import asyncio
from enum import Enum
import logging
from chat import ChatData, ChatManager, ChatState, ChatContext
from dataclasses import dataclass
from gpt import GPTClient
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ConversationHandler, PicklePersistence, filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler
from telegram.warnings import PTBUserWarning
from typing import cast
from warnings import filterwarnings

async def __start(_: Update, chat_manager: ChatManager):
  chat_id = chat_manager.context.chat_id

  await chat_manager.bot.send_message(chat_id=chat_id, text="Start by sending me a message!")

  logging.info(f"Start command executed for chat {chat_id}")

async def __handle_message(update: Update, chat_manager: ChatManager):
  if not update.message or not update.message.text:
    logging.warning(f"Update received but ignored because it doesn't have a message")
    return

  await chat_manager.handle_message(text=update.message.text)

async def __retry_last_message(update: Update, chat_manager: ChatManager):
  query = update.callback_query
  if query:
    await query.answer()
    if query.message:
      await chat_manager.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
  await chat_manager.retry_last_message()

async def __resume(update: Update, chat_manager: ChatManager):
  query = update.callback_query

  if query and query.data and query.data.startswith('/resume_'):
    await query.answer()
    conversation_id = int(query.data.split('_')[1])
  elif update.message and update.message.text and update.message.text.startswith('/resume_'):
    conversation_id = int(update.message.text.split('_')[1])
  else:
    raise Exception("Invalid parameters")

  await chat_manager.resume(conversation_id=conversation_id)

async def __new_conversation(_: Update, chat_manager: ChatManager):
  await chat_manager.new_conversation()

async def __show_conversation_history(_: Update, chat_manager: ChatManager):
  await chat_manager.show_conversation_history()

async def __set_mode(update: Update, chat_manager: ChatManager):
  if update.callback_query:
    await update.callback_query.answer()
  await chat_manager.list_modes_for_selection()

async def __edit_modes(_: Update, chat_manager: ChatManager):
  await chat_manager.show_modes()

async def __mode_show_detail(update: Update, chat_manager: ChatManager):
  query = update.callback_query
  if query and query.data and query.data.startswith('/mode_detail_'):
    await query.answer()
    mode_id = query.data[len('/mode_detail_'):]
  else:
    raise Exception("Invalid parameters")

  await chat_manager.show_mode_detail(mode_id)

async def __mode_select(update: Update, chat_manager: ChatManager):
  query = update.callback_query
  if query and query.data and query.data.startswith('/mode_select_') and query.message:
    await query.answer()
    mode_id = query.data[len('/mode_select_'):]
  else:
    raise Exception("Invalid parameters")

  await chat_manager.select_mode(mode_id, query.message.id)

async def __mode_delete(update: Update, chat_manager: ChatManager):
  query = update.callback_query
  if query and query.data and query.data.startswith('/mode_delete_') and query.message:
    await query.answer()
    mode_id = query.data[len('/mode_delete_'):]
  else:
    raise Exception("Invalid parameters")

  await chat_manager.delete_mode(mode_id, query.message.id)

async def __mode_toggle_default(update: Update, chat_manager: ChatManager):
  query = update.callback_query
  if query and query.data and query.data.startswith('/mode_toggle_default_') and query.message:
    await query.answer()
    mode_id = query.data[len('/mode_toggle_default_'):]
  else:
    raise Exception("Invalid parameters")

  await chat_manager.toggle_default_mode(mode_id, query.message.id)


class ModeEditState(Enum):
  INIT = 0
  ENTER_TITLE = 1
  ENTER_PROMPT = 2

async def __mode_add_start(_: Update, chat_manager: ChatManager) -> ModeEditState:
  chat_id = chat_manager.context.chat_id
  await chat_manager.bot.send_message(chat_id=chat_id, text="Enter a title for the new mode:")

  return ModeEditState.ENTER_TITLE

async def __mode_edit_start(update: Update, chat_manager: ChatManager) -> ModeEditState|None:
  query = update.callback_query
  if query and query.data and query.data.startswith('/mode_edit_'):
    await query.answer()
    mode_id = query.data[len('/mode_edit_'):]
  else:
    raise Exception("Invalid parameters")

  if not await chat_manager.edit_mode(mode_id):
    return

  return ModeEditState.ENTER_PROMPT

async def __mode_enter_title(update: Update, chat_manager: ChatManager) -> ModeEditState|None:
  if not update.message or not update.message.text:
    await chat_manager.bot.send_message(chat_id=chat_manager.context.chat_id, text="Invalid title. Please try again.")
    logging.warning(f"Update received but ignored because it doesn't have a message")
    return

  if not await chat_manager.update_mode_title(update.message.text):
    return

  await chat_manager.bot.send_message(chat_id=chat_manager.context.chat_id, text="Enter a prompt for the new mode:")

  return ModeEditState.ENTER_PROMPT

async def __mode_enter_prompt(update: Update, chat_manager: ChatManager) -> int|None:
  if not update.message or not update.message.text:
    await chat_manager.bot.send_message(chat_id=chat_manager.context.chat_id, text="Invalid prompt. Please try again.")
    logging.warning(f"Update received but ignored because it doesn't have a message")
    return

  await chat_manager.add_or_edit_mode(update.message.text)

  return ConversationHandler.END

async def __mode_add_cancel(_: Update, chat_manager: ChatManager) -> int:
  await chat_manager.bot.send_message(chat_id=chat_manager.context.chat_id, text="Mode creation cancelled.")

  return ConversationHandler.END


@dataclass
class WebhookInfo:
  listen_address: str
  url: str|None

async def __post_init(app: Application):
  commands = [
    ('new', "Start a new conversation"),
    ('history', "Show previous conversations"),
    ('retry', "Regenerate response for last message"),
    ('mode', "Select a mode for current conversation"),
    ('editmodes', "Manage modes"),
    ('addmode', "Create a new mode"),
  ]
  await app.bot.set_my_commands(commands)
  logging.info("Set command list")

def __create_callback(gpt: GPTClient, chat_tasks: dict[int, asyncio.Task], allowed_chat_ids: set[int], conversation_timeout: int|None, chat_states: dict[int, ChatState], callback):
  async def invoke(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    if chat_id not in chat_states:
      chat_states[chat_id] = ChatState()
    chat_state = chat_states[chat_id]

    chat_data = cast(ChatData, context.chat_data)
    chat_context = ChatContext(chat_id, chat_state, chat_data)

    chat_manager = ChatManager(gpt=gpt, bot=context.bot, context=chat_context, conversation_timeout=conversation_timeout)

    return await callback(update, chat_manager)

  async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      logging.warning(f"Message received but ignored because it doesn't have a chat")
      return

    chat_id = update.effective_chat.id

    if len(allowed_chat_ids) > 0 and not chat_id in allowed_chat_ids:
      logging.info(f"Message received for chat {chat_id} but ignored because it's not the configured chat")
      return

    current_task = chat_tasks.get(chat_id)
    async def task():
      if current_task:
        await current_task
      return await invoke(update, context, chat_id)

    chat_tasks[chat_id] = asyncio.create_task(task())
    result = await chat_tasks[chat_id]
    if chat_id in chat_tasks:
      del chat_tasks[chat_id]

    return result

  return handler

def run(token: str, gpt: GPTClient, chat_ids: list[int], conversation_timeout: int|None, data_path: str|None, webhook_info: WebhookInfo|None):
  chat_tasks = {}
  allowed_chat_ids = set(chat_ids)
  chat_states = {}

  def create_callback(callback):
    return __create_callback(gpt, chat_tasks, allowed_chat_ids, conversation_timeout, chat_states, callback)

  app_builder = ApplicationBuilder().token(token).post_init(__post_init)
  if data_path:
    persistence = PicklePersistence(data_path)
    app_builder.persistence(persistence)
  app = app_builder.build()

  filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

  app.add_handler(CommandHandler('start', create_callback(__start), block=False))

  app.add_handler(CommandHandler('new', create_callback(__new_conversation), block=False))

  app.add_handler(CommandHandler('retry', create_callback(__retry_last_message), block=False))
  app.add_handler(CallbackQueryHandler(create_callback(__retry_last_message), pattern=r'^/retry$', block=False))

  app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r'\/resume_\d+'), create_callback(__resume), block=False))
  app.add_handler(CallbackQueryHandler(create_callback(__resume), pattern=r'^\/resume_\d+$', block=False))

  app.add_handler(CommandHandler('history', create_callback(__show_conversation_history), block=False))

  app.add_handler(CommandHandler('mode', create_callback(__set_mode), block=False))
  app.add_handler(CallbackQueryHandler(create_callback(__set_mode), pattern=r'^/mode$', block=False))
  app.add_handler(CommandHandler('editmodes', create_callback(__edit_modes), block=False))
  app.add_handler(CallbackQueryHandler(create_callback(__mode_show_detail), pattern=r'\/mode_detail_.+', block=False))
  app.add_handler(CallbackQueryHandler(create_callback(__mode_select), pattern=r'\/mode_select_.+', block=False))
  app.add_handler(CallbackQueryHandler(create_callback(__mode_delete), pattern=r'\/mode_delete_.+', block=False))
  app.add_handler(CallbackQueryHandler(create_callback(__mode_toggle_default), pattern=r'\/mode_toggle_default_.+', block=False))

  app.add_handler(ConversationHandler(
                    entry_points=[
                      CommandHandler('addmode', create_callback(__mode_add_start), block=False),
                      CallbackQueryHandler(create_callback(__mode_edit_start), pattern=r'\/mode_edit_.+', block=False),
                    ],
                    states={
                      ModeEditState.ENTER_TITLE: [MessageHandler(filters.UpdateType.MESSAGE & (~filters.COMMAND), create_callback(__mode_enter_title), block=False)],
                      ModeEditState.ENTER_PROMPT: [MessageHandler(filters.UpdateType.MESSAGE & (~filters.COMMAND), create_callback(__mode_enter_prompt), block=False)],
                    },
                    fallbacks=[CommandHandler('cancel', create_callback(__mode_add_cancel), block=False)],
                  ))

  app.add_handler(MessageHandler(filters.UpdateType.MESSAGE & (~filters.COMMAND), create_callback(__handle_message), block=False))

  if webhook_info:
    parts = webhook_info.listen_address.split(':')
    host = parts[0]
    port = int(parts[1] if len(parts) > 1 else 80)
    url = webhook_info.url or f"https://{webhook_info.listen_address}"
    app.run_webhook(host, port, webhook_url=url)
  else:
    app.run_polling()
