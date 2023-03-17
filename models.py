from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class Role(str, Enum):
  SYSTEM = 'system'
  ASSISTANT = 'assistant'
  USER = 'user'

@dataclass
class Message:
  id: int
  role: Role
  content: str
  timestamp: datetime

class SystemMessage(Message):
  def __init__(self, content: str, timestamp: datetime|None = None):
    super().__init__(-1, Role.SYSTEM, content, timestamp or datetime.now())

class AssistantMessage(Message):
  replied_to_id: int

  def __init__(self, id: int, content: str, replied_to_id: int, timestamp: datetime|None = None):
    super().__init__(id, Role.ASSISTANT, content, timestamp or datetime.now())
    self.id = id
    self.replied_to_id = replied_to_id

class UserMessage(Message):
  answer_id: int|None

  def __init__(self, id: int, content: str, timestamp: datetime|None = None):
    super().__init__(id, Role.USER, content, timestamp or datetime.now())
    self.id = id
    self.answer_id = None

@dataclass
class Conversation:
  id: int
  title: str|None
  started_at: datetime
  messages: list[Message]

  @property
  def last_message(self):
    if len(self.messages) == 0:
      return None
    return self.messages[-1]
