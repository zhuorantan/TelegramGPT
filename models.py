from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

class Role(str, Enum):
  SYSTEM = 'system'
  ASSISTANT = 'assistant'
  USER = 'user'

@dataclass
class Message:
  role: Role
  content: str
  timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class Conversation:
  title: str|None
  started_at: datetime
  messages: list[Message]

  @property
  def last_message(self):
    if len(self.messages) == 0:
      return None
    return self.messages[-1]
