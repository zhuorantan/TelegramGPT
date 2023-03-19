from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from gpt import GPTClient
from models import AssistantMessage, Conversation, Role, SystemMessage, UserMessage
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ExtBot
from typing import TypedDict, cast
from uuid import uuid4

@dataclass
class ConversationMode:
  title: str
  prompt: str
  id: str = field(default_factory=lambda: str(uuid4()))

class ChatData(TypedDict):
  conversations: dict[int, Conversation]
  modes: dict[str, ConversationMode]
  current_mode_id: str|None

@dataclass
class ChatState:
  timeout_task: asyncio.Task|None = None
  current_conversation: Conversation|None = None

  new_mode_title: str|None = None
  editing_mode: ConversationMode|None = None

@dataclass
class ChatContext:
  chat_id: int
  chat_state: ChatState
  __chat_data: ChatData

  @property
  def all_conversations(self) -> dict[int, Conversation]:
    if 'conversations' not in self.__chat_data:
      self.__chat_data['conversations'] = {}
    return self.__chat_data['conversations']

  @property
  def modes(self) -> dict[str, ConversationMode]:
    if 'modes' not in self.__chat_data:
      self.__chat_data['modes'] = {}
    return self.__chat_data['modes']

  @property
  def current_mode(self) -> ConversationMode|None:
    current_mode_id = self.__chat_data.get('current_mode_id')
    if not current_mode_id:
      return None
    return self.modes.get(current_mode_id)

  def get_conversation(self, conversation_id: int) -> Conversation|None:
    if 'conversations' not in self.__chat_data:
      self.__chat_data['conversations'] = {}
    return self.__chat_data['conversations'].get(conversation_id)

  def add_mode(self, mode: ConversationMode):
    if 'modes' not in self.__chat_data:
      self.__chat_data['modes'] = {}
    self.__chat_data['modes'][mode.id] = mode

  def set_current_mode(self, mode: ConversationMode|None):
    self.__chat_data['current_mode_id'] = mode.id if mode else None

