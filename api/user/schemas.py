from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    user_id: str
    access_token: str
    refresh_token: str
    session_id: str
    token_type: str
    expires_in: int  # in seconds

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    session_id: str
    # Optional: the /chat stub returns no reply. The client falls back to a
    # placeholder when this is absent.
    reply: str | None = None