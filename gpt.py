import asyncio
import logging
from typing import cast
import openai
from models import AssistantMessage, Conversation, Message, Role, SystemMessage, UserMessage

class GPTClient:
  __background_tasks: set[asyncio.Task]

  def __init__(self, api_key: str,  max_message_count: int|None):
    self.__max_message_count = max_message_count
    self.__background_tasks = set()

    openai.api_key = api_key

  async def complete(self, conversation: Conversation, user_message: UserMessage, sent_msg_id: int) -> AssistantMessage:
    logging.info(f"Completing message for conversation {conversation.id}, message: '{user_message}'")

    logging.debug(f"Current conversation for chat {conversation.id}: {conversation}")

    text = await self.__request(conversation.messages)
    assistant_message = AssistantMessage(sent_msg_id, text, user_message.id)

    conversation.messages.append(assistant_message)

    logging.info(f"Completed message for chat {conversation.id}, message: '{assistant_message}'")

    return assistant_message

  async def retry_last_message(self, conversation: Conversation, sent_msg_id: int) -> AssistantMessage|None:
    if conversation.last_message and conversation.last_message.role == Role.ASSISTANT:
      conversation.messages.pop()

    if not conversation.last_message or not conversation.last_message.role == Role.USER:
      return None

    text = await self.__request(conversation.messages)
    assistant_message = AssistantMessage(sent_msg_id, text, cast(UserMessage, conversation.last_message).id)

    conversation.messages.append(assistant_message)

    logging.info(f"Retried message for conversation {conversation.id}, message: '{assistant_message}'")

    return assistant_message

  def new_conversation(self, conversation_id: int, user_message: UserMessage) -> Conversation:
    conversation = Conversation(conversation_id, None, user_message.timestamp, [user_message])

    task = asyncio.create_task(self.__set_title(conversation, user_message))
    self.__background_tasks.add(task)
    task.add_done_callback(self.__background_tasks.discard)

    if self.__max_message_count and len(conversation.messages) > self.__max_message_count:
      conversation.messages = conversation.messages[self.__max_message_count:]

    return conversation

  async def __set_title(self, conversation: Conversation, message: UserMessage):
    prompt = 'You are a title generator. You will receive a message that initiates a conversation. You will reply with only the title of the conversation without any punctuation mark either at the begining or the end.'
    messages = [
      SystemMessage(prompt),
      message,
    ]

    title = await self.__request(messages)
    conversation.title = title

    logging.info(f"Set title for conversation {conversation}: '{title}'")

  async def __request(self, messages: list[Message]) -> str:
    response = openai.ChatCompletion.create(
      model='gpt-3.5-turbo',
      messages=[{'role': message.role, 'content': message.content} for message in messages],
    )
    return response['choices'][0]['message']['content']
