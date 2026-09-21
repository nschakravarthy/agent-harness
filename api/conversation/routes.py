from fastapi import Request, Depends
from fastapi.routing import APIRouter
from sqlmodel.ext.asyncio.session import AsyncSession

from api.conversation.models import Session, Message, MessageRole
from api.conversation.schemas import SessionResponse, MessageRequest, MessageResponse
from api.core.db import get_async_session

router = APIRouter()

@router.post("/session", response_model=SessionResponse)
async def create_session(request: Request, session: AsyncSession = Depends(get_async_session)):
    new_session = Session(user_uuid=request.state.user)
    session.add(new_session)
    await session.commit()
    await session.refresh(new_session)
    return SessionResponse(session_id=str(new_session.session_id))


@router.post("/message", response_model=MessageResponse)
async def create_message(data: MessageRequest, session: AsyncSession = Depends(get_async_session)):
    new_message = Message(
        session_id=data.session_id,
        content=data.content,
        role=MessageRole.user,
    )
    session.add(new_message)
    await session.commit()
    await session.refresh(new_message)
    return MessageResponse(
        message_id=str(new_message.message_id),
        session_id=str(new_message.session_id),
        content=new_message.content,
        role=getattr(new_message.role, "value", new_message.role),
        created_at=new_message.created_at,
    )
