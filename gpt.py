import logging
import openai
from message import Role
from history import MessageHistory

class GPTClient:
  def __init__(self, api_key: str, max_message_count: int|None):
    self.__max_message_count = max_message_count
    self.__history = MessageHistory()

    openai.api_key = api_key

  def complete(self, chat_id: int, text: str):
    logging.info(f"Completing message for chat {chat_id}, text: '{text}'")

    messages = self.__get_previous_messages(chat_id)
    messages.append({'role': Role.USER, 'content': text})

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

    elif self.__max_message_count and len(messages) > self.__max_message_count:
      messages = messages[-self.__max_message_count:]

    return messages