class ChatManager:
  def __init__(self, *, gpt: GPTClient, bot: ExtBot, context: ChatContext, conversation_timeout: int|None):
    self.__gpt = gpt
    self.bot = bot
    self.context = context
    self.__conversation_timeout = conversation_timeout

  async def new_conversation(self):
    chat_state = self.context.chat_state
    timeout_job = chat_state.timeout_task
    if timeout_job:
      timeout_job.cancel()
      chat_state.timeout_task = None
    await self.__expire_current_conversation()

    current_mode = self.context.current_mode
    if current_mode:
      text = f"Started a new conversation in mode \"{current_mode.title}\"."
    else:
      text = "Started a new conversation without mode. Send /addmode to create a new mode."

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Change mode", callback_data="/mode")]])
    await self.bot.send_message(chat_id=self.context.chat_id, text=text, reply_markup=reply_markup)

    logging.info(f"Started a new conversation for chat {self.context.chat_id}")

  async def handle_message(self, *, text: str):
    sent_message = await self.bot.send_message(chat_id=self.context.chat_id, text="Generating response...")

    user_message = UserMessage(sent_message.id, text)

    conversation = self.context.chat_state.current_conversation
    if conversation:
      conversation.messages.append(user_message)
    else:
      conversation = self.__create_conversation(user_message)

    await self.__complete(conversation, sent_message.id)

  async def retry_last_message(self):
    chat_id = self.context.chat_id
    conversation = self.context.chat_state.current_conversation
    if not conversation:
      await self.bot.send_message(chat_id=chat_id, text="No conversation to retry")
      return
      
    sent_message = await self.bot.send_message(chat_id=chat_id, text="Regenerating response...")

    if conversation.last_message and conversation.last_message.role == Role.ASSISTANT:
      conversation.messages.pop()

    if not conversation.last_message or not conversation.last_message.role == Role.USER:
      await self.bot.edit_message_text(chat_id=chat_id, message_id=sent_message.id, text="No message to retry")
      return

    await self.__complete(conversation, sent_message.id)

  async def resume(self, *, conversation_id: int):
    chat_id = self.context.chat_id
    conversation = self.context.get_conversation(conversation_id)
    if not conversation:
      await self.bot.send_message(chat_id=chat_id, text="Failed to find that conversation. Try sending a new message.")
      return

    current_mode = self.context.current_mode
    mode_description = f" in mode \"{current_mode.title}\"" if current_mode else ""
    text = f"Resuming conversation \"{conversation.title}\"{mode_description}:"
    await self.bot.send_message(chat_id=chat_id, text=text)

    last_message = conversation.last_message
    if last_message:
      await self.bot.edit_message_text(chat_id=chat_id, message_id=last_message.id, text=last_message.content)

    self.context.chat_state.current_conversation = conversation

    self.__add_timeout_task()

    logging.info(f"Resumed conversation {conversation.id} for chat {chat_id}")

  async def show_conversation_history(self):
    conversations = list(self.context.all_conversations.values())
    text = '\n'.join(f"[/resume_{conversation.id}] {conversation.title} ({conversation.started_at:%Y-%m-%d %H:%M})" for conversation in conversations)

    if not text:
      text = "No conversation history"

    logging.info(f"Sending history for chat {self.context.chat_id}: {text}")

    await self.bot.send_message(chat_id=self.context.chat_id, text=text)

    logging.info(f"Showed conversation history for chat {self.context.chat_id}")

  async def list_modes_for_selection(self):
    modes = list(self.context.modes.values())

    if not modes:
      await self.bot.send_message(chat_id=self.context.chat_id, text="No modes available. Send /addmode to create a new mode.")
      return

    current_mode = self.context.current_mode
    text = f"Current mode: \"{current_mode.title}\". Change to mode:" if current_mode else "Select a mode:"
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(mode.title, callback_data=f"/mode_select_{mode.id}")] for mode in modes] + [[InlineKeyboardButton("Clear", callback_data="/mode_clear")]])
    await self.bot.send_message(chat_id=self.context.chat_id, text=text, reply_markup=reply_markup)

  async def select_mode(self, mode_id: str|None, sent_message_id: int):
    if not mode_id:
      self.context.set_current_mode(None)
      await self.bot.edit_message_text(chat_id=self.context.chat_id, message_id=sent_message_id, text="Cleared mode.")
      return

    mode = self.context.modes.get(mode_id)
    if not mode:
      await self.bot.send_message(chat_id=self.context.chat_id, text="Failed to find that mode. Try sending a new message.")
      return

    self.context.set_current_mode(mode)

    text = f"Changed mode to \"{mode.title}\"."
    await self.bot.edit_message_text(chat_id=self.context.chat_id, message_id=sent_message_id, text=text)

    logging.info(f"Selected mode {mode.id} for chat {self.context.chat_id}")

  async def update_mode_title(self, title: str) -> bool:
    self.context.chat_state.new_mode_title = title
    return True

  async def add_or_edit_mode(self, prompt: str):
    editing_mode = self.context.chat_state.editing_mode
    if editing_mode:
      editing_mode.prompt = prompt
      self.context.chat_state.editing_mode = None

      await self.bot.send_message(chat_id=self.context.chat_id, text="Mode updated.")
    else:
      title = self.context.chat_state.new_mode_title
      self.context.chat_state.new_mode_title = None
      if not title:
        raise Exception("Invalid state")

      mode = ConversationMode(title, prompt)
      self.context.add_mode(mode)

      if not self.context.current_mode:
        self.context.set_current_mode(mode)

      await self.bot.send_message(chat_id=self.context.chat_id, text="Mode added.")

  async def show_modes(self):
    modes = self.context.modes.values()
    if modes:
      text = "Select a mode to edit:"
      reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(mode.title, callback_data=f"/mode_detail_{mode.id}")] for mode in modes])
      await self.bot.send_message(chat_id=self.context.chat_id, text=text, reply_markup=reply_markup)
    else:
      text = "No modes defined. Send /addmode to add a new mode."
      await self.bot.send_message(chat_id=self.context.chat_id, text=text)

    logging.info(f"Showed modes for chat {self.context.chat_id}")

  async def show_mode_detail(self, id: str):
    mode = self.context.modes.get(id)
    if not mode:
      await self.bot.send_message(chat_id=self.context.chat_id, text="Invalid mode.")
      return

    text = f"Mode \"{mode.title}\":\n{mode.prompt}"
    reply_markup = InlineKeyboardMarkup([
                                          [InlineKeyboardButton('Edit', callback_data=f"/mode_edit_{mode.id}"), InlineKeyboardButton('Delete', callback_data=f"/mode_delete_{mode.id}")],
                                        ])
    await self.bot.send_message(chat_id=self.context.chat_id, text=text, reply_markup=reply_markup)

  async def edit_mode(self, id: str) -> bool:
    mode = self.context.modes.get(id)
    if not mode:
      await self.bot.send_message(chat_id=self.context.chat_id, text="Invalid mode.")
      return False

    self.context.chat_state.editing_mode = mode

    await self.bot.send_message(chat_id=self.context.chat_id, text=f"Enter a new prompt for mode \"{mode.title}\":")
    return True

  async def delete_mode(self, id: str, sent_message_id: int):
    mode = self.context.modes.get(id)
    if not mode:
      await self.bot.send_message(chat_id=self.context.chat_id, text="Invalid mode.")
      return

    del self.context.modes[mode.id]

    text = f"Mode \"{mode.title}\" deleted."
    await self.bot.edit_message_text(chat_id=self.context.chat_id, message_id=sent_message_id, text=text)

  async def __complete(self, conversation: Conversation, sent_message_id: int):
    chat_id = self.context.chat_id
    try:
      system_prompt = SystemMessage(self.context.current_mode.prompt) if self.context.current_mode else None
      message = await self.__gpt.complete(conversation, cast(UserMessage, conversation.last_message), sent_message_id, system_prompt)
      await self.bot.edit_message_text(chat_id=chat_id, message_id=sent_message_id, text=message.content)

      logging.info(f"Replied chat {chat_id} with text '{message}'")
    except Exception as e:
      retry_markup = InlineKeyboardMarkup([[InlineKeyboardButton('Retry', callback_data='/retry')]])
      await self.bot.edit_message_text(chat_id=chat_id, message_id=sent_message_id, text="Error generating response", reply_markup=retry_markup)
      logging.error(f"Error generating response for chat {chat_id}: {e}")
    
    self.context.chat_state.current_conversation = conversation

    self.__add_timeout_task()

  def __add_timeout_task(self):
    chat_state = self.context.chat_state
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

      await self.__expire_current_conversation()

    chat_state.timeout_task = asyncio.create_task(time_out_current_conversation())

  async def __expire_current_conversation(self):
    chat_state = self.context.chat_state
    current_conversation = chat_state.current_conversation
    if not current_conversation:
      return

    chat_state.current_conversation = None

    last_message = current_conversation.last_message
    if not last_message or last_message.role != Role.ASSISTANT:
      return
    last_message = cast(AssistantMessage, last_message)

    new_text = last_message.content + f"\n\nThis conversation has expired and it was about \"{current_conversation.title}\". A new conversation has started."
    resume_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Resume this conversation", callback_data=f"/resume_{current_conversation.id}")]])
    await self.bot.edit_message_text(chat_id=self.context.chat_id, message_id=last_message.id, text=new_text, reply_markup=resume_markup)

    logging.info(f"Conversation {current_conversation.id} timed out")

  def __create_conversation(self, user_message: UserMessage) -> Conversation:
    current_conversation = self.context.chat_state.current_conversation
    if current_conversation:
      current_conversation.messages.append(user_message)
      return current_conversation
    else:
      conversations = self.context.all_conversations
      conversation = self.__gpt.new_conversation(len(conversations), user_message)
      conversations[conversation.id] = conversation

      return conversation
