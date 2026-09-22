# The production image cannot be built unless the tests pass. Stage 3 runs
# them; stage 4 copies a file out of stage 3, which is what forces the build
# to go through it. There is no way to reach the runtime image around it.
#
# Only the tiers that need no services run here - `docker build` has no
# Postgres and no server to talk to. The integration and e2e tiers run from
# the `tests` service in docker-compose.yml, which does.

# -------- Stage 1: Resolve dependencies with Poetry --------
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

# Export dependencies to requirements.txt (no hashes for pip compatibility).
# Two sets: runtime only, and runtime plus the dev group that holds pytest.
# Keeping them apart is what keeps pytest out of the production image.
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes \
 && poetry export -f requirements.txt --output requirements-dev.txt --without-hashes --with dev

# -------- Stage 2: Runtime dependencies, shared by test and production --------
FROM python:3.12-slim AS base

ENV DB_SERVER=postgres-db \
    DB_PORT=5432 \
    DB_NAME=testdb \
    DB_USER=testadmin \
    DB_PASSWORD=test1234

WORKDIR /code

# Copy requirements.txt from builder and install dependencies
COPY --from=builder /tmp/requirements.txt ./
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# -------- Stage 3: Run the tests --------
FROM base AS test

# Dev dependencies go in before the source, so editing code does not
# reinstall pytest on every build.
COPY --from=builder /tmp/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . /code/

# An escape hatch for an emergency build: `--build-arg SKIP_TESTS=1`.
# It is off by default and leaves a trace in the image, so a skipped run
# cannot be mistaken for a passing one.
ARG SKIP_TESTS=0

RUN mkdir -p /test-report && \
    if [ "$SKIP_TESTS" = "1" ]; then \
        echo "SKIPPED via --build-arg SKIP_TESTS=1" > /test-report/result; \
    else \
        pytest -m "unit or smoke" --junitxml=/test-report/junit.xml && \
        echo "PASSED" > /test-report/result; \
    fi

# Default command for the compose `tests` service, which does have Postgres
# and a server on its network.
CMD ["pytest", "-m", "integration or e2e"]

# -------- Stage 4: Production image --------
FROM base AS production

# Copy FastAPI application code
COPY . /code/

# This is the gate. Copying from `test` makes that stage part of this build,
# so a failing `pytest` fails `docker build` before the image exists.
COPY --from=test /test-report/result /code/.docker-test-result

# Expose FastAPI default port
EXPOSE 8000

# Run Alembic migrations and start the FastAPI app with Uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
