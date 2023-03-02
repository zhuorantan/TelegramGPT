import logging
import openai
from enum import Enum
from typing import TypedDict

class Role(str, Enum):
  SYSTEM = 'system'
  ASSISTANT = 'assistant'
  USER = 'user'


class Message(TypedDict):
  role: Role
  content: str


class MessageHistory:
  __data: dict[int, list[Message]]

  def __init__(self):
    self.__data = {}

  def get(self, chat_id: int) -> list[Message]:
    if chat_id not in self.__data:
      return []

    return self.__data[chat_id]

  def add(self, chat_id: int, message: Message):
    if chat_id not in self.__data:
      self.__data[chat_id] = []

    self.__data[chat_id].append(message)

  def clear(self, chat_id: int):
    if chat_id not in self.__data:
      return
    
    self.__data[chat_id] = []


class GPTClient:
  def __init__(self, api_key: str):
    self.__history = MessageHistory()

    openai.api_key = api_key

  def complete(self, chat_id: int, text: str):
    logging.info(f"Completing message for chat {chat_id}, text: '{text}'")

    messages = self.__get_previous_messages(chat_id)
    messages.append({'role': Role.ASSISTANT, 'content': text})

    logging.debug(f"Current messages for chat {chat_id}: {messages}")

    response = openai.ChatCompletion.create(
      model='gpt-3.5-turbo',
      messages=messages,
    )
    message = response['choices'][0]['message']

    logging.info(f"Completed message for chat {chat_id}, text: '{message}'")

    self.__history.add(chat_id, message)

    return message.content

  def clear(self, chat_id: int):
    self.__history.clear(chat_id)

  def __get_previous_messages(self, chat_id: int):
    messages = self.__history.get(chat_id)
    if len(messages) == 0:
      messages.append({'role': Role.SYSTEM, 'content': 'You are a helpful assistant.'})

    return messages
