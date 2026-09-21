from typing import Optional

from sqlalchemy import Column, event
from sqlmodel import Field, SQLModel

from api.core.models import TimestampModel, UUIDModel

class UserBase(SQLModel):
    email: str = Field(unique=True)
    hashed_password: str
    is_active: bool = Field(default=True)

class User(UserBase, UUIDModel, TimestampModel, table=True):
    __tablename__ = "user"
