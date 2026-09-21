import uuid as uuid_pkg
from datetime import datetime

from pydantic import BaseModel

class SessionResponse(BaseModel):
    session_id: str


class MessageRequest(BaseModel):
    session_id: uuid_pkg.UUID
    content: str


class MessageResponse(BaseModel):
    message_id: str
    session_id: str
    content: str
    role: str
    created_at: datetime
