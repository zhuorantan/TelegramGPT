from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from gpt import GPTClient
from models import AssistantMessage, Conversation, Role, UserMessage
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ExtBot
from typing import TypedDict, cast

class ChatData(TypedDict):
  conversations: dict[int, Conversation]

@dataclass
class ChatState:
  timeout_task: asyncio.Task|None = None
  current_conversation: Conversation|None = None

@dataclass
class ChatContext:
  chat_id: int
  chat_state: ChatState
  __chat_data: ChatData

  def get_all_conversations(self) -> dict[int, Conversation]:
    if 'conversations' not in self.__chat_data:
      self.__chat_data['conversations'] = {}
    return self.__chat_data['conversations']

  def get_conversation(self, conversation_id: int) -> Conversation|None:
    if 'conversations' not in self.__chat_data:
      self.__chat_data['conversations'] = {}
    return self.__chat_data['conversations'].get(conversation_id)

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

    await self.bot.send_message(chat_id=self.context.chat_id, text="Starting a new conversation.")

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

    text = f"Resuming conversation \"{conversation.title}\":"
    await self.bot.send_message(chat_id=chat_id, text=text)

    last_message = conversation.last_message
    if last_message:
      await self.bot.edit_message_text(chat_id=chat_id, message_id=last_message.id, text=last_message.content)

    self.context.chat_state.current_conversation = conversation

    self.__add_timeout_task()

    logging.info(f"Resumed conversation {conversation.id} for chat {chat_id}")

  async def show_conversation_history(self):
    conversations = list(self.context.get_all_conversations().values())
    text = '\n'.join(f"[/resume_{conversation.id}] {conversation.title} ({conversation.started_at:%Y-%m-%d %H:%M})" for conversation in conversations)

    if not text:
      text = "No conversation history"

    await self.bot.send_message(chat_id=self.context.chat_id, text=text)

    logging.info(f"Showed conversation history for chat {self.context.chat_id}")

  async def __complete(self, conversation: Conversation, sent_message_id: int):
    chat_id = self.context.chat_id
    try:
      message = await self.__gpt.complete(conversation, cast(UserMessage, conversation.last_message), sent_message_id)
      await self.bot.edit_message_text(chat_id=chat_id, message_id=sent_message_id, text=message.content)

      logging.info(f"Replied chat {chat_id} with text '{message}'")
    except Exception as e:
      retry_markup = InlineKeyboardMarkup([[InlineKeyboardButton('Retry', callback_data='retry')]])
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
      conversations = self.context.get_all_conversations()
      conversation = self.__gpt.new_conversation(len(conversations), user_message)
      conversations[conversation.id] = conversation

      return conversation
