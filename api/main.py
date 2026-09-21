from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
import logging

from api.core.config import settings
from api.core.routes import router as main_router
from api.core.middleware import AuthMiddleware

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Setup memory in app state
    """
    logger.info("Setting up episodic and semantic memory...")
    yield
    
    # Cleanup on shutdown
    logger.info("Application shutdown")

def get_application() -> FastAPI:
    app = FastAPI(
        title=settings.TITLE,
        version = settings.VERSION,
        description = settings.DESCRIPTION,
        debug = settings.DEBUG,
        openapi_url = f"{settings.API_PREFIX}/openapi.json",
        lifespan =  lifespan
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins (you can specify specific origins if needed)
        allow_methods=["*"],  # Allow all HTTP methods
        allow_headers=["*"],  # Allow all headers
    )

    app.add_middleware(AuthMiddleware)

    app.include_router(main_router, prefix=settings.API_PREFIX)

    return app

app = get_application()