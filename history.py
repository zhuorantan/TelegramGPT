from message import Message

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
