# -------- Stage 1: Build dependencies with Poetry --------
    FROM python:3.12-slim as builder

    ARG APP_ENV=production

    ENV APP_ENV=${APP_ENV} \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 

    WORKDIR /tmp
    
    # Install Poetry (specify version if desired, e.g., pip install poetry==1.8.2)
    RUN pip install --no-cache-dir poetry==2.3.2 poetry-plugin-export
    
    # Copy dependency files
    COPY pyproject.toml ./
    COPY poetry.lock ./
    
    # Export dependencies to requirements.txt (no hashes for pip compatibility)
    RUN ls -la && poetry export -f requirements.txt --output requirements.txt --without-hashes
    # RUN poetry export -f requirements.txt --output requirements.txt --without-hashes
    
    # -------- Stage 2: Production image --------
    FROM python:3.12-slim

    ENV DB_SERVER=postgres-db \
    DB_PORT=5432 \
    DB_NAME=testdb \
    DB_USER=testadmin \
    DB_PASSWORD=test1234

    WORKDIR /code
    
    # Copy requirements.txt from builder and install dependencies
    COPY --from=builder /tmp/requirements.txt ./
    RUN pip install --no-cache-dir --upgrade -r requirements.txt
    
    # Copy FastAPI application code
    COPY . /code/
    
    # Expose FastAPI default port
    EXPOSE 8000
    
    # Run Alembic migrations and start the FastAPI app with Uvicorn
    CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
