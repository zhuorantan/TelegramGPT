import logging
import openai
from models import Conversation, Message, Role
from store import Store

class GPTClient:
  def __init__(self, api_key: str, max_message_count: int|None):
    self.__max_message_count = max_message_count
    self.__store = Store()

    openai.api_key = api_key

  def complete(self, chat_id: int, text: str):
    logging.info(f"Completing message for chat {chat_id}, text: '{text}'")

    conversation = self.__get_conversation(chat_id, Message(Role.USER, text))

    logging.debug(f"Current conversation for chat {chat_id}: {conversation}")

    response = openai.ChatCompletion.create(
      model='gpt-3.5-turbo',
      messages=[{ 'role': message.role, 'content': message.content } for message in conversation.messages],
    )
    raw_message = response['choices'][0]['message']

    message = Message(raw_message['role'], raw_message['content'])

    logging.info(f"Completed message for chat {chat_id}, text: '{message}'")

    self.__store.add_message(message, conversation)

    return raw_message.content

  def start_new(self, chat_id: int):
    self.__store.terminate_conversation(chat_id)

  def __get_conversation(self, chat_id: int, message: Message) -> Conversation:
    conversation = self.__store.get_current_conversation(chat_id)
    if not conversation:
      conversation = self.__store.new_conversation(chat_id, message, 'foobar')

    if self.__max_message_count and len(conversation.messages) > self.__max_message_count:
      conversation.messages = conversation.messages[-self.__max_message_count:]

    return conversation
