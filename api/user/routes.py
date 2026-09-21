import uuid as uuid_pkg

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from api.user.schemas import UserResponse, UserCreate, RefreshTokenRequest, RefreshTokenResponse, ChatRequest, ChatResponse
from api.user.services import create_user, login_user, refresh_user_token
from api.core.db import get_async_session

router = APIRouter()

@router.post("/register", response_model=UserResponse)
async def register(data:UserCreate, session: AsyncSession = Depends(get_async_session)):
    response = await create_user(data, session)
    return response

@router.post("/login", response_model=UserResponse)
async def login(data:UserCreate, session: AsyncSession = Depends(get_async_session)):
    response = await login_user(data, session)
    return response

@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(data: RefreshTokenRequest):
    """
    Refresh access token using a valid refresh token.
    """
    response = await refresh_user_token(data.refresh_token)
    return response

@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    x_session_id: str = Header(...),
):
    """
    Acknowledge a chat turn.

    Stub: there is no agent behind this route. The LangGraph workflow that used
    to generate the reply has been removed, so no assistant message is produced
    or persisted. The user's own turn is already stored by
    POST /conversation/message, and the client renders a placeholder when the
    response carries no `reply`.
    """
    try:
        session_uuid = uuid_pkg.UUID(x_session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid x-session-id header")

    return ChatResponse(session_id=str(session_uuid))
