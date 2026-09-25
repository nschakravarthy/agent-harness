# agent-harness

Building an AI agent harness from scratch — the loop around the model, not the
model itself.

---

## The concept

Three things get conflated constantly, and the confusion is what produces
fragile systems:

| | What it is |
|---|---|
| **Model** | A function. Hand it a context, get back a probability distribution over next tokens. Stateless, goal-less, action-less. |
| **Agent** | A loop coupling that model to bounded state, tools, and a context-management policy. |
| **Harness** | The engineering that makes the loop survive production: turn protocol, context management, tool orchestration, error handling, observability, persistence, permission and budget gates. |

The model is the function. The agent is the loop. The harness is the
engineering.

Almost everything that determines whether an agent is reliable lives in that
third row. A stronger model raises the ceiling on what a single step can do; it
does nothing about truncated tool output, a context window that quietly fills
with noise, or a twelve-step task where each step is 95% reliable. **Harness
quality, not model capability, is what decides whether the thing works.**

This repo builds that harness deliberately, one concern at a time, rather than
inheriting it from a framework and discovering its assumptions later.

## Why the harness is the hard part

Three forces break agents in production. Each one dictates a piece of
infrastructure.

**Context drift.** Context windows are finite, tool outputs are unbounded, and
attention degrades well before the hard limit is reached — relevant detail
buried in the middle of a long context gets used far less reliably than the
same detail at either end. Growing the window doesn't fix it. *What it forces:
compaction, retrieval, and offloading state to a scratchpad instead of letting
the transcript grow without bound.*

**Tools deceive.** A tool returns output truncated with no indication that it
was truncated. A schema underspecifies, so the model guesses. A null could mean
"empty", "missing", or "failed" and the model can't tell which. A call has a
side effect nobody documented. The model believes all of it. *What it forces:
validating results against an envelope, gating calls on schemas, and parsing
defensively rather than trusting shape.*

**Failure compounds.** Per-step accuracy multiplies over a run. 95% per step is
about 60% across ten steps. 85% per step is about 20%. This is the arithmetic
that makes demos look fine and production look broken — and when work is split
across multiple agents, coordination breakdown becomes a leading cause of
failure in its own right. *What it forces: validation at each step, explicit
recovery paths, and keeping scope bounded enough that the exponent stays small.*

## The shape we're targeting

Four axes locate any harness. Where this one aims to sit:

- **Autonomy** — medium. The model directs tool selection inside a bounded loop.
  Not a fixed pipeline with model calls at predetermined points, and not an
  unconstrained agent left to decide everything.
- **State** — session plus durable. Conversations survive restarts.
- **Tools** — roughly a dozen, hand-designed. Deliberately below the point where
  selection accuracy collapses under too much choice.
- **Context** — actively managed. Compaction, retrieval, and scratchpad offload
  rather than appending until something breaks.

Worth being honest about the first axis: a **workflow** — a predefined code path
calling a model at fixed points — is faster, cheaper, and more reliable whenever
the structure of the problem is known ahead of time. An agent only earns its
cost when the control flow genuinely can't be decided in advance. Much of what
gets built as an agent should have been a workflow.

## Status

**The harness does not exist yet.** What's built today is the service shell that
will host it: authentication, durable conversation storage, migrations, and a
web client. There is no agent loop, no provider adapter, and no tool layer.

An earlier LangGraph experiment lived in `workflow/`. It's been removed, along
with its dependencies, so the loop can be built from first principles.

| Area | State |
|---|---|
| FastAPI service, JWT auth, Argon2 password hashing | Built |
| Postgres persistence, SQLModel models, Alembic migrations | Built |
| React + Vite chat client | Built |
| `POST /user/chat` | **Stub** — validates the session header, returns no reply |
| Agent loop, providers, tools, context management | **Not started** |

One consequence worth noting: the durable-state layer, normally the *last* thing
built, is already done. The loop, normally the *first*, isn't started. The
foundation is solid and the thing that sits on it is missing.

## Architecture

What exists today:

```
api/
├── main.py              FastAPI app factory, CORS, lifespan
├── core/
│   ├── config.py        pydantic-settings; Postgres URL (no SQLite fallback)
│   ├── db.py            async engine + session dependency
│   ├── models.py        UUID / timestamp mixins, health check
│   ├── middleware.py    token auth, public-path allowlist
│   └── routes.py        router composition
├── user/                register / login / refresh, JWT + Argon2
└── conversation/        Session and Message models, persistence routes
alembic/                 migrations (Postgres)
frontend/                React + Vite client
```

