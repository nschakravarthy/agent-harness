# -------- Stage 1: Build dependencies with Poetry --------
    FROM python:3.12-slim AS builder

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

    # -------- Stage 2: Run the test suite --------
    FROM builder AS test

    # Runtime deps plus the dev group (pytest, httpx), installed straight into
    # the image's interpreter. Poetry is in non-package mode, so this resolves
    # from the lock without building or installing the repo itself. It runs in
    # /tmp, where the builder stage left pyproject.toml and poetry.lock.
    RUN poetry config virtualenvs.create false \
        && poetry install --no-interaction --no-ansi

    WORKDIR /code
    COPY . /code/

    # A failing test fails the build. The marker file exists only to give the
    # production stage something to COPY: BuildKit prunes any stage the target
    # image does not depend on, so without that reference the tests never run.
    RUN pytest -q && touch /tests-passed

    # -------- Stage 3: Production image --------
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

    # Keeps the test stage in the build graph; see the note there.
    COPY --from=test /tests-passed /tmp/tests-passed
    
    # Copy FastAPI application code
    COPY . /code/
    
    # Expose FastAPI default port
    EXPOSE 8000
    
    # Run Alembic migrations and start the FastAPI app with Uvicorn
    CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
