from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import cast

class Role(str, Enum):
  SYSTEM = 'system'
  ASSISTANT = 'assistant'
  USER = 'user'

@dataclass
class Message:
  role: Role
  content: str
  timestamp: datetime

class SystemMessage(Message):
  def __init__(self, content: str, timestamp: datetime|None = None):
    super().__init__(Role.SYSTEM, content, timestamp or datetime.now())

class AssistantMessage(Message):
  id: int

  def __init__(self, id: int, content: str, replied_to: Message, timestamp: datetime|None = None):
    super().__init__(Role.ASSISTANT, content, timestamp or datetime.now())
    self.id = id
    self.replied_to = replied_to
    cast(UserMessage, replied_to).answer = self

class UserMessage(Message):
  id: int
  answer: Message|None

  def __init__(self, id: int, content: str, timestamp: datetime|None = None):
    super().__init__(Role.USER, content, timestamp or datetime.now())
    self.id = id
    self.answer = None

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