Where the harness will go:

```
src/harness/
├── agent.py             the loop
├── messages.py          transcripts
├── providers/           base protocol, mock, anthropic, openai
├── tools/               protocol + registry
└── context/             compaction, accounting
```

The harness is a **standalone package**, not FastAPI code. The service depends
on the harness; the harness knows nothing about HTTP, and can be driven from a
test or a script with no server running. That boundary is the point — it keeps
the loop testable and stops web concerns leaking into agent logic.

## How we're building it

Each phase is independently testable and lands before the next one starts.

**1 — The loop.** A `Provider` protocol (`complete(transcript, tools) ->
ProviderResponse`), a `MockProvider` returning scripted responses, and a `run()`
function. The loop does three things per iteration: **ask** the provider,
**classify** the response as a tool call or a final answer, and **bound** the
whole thing with a hard iteration cap so it can't spin forever.

The mock provider comes *first*, deliberately. Scripted responses make the loop
deterministic and testable offline with no API cost and no network — and they
let us exercise failure paths (a malformed tool call, a model that never
terminates) that are hard to trigger against a live model on demand.

**2 — Transcript.** Messages and turns as real types rather than loose dicts.
This is what everything downstream reads and rewrites, so it gets a proper shape
before tools arrive.

**3 — Tools.** A tool protocol, a registry, dispatch, and result validation. The
"tools deceive" defences land here: envelope validation and defensive parsing,
so a lying tool fails loudly instead of quietly poisoning the context.

**4 — Streaming, interruption, and errors.** Partial output, cancelling a run in
flight, and recovering from provider failures without losing the transcript.

**5 — Context management.** Token accounting first, because you can't manage
what you don't measure. Then compaction, a scratchpad for offloading state, and
retrieval to pull back only what the current step needs.

**6 — Tools at scale.** Designing schemas a model can actually use, dynamic
loading once the catalogue outgrows a single prompt, and MCP for tools that come
from outside the codebase.

**7 — Boundaries.** Sandboxing, permission gates, and budget caps — the controls
that decide what the loop is allowed to do and how much it may spend doing it.

**8 — Composition.** Sub-agents, structured plans with verified completion, and
parallel execution over shared state. This is where coordination breakdown shows
up, so it comes after single-agent reliability is solid.

**9 — Production.** Observability and tracing, an eval suite, cost control, and
resumability on top of the durable state already in place.

Real providers (Anthropic, OpenAI) arrive as adapters behind the same protocol,
kept in optional dependency extras so the core carries no vendor lock-in.

**Next up:** phase 1 — the loop, the provider protocol, and the mock provider,
built standalone and only then wired behind `POST /user/chat`.

## Running it

Requires Python 3.12+, Poetry, and Docker.

```bash
docker compose up -d postgres-db     # Postgres 15 on :5432
poetry install                       # installs harness/api editable into the venv
poetry run alembic upgrade head      # create user / session / message tables
poetry run uvicorn api.main:app --reload
```

The API is at `http://localhost:8000/api/v1/`, with docs at `/docs`. Postgres is
the only supported backend — there's deliberately no SQLite fallback, so a
misconfigured environment fails loudly instead of quietly writing to a local
file. Connection defaults match the compose service, so no `.env` is needed for
local work.

The frontend runs separately:

```bash
docker compose up -d frontend        # or: cd frontend && npm install && npm run dev
```

### Endpoints

```
GET  /api/v1/                        health check
POST /api/v1/user/register           create account, returns tokens
POST /api/v1/user/login              returns access + refresh tokens
POST /api/v1/user/refresh            exchange refresh for access token
POST /api/v1/user/chat               stub; returns {session_id}, no reply
POST /api/v1/conversation/session    create a conversation
POST /api/v1/conversation/message    persist a user message
```

Authenticated routes expect `Authorization: Token <access_token>` — note
`Token`, not `Bearer`.

## Further reading

Primary sources behind the claims above:

- Franklin & Graesser (1996), *Is it an Agent, or Just a Program?* — the
  autonomy / reactivity / proactivity / situatedness criteria
- Yao et al. (2022), *ReAct: Synergizing Reasoning and Acting in Language Models*
- Liu et al. (2023), *Lost in the Middle: How Language Models Use Long Contexts*
  — the attention-degradation result
- Cemri et al. (2025), MAST — a failure taxonomy for multi-agent systems
- Anthropic (2024), *Building Effective Agents* — the workflow/agent distinction

## License

MIT — see [LICENSE](LICENSE).
