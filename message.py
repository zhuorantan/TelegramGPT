from enum import Enum
from typing import TypedDict

class Role(str, Enum):
  SYSTEM = 'system'
  ASSISTANT = 'assistant'
  USER = 'user'

class Message(TypedDict):
  role: Role
  content: str
