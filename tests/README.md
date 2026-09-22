# Tests

Four tiers, cheapest first. Each tier is a directory under `tests/`, and
`tests/conftest.py` marks every test with the name of the directory it lives
in — so the marker never has to be repeated on a test function.

| Tier | Directory | Needs | Answers |
|---|---|---|---|
| `unit` | `tests/unit/` | nothing | Is the logic right? |
| `integration` | `tests/integration/` | Postgres | Do the app and the database agree? |
| `e2e` | `tests/e2e/` | a running server | Does the journey a client makes work? |
| `smoke` | `tests/smoke/` | nothing | Is this build wired up and alive? |

Evals are deliberately out of scope for now; when they land they belong in
their own top-level directory, not in here — they measure model quality and
are neither deterministic nor a merge gate.

## Running

```bash
poetry install

pytest                      # everything; tiers with no service are skipped
pytest -m unit              # milliseconds, no I/O, runs anywhere
pytest -m "unit or smoke"   # the pre-commit set
pytest -m integration       # needs Postgres
pytest -m e2e               # needs a server
pytest --cov                # coverage over api/ and harness/
```

Tiers whose backing service is missing **skip with an explanatory message**
rather than fail, so `pytest` stays green on a laptop with nothing running.
CI must not accept that silence:

```bash
TESTS_REQUIRE_SERVICES=1 pytest    # a missing service is now a failure
```

## Docker

`docker build` runs the tests. The production image is built from a stage
that copies a file out of the test stage, so a failing `pytest` fails the
build and the runtime image never exists:

```bash
docker build .          # runs `pytest -m "unit or smoke"` on the way through
```

Only the service-free tiers run there - a `docker build` has no Postgres and
no server to talk to. The other two run from compose, which does:

```bash
docker compose up -d                 # postgres + backend
docker compose run --rm tests        # pytest -m "integration or e2e"
```

Between them the two commands cover the whole suite, 78 + 30, with no test
in neither. The `tests` service sits behind a `test` profile, so a plain
`docker compose up` does not start it; `docker compose run` enables the
profile on its own.

Docker caches the test layer, so an unchanged source tree does not re-run the
suite - the build copies the source in before running pytest, so any code
change invalidates the layer and the tests run again.

For an emergency build with a known-failing suite:

```bash
docker build --build-arg SKIP_TESTS=1 .
```

It is off by default, and it records the skip in `/code/.docker-test-result`
inside the image so a skipped build cannot be mistaken for a passing one.

## Tier notes

### unit

No database, no network, no ASGI app. Covers the transcript value types in
`harness/messages.py` and the parts of `api/` that are pure functions —
password hashing, JWT issuance and verification, the public-path whitelist,
and the database URL built in `api/core/config.py`.

### integration

Drives the real ASGI app through `httpx.ASGITransport` — in-process, no
socket — against a real Postgres.

Why a real database rather than a fake: `AuthMiddleware` builds its own
session factory from `api.core.db.async_engine` at import time, so it cannot
be reached by FastAPI dependency overrides, and every test that crosses the
middleware has to talk to Postgres. The app is Postgres-only by design, so a
different backend would test something the app never runs on.

```bash
docker compose up -d postgres-db
pytest -m integration
```

The test database is **not** the dev database. `tests/conftest.py` overrides
`DB_NAME` to `agent_harness_test` before `api.core.config` is imported — the
only moment that works, since `settings` is a module-level singleton. The
database is created if missing, its schema built from `SQLModel.metadata`,
and its tables truncated between tests. Override the name with
`TEST_DB_NAME`.

### e2e

Nothing here imports the app; these tests know only a base URL and speak
HTTP. That is what makes them the same tests you can point at staging.

```bash
docker compose up -d
E2E_BASE_URL=http://localhost:8000 pytest -m e2e
```

They create their own users with random emails and never truncate anything,
so they are safe to run against an environment whose data you care about.
`E2E_BASE_URL` defaults to `http://localhost:8000`.

### smoke

Shallow, fast, and dependency-free: modules import, the app builds, the
health route answers, the OpenAPI schema generates, every expected route is
mounted, and protected routes reject anonymous callers. This is the tier to
run against a freshly built image or a just-deployed container.

## Conventions

- Test names are sentences about behaviour (`test_an_expired_token_is_rejected`),
  not about method names.
- Assert on observable behaviour. The one exception is integration tests that
  read a row back to prove something was actually persisted.
- Fixtures live in the nearest `conftest.py`. Shared ones (`client`, `api`,
  `registered_user`, `conversation_session`) are per-tier, because the same
  name means a different thing in-process than it does over the wire.
