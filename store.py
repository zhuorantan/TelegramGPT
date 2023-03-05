from models import Conversation, Message

class Store:
  __data: dict[int, dict[int, Conversation]]

  def __init__(self):
    self.__data = {}

  def get_all_conversations(self, chat_id: int) -> list[Conversation]:
    conversations = self.__data.get(chat_id)
    if not conversations:
      return []
    return list(conversations.values())

  def new_conversation(self, chat_id: int, message: Message, title: str|None) -> Conversation:
    if chat_id not in self.__data:
      self.__data[chat_id] = {}

    conversations = self.__data[chat_id]

    conversation = Conversation(len(conversations), title, message.timestamp, [message])
    
    conversations[conversation.id] = conversation

    return conversation

  def add_message(self, message: Message, conversation: Conversation):
    conversation.messages.append(message)

  def get_conversation(self, chat_id: int, conversation_id: int) -> Conversation|None:
    conversations = self.__data.get(chat_id)
    if not conversations:
      return None
    return conversations.get(conversation_id)

  def truncate_conversation(self, conversation: Conversation, max_message_count: int):
    conversation.messages = conversation.messages[max_message_count:]

  def set_title(self, conversation: Conversation, title: str):
    conversation.title = title

  def pop_message(self, conversation: Conversation) -> Message:
    return conversation.messages.pop()
