# LightClaw Technical Selection

## 1. Recommended Primary Stack

### Language
Python 3.12+

Reason:

- strong ecosystem for async services, LLM APIs, bots, and scripting
- fast iteration speed
- aligns with the original document direction
- easiest path for tool execution, filesystem work, and MCP integration

### Package and Project Management
- `uv` for dependency management and fast environment setup
- `pyproject.toml` as the single project manifest

### API and Service Runtime
- `FastAPI` for HTTP API
- `Uvicorn` as the ASGI server

Reason:

- clean async support
- strong typing and validation support
- easy health endpoints and docs

### CLI
- `Typer`

Reason:

- simple developer experience
- good fit for local interaction and maintenance commands

## 2. Async and HTTP

- `httpx` for outbound HTTP calls
- built-in `asyncio` as the concurrency base

Reason:

- consistent async model
- simpler than mixing multiple networking abstractions

## 3. Data Modeling and Validation

- `Pydantic v2`

Reason:

- clean schemas for config, messages, tool inputs, and provider normalization
- useful for both runtime validation and generated API docs

## 4. Persistence

### MVP Choice
- `SQLite` with `SQLAlchemy` 2.x and `Alembic`

Reason:

- lowest operational burden
- enough for local and small-team deployments
- easy upgrade path to PostgreSQL later

### Later Upgrade
- PostgreSQL when concurrency, observability, or deployment scale requires it

## 5. Background Jobs and Scheduling

### MVP Choice
- `APScheduler` with cron triggers

Reason:

- simpler and lighter than introducing a full distributed queue at the start
- enough for a modular monolith

### Later Upgrade
- add `Redis` plus a worker queue only when task volume or isolation requires it

## 6. Logging and Observability

- standard `logging` with structured JSON formatting
- health endpoints in FastAPI
- optional `OpenTelemetry` later

Reason:

- logging is mandatory in MVP
- tracing can wait until the runtime becomes more complex

## 7. LLM Provider Integration

### Provider Strategy
- define an internal provider interface
- implement OpenAI-compatible adapter first
- implement Anthropic adapter second
- treat local models as OpenAI-compatible where possible

Reason:

- minimizes branching in the runtime
- reduces provider-specific complexity in the domain layer

## 8. Tools and Sandboxing

### Filesystem
- Python standard library with explicit path restriction checks

### Shell
- `asyncio.create_subprocess_exec` instead of shell string expansion where possible

Reason:

- safer command execution model
- easier policy enforcement and timeout handling

### Web
- `httpx` plus a lightweight readability extraction library only if needed

Recommendation:

- do not overbuild search or scraping in MVP
- start with fetch and plain extraction, then add search adapters later

## 9. Channel Integrations

### MVP
- CLI
- HTTP API
- Telegram

Reason:

- enough to validate the channel abstraction
- Telegram has mature bot support and strong practical value

### Suggested Libraries
- Telegram: `python-telegram-bot` or direct HTTP webhook integration

Recommendation:

- prefer direct, minimal integration if you want tighter control
- prefer the mature SDK if speed of implementation matters more than abstraction purity

## 10. Skills and MCP

### Skills
- filesystem-based skill packages with Markdown instructions and YAML metadata

### MCP
- implement after core tool and provider abstractions are stable

Reason:

- MCP should extend a mature tool model, not define it prematurely

## 11. Testing Strategy

- `pytest`
- `pytest-asyncio`
- integration tests around agent loop, persistence, and tool policy enforcement

Minimum required automated coverage areas:

- provider adapter normalization
- message normalization
- policy rejection paths
- persistence round trips
- scheduler execution flow

## 12. Deployment

### MVP
- local development via `uv`
- Docker image for self-hosted use
- `.env` based configuration for simple deployment

### Later
- Docker Compose for bundled local stack
- Kubernetes only if the system genuinely grows into multiple services

## 13. Summary Decision

The best current implementation choice is:

- Python 3.12+
- FastAPI
- Typer
- Pydantic v2
- SQLAlchemy + SQLite
- APScheduler
- httpx
- async subprocess execution
- modular monolith architecture

This stack is lightweight, practical, and directly aligned with the product goals.
