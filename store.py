from dataclasses import dataclass
from models import Conversation, Message

@dataclass
class ChatState:
  conversations: list[Conversation]
  current_conversation: Conversation|None

class Store:
  __data: dict[int, ChatState]

  def __init__(self):
    self.__data = {}

  def get_current_conversation(self, chat_id: int) -> Conversation|None:
    if chat_id not in self.__data:
      return None

    chat_state = self.__data[chat_id]
    return chat_state.current_conversation

  def new_conversation(self, chat_id: int, message: Message, title: str|None) -> Conversation:
    if chat_id not in self.__data:
      self.__data[chat_id] = ChatState([], None)

    conversation = Conversation(title, message.timestamp, [message])
    
    chat_state = self.__data[chat_id]
    chat_state.conversations.append(conversation)
    chat_state.current_conversation = conversation

    return conversation

  def add_message(self, message: Message, conversation: Conversation):
    conversation.messages.append(message)

  def terminate_conversation(self, chat_id: int):
    chat_state = self.__data[chat_id]
    if not chat_state:
      return

    chat_state.current_conversation = None
