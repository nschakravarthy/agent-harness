import fnmatch

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.utils import verify_token

from api.core.config import settings
from api.core.db import async_engine
from api.user.models import User
from api.core.config import settings, PUBLIC_PATHS

# Create a session factory once (no yield, no generator)
AsyncSessionLocal = sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

def is_public_path(path: str) -> bool:
    """Check if request path is in the public whitelist (supports wildcards)."""
    print("Checking public path:", path)
    print("Status", any(fnmatch.fnmatch(path, pattern) for pattern in PUBLIC_PATHS))
    return any(fnmatch.fnmatch(path, pattern) for pattern in PUBLIC_PATHS)

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip authentication for docs or public endpoints
        print("Request path:", request.url.path)
        if is_public_path(request.url.path):
            return await call_next(request)
        async with AsyncSessionLocal() as session:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Token "):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing or invalid Authorization header"},
                )

            token = auth_header.split(" ")[1]

            try:
                token_data = verify_token(token)
                if not token_data:
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or expired token"},
                    )
                
                # Ensure it's an access token (not a refresh token)
                if token_data.get("type") != "access":
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid token type. Access token required."},
                    )
                
                print("Token data:", token_data)
                request.state.user = token_data  # Store user info for downstream handlers
            except Exception:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or expired token"},
                )
            
            statement = select(
                User
            ).where(
                User.uuid == token_data.get("user_id")
            )
            results = await session.execute(statement=statement)
            db_user = results.scalar_one_or_none()
            if not db_user:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "User does not exist"},
                )
            if not db_user.is_active:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "User is inactive"},
                )
            print("Authenticated user:", db_user.uuid)
            request.state.user = db_user.uuid
            return await call_next(request)