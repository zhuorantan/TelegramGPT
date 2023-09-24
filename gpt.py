import asyncio
from dataclasses import dataclass, field
import logging
import openai
from aiohttp import ClientSession
from models import AssistantMessage, Conversation, Message, SystemMessage, UserMessage
from typing import cast

@dataclass
class GPTOptions:
  api_key: str = field(repr=False)
  model_name: str = 'gpt-3.5-turbo'
  azure_endpoint: str|None = None
  max_message_count: int|None = None

class GPTClient:
  def __init__(self, *, options: GPTOptions):
    self.__model_name = options.model_name
    self.__max_message_count = options.max_message_count
    self.__is_azure = options.azure_endpoint is not None

    openai.api_key = options.api_key
    if options.azure_endpoint:
      openai.api_base = options.azure_endpoint
      openai.api_type = 'azure'
      openai.api_version = "2023-03-15-preview"

    openai.aiosession.set(ClientSession(trust_env=True))

  async def complete(self, conversation: Conversation, user_message: UserMessage, sent_msg_id: int, system_message: SystemMessage|None):
    logging.info(f"Completing message for conversation {conversation.id}, message: '{user_message}'")

    logging.debug(f"Current conversation for chat {conversation.id}: {conversation}")

    assistant_message = None

    async for chunk in self.__stream(([system_message] if system_message else []) + conversation.messages):
      if not assistant_message:
        assistant_message = AssistantMessage(sent_msg_id, '', user_message.id)
        conversation.messages.append(assistant_message)

      assistant_message.content += chunk
      yield assistant_message

    if conversation.title is None and len(conversation.messages) < 3:
      async def set_title(conversation: Conversation):
        prompt = 'You are a title generator. You will receive one or multiple messages of a conversation. You will reply with only the title of the conversation without any punctuation mark either at the begining or the end.'
        messages = [SystemMessage(prompt)] + conversation.messages

        title = await self.__request(messages)
        conversation.title = title

        logging.info(f"Set title for conversation {conversation}: '{title}'")

      asyncio.create_task(set_title(conversation))

    logging.info(f"Completed message for chat {conversation.id}, message: '{assistant_message}'")

  def new_conversation(self, conversation_id: int, user_message: UserMessage) -> Conversation:
    conversation = Conversation(conversation_id, None, user_message.timestamp, [user_message])

    if self.__max_message_count and len(conversation.messages) > self.__max_message_count:
      conversation.messages = conversation.messages[self.__max_message_count:]

    return conversation

  async def __request(self, messages: list[Message]):
    if self.__is_azure:
      task = openai.ChatCompletion.acreate(
        engine=self.__model_name,
        messages=[{'role': message.role, 'content': message.content} for message in messages],
      )
    else:
      task = openai.ChatCompletion.acreate(
        model=self.__model_name,
        messages=[{'role': message.role, 'content': message.content} for message in messages],
      )
    response = await asyncio.wait_for(task, 60)
    return cast(dict, response)['choices'][0]['message']['content']

  async def __stream(self, messages: list[Message]):
    if self.__is_azure:
      task = openai.ChatCompletion.acreate(
        engine=self.__model_name,
        messages=[{'role': message.role, 'content': message.content} for message in messages],
        stream=True,
      )
    else:
      task = openai.ChatCompletion.acreate(
        model=self.__model_name,
        messages=[{'role': message.role, 'content': message.content} for message in messages],
        stream=True,
      )
    async for response in await task:
      content = cast(dict, response)['choices'][0]['delta'].get('content')
      if content:
        yield content
