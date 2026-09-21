from fastapi.routing import APIRouter

from api.core.config import Settings
from api.core.models import HealthCheck
from api.user.routes import router as user_router
from api.conversation.routes import router as conversation_router


router = APIRouter()

@router.get("/", response_model=HealthCheck, tags=["status"])
async def health_check() -> HealthCheck:
    settings = Settings()
    return HealthCheck(
        name=settings.TITLE,
        version=settings.VERSION,
        description=settings.DESCRIPTION
    )

router.include_router(user_router, prefix = "/user", tags = ["user"])
router.include_router(conversation_router, prefix = "/conversation", tags = ["conversation"])
