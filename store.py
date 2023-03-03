from dataclasses import dataclass
from models import Conversation, Message

@dataclass
class ChatState:
  conversations: dict[int, Conversation]
  current_conversation: Conversation|None

class Store:
  __data: dict[int, ChatState]

  def __init__(self):
    self.__data = {}

  def get_current_conversation(self, chat_id: int) -> Conversation|None:
    chat_state = self.__data.get(chat_id)
    if not chat_state:
      return None
    return chat_state.current_conversation

  def get_all_conversations(self, chat_id: int) -> list[Conversation]:
    chat_state = self.__data.get(chat_id)
    if not chat_state:
      return []
    return list(chat_state.conversations.values())

  def new_conversation(self, chat_id: int, message: Message, title: str|None) -> Conversation:
    if chat_id not in self.__data:
      self.__data[chat_id] = ChatState({}, None)

    chat_state = self.__data[chat_id]

    conversation = Conversation(len(chat_state.conversations), title, message.timestamp, [message])
    
    chat_state.conversations[conversation.id] = conversation
    chat_state.current_conversation = conversation

    return conversation

  def add_message(self, message: Message, conversation: Conversation):
    conversation.messages.append(message)

  def resume_conversation(self, chat_id: int, conversation_id: int) -> Conversation|None:
    if chat_id not in self.__data:
      return None

    chat_state = self.__data[chat_id]

    conversation = chat_state.conversations.get(conversation_id)
    if not conversation:
      return None

    chat_state.current_conversation = conversation
    return conversation

  def terminate_conversation(self, chat_id: int):
    if chat_id not in self.__data:
      return

    self.__data[chat_id].current_conversation = None
