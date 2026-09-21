import uuid as uuid_pkg
from enum import Enum

from sqlalchemy import String
from sqlmodel import Column, Field

from api.core.models import TimestampModel

class Session(TimestampModel, table = True):
    session_id: uuid_pkg.UUID = Field(
       default_factory=uuid_pkg.uuid4,
       primary_key=True,
       index=True,
       nullable=False
   )
    user_uuid: uuid_pkg.UUID = Field(
       foreign_key="user.uuid",
       index=True,
       nullable=False
   )


class MessageRole(str, Enum):
    user = "user"
    system = "system"
    agent = "agent"


class Message(TimestampModel, table = True):
    message_id: uuid_pkg.UUID = Field(
       default_factory=uuid_pkg.uuid4,
       primary_key=True,
       index=True,
       nullable=False
   )
    session_id: uuid_pkg.UUID = Field(
       foreign_key="session.session_id",
       index=True,
       nullable=False
   )
    content: str = Field(nullable=False)
    # Stored as VARCHAR (not a native PG enum); MessageRole validates the value.
    role: MessageRole = Field(sa_column=Column(String, nullable=False))
