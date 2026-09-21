from urllib.parse import quote_plus

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    TITLE: str = "Nexus Backend"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "FastAPI backend for Nexus, an AI enterprise service management"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    # Postgres connection. Defaults match the postgres-db service in
    # docker-compose.yml so a local `docker compose up -d postgres-db` works
    # with no .env. In the container, the Dockerfile overrides DB_SERVER with
    # the compose service hostname.
    DB_USER: str = "testadmin"
    DB_PASSWORD: str = "test1234"
    DB_SERVER: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "testdb"
    SECRET_KEY: str = "8aHsX-TQ}MbI|mS"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 1  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7 days
    
settings = Settings()

# Postgres only - there is deliberately no SQLite fallback, so a misconfigured
# environment fails loudly instead of silently writing to a local file.
DB_ASYNC_CONNECTION_STR = (
    f"postgresql+asyncpg://{quote_plus(settings.DB_USER)}:{quote_plus(settings.DB_PASSWORD)}"
    f"@{settings.DB_SERVER}:{settings.DB_PORT}/{settings.DB_NAME}"
)

PUBLIC_PATHS = [
    "*/openapi.json",
    "*/docs",
    "*/docs/oauth2-redirect",
    "*/login",
    "*/register",
    "*/refresh",       # Token refresh — called with an expired access token
    "*/health",        # Health check endpoint
    "*/public/*",
    "*/event/",
    "/api/v1/",
    "/api/v1/user/register/",
    "/api/v1/user/login/"            # Wildcard support for public endpoints
]

