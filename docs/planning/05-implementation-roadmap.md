# LightClaw Implementation Roadmap

## Purpose

This document breaks the project into concrete implementation stages so future agents can extend the codebase step by step instead of attempting the whole system at once.

## Stage 0: Foundation

Status: completed in the current iteration

Deliverables:

- Python project scaffold
- layered package structure
- configuration and logging
- CLI entrypoint
- FastAPI entrypoint
- minimal agent runtime path
- mock provider
- in-memory session and memory stores
- initial tests

## Stage 1: Core Runtime Hardening

Status: in progress, partially completed in the current iteration

Goals:

- replace placeholder runtime behavior with explicit agent loop states
- define request and response envelopes more rigorously
- add error types and policy decision models
- add structured execution logging

Tasks:

1. add domain error classes
2. add execution policy models
3. add richer tool contracts beyond `list_tool_names`
4. support provider tool-call responses
5. add loop limits and timeout handling

Completed so far:

- domain error classes are in place
- execution policy models are in place
- the tool registry now resolves executable tools
- the mock provider can emit tool calls
- the runtime now executes a bounded tool loop
- structured execution logging is in place
- provider and tool timeouts are in place

Remaining:

- strengthen request and response envelopes for future real providers

## Stage 2: Persistence

Status: in progress, partially completed in the current iteration

Goals:

- move from in-memory stores to SQLite-backed persistence

Tasks:

1. add SQLAlchemy models and repositories
2. persist sessions, messages, memories, jobs, and execution logs
3. add migrations
4. keep repository interfaces compatible with the domain layer

Completed so far:

- SQLAlchemy-backed SQLite persistence is in place
- sessions and messages persist through the `SessionStore` interface
- long-term memories persist through the `MemoryStore` interface
- execution logs persist through the `ExecutionLogStore` interface
- scheduled job definitions persist through the `JobStore` interface
- persisted job definitions now include target destination and active skill ids
- bootstrap can switch between `memory` and `sqlite` backends by configuration
- persistence survives container rebuilds in tests
- a lightweight schema version baseline is recorded during database initialization
- versioned SQL migration files are now in place and exposed through CLI commands

Remaining:

- add downgrade support and more advanced operational migration workflows

## Stage 3: Real Providers

Status: completed for the current MVP scope

Goals:

- add real model integrations

Tasks:

1. add OpenAI-compatible provider adapter
2. add Anthropic adapter
3. normalize streaming, token usage, and tool calls
4. add provider configuration profiles

Completed so far:

- provider configuration fields are wired through app settings
- provider configuration validation is in place
- bootstrap can switch between `mock`, `openai_compatible`, and `anthropic`
- an OpenAI-compatible chat completions adapter is in place
- an Anthropic messages adapter is in place
- text responses and tool calls are normalized into internal provider responses
- streaming event parsing is in place for OpenAI-compatible and Anthropic SSE responses
- upstream HTTP errors are wrapped into provider-level exceptions
- provider normalization is covered with transport-level tests

Remaining:

- enrich provider profiles and validation for production use

## Stage 4: Tool Framework

Status: completed for the current MVP scope

Goals:

- replace the placeholder registry with executable tools and policy checks

Tasks:

1. define JSON-schema-backed tool definitions
2. add filesystem read tool
3. add constrained filesystem write tool
4. add constrained shell execution tool
5. add HTTP fetch tool
6. add audit logs and permission checks

Completed so far:

- tools now expose JSON-schema-backed definitions
- filesystem read and write tools are in place
- shell execution is implemented with explicit command allowlists
- HTTP fetch is implemented behind network policy checks
- runtime audit logging records tool execution and policy denial events
- tool arguments are validated against declared schemas before execution
- oversized and sensitive tool outputs are truncated and redacted before exposure
- tool behavior is covered by automated tests

Remaining:

- expand schema coverage beyond the current lightweight validator subset

## Stage 5: HTTP and CLI Hardening

Status: completed for the current MVP scope

Goals:

- make interfaces production-ready enough for MVP

Tasks:

1. add request validation and error mapping
2. add dependency injection cleanup
3. add config-driven provider selection
4. add structured API response models
5. add interactive CLI mode

Completed so far:

- API request and response models are explicit
- domain errors are mapped to stable HTTP error responses
- API bootstrap no longer rebuilds dependencies redundantly
- CLI supports single-turn chat and interactive REPL mode
- CLI errors are converted to user-facing messages instead of raw stack traces
- CLI output now includes tool execution traces for multi-step runs
- interface behavior is covered by API and CLI tests

Remaining:

- add streaming-oriented CLI rendering when provider streaming is exposed through the interface layer

## Stage 6: Telegram Integration

Status: completed for the current MVP scope

Goals:

- validate the multi-channel abstraction with one real external channel

Tasks:

1. add Telegram adapter package
2. normalize inbound Telegram messages
3. map replies back to Telegram
4. add delivery error handling

Completed so far:

- Telegram webhook payloads are normalized into internal channel messages
- Telegram updates are converted into `AgentRequest` flow through a dedicated service
- outbound replies can be mapped to Telegram `sendMessage`
- webhook secret validation is supported
- Telegram adapter, webhook, and sender behavior are covered by tests

Remaining:

- add webhook registration helpers
- handle richer Telegram message types beyond plain text

## Stage 7: Memory

Status: completed for the current MVP scope

Goals:

- move from raw string memories to structured records

Tasks:

1. define memory record schemas
2. add memory write policies
3. add extraction prompts or provider workflow
4. add retrieval ranking rules

Completed so far:

- structured memory record schemas are in place
- memory write policy and deduplication rules are in place
- session-scoped and user-scoped retrieval rules are implemented
- runtime memory context is now built from structured records
- structured memory persistence is covered for both in-memory and SQLite stores
- provider-assisted extraction is integrated into the post-chat path
- extraction writes now reuse the same policy and deduplication flow as manual memory writes
- memory context now applies scope and kind priority ordering

Remaining:

- add more adaptive ranking once retrieval sources grow beyond the current structured-memory set

## Stage 8: Scheduling

Status: completed for the current MVP scope

Goals:

- support autonomous background execution

Tasks:

1. add APScheduler integration
2. add job store abstraction
3. add job execution logs
4. add channel delivery targets for scheduled outputs

Completed so far:

- persisted job definitions can be created, listed, and updated
- jobs can be executed manually through the job service
- due jobs can be matched and run through a lightweight scheduler service
- job execution status and output are persisted
- scheduling and job execution behavior are covered by API, service, and persistence tests
- a long-running scheduler loop can be started and stopped
- API lifecycle can auto-start the scheduler when enabled by configuration
- scheduler status and manual tick controls are exposed through API and CLI

Remaining:

- expand delivery targets beyond the current lightweight channel handling
- consider APScheduler only if cron syntax or operational requirements outgrow the current lightweight scheduler

## Stage 9: Skills

Status: completed for the current MVP scope

Goals:

- add declarative extension loading

Tasks:

1. define skill metadata schema
2. load Markdown and YAML skill packages
3. support dependency checks
4. allow skills to contribute prompts and tools

Completed so far:

- filesystem-backed skill packages now load from `skills/`
- each skill package combines `skill.yaml` metadata with Markdown prompt content
- skill activation checks required environment variables and commands before use
- active skills can contribute prompt fragments to the provider context
- active skills can narrow the exposed tool registry to skill-declared tools
- API and CLI now support explicit skill activation
- scheduled jobs can now declare active skills directly
- skill loading and activation behavior is covered by automated tests

Remaining:

- add richer skill composition and conflict-resolution rules

## Stage 10: MCP

Status: completed for the current MVP scope

Goals:

- connect external MCP tools cleanly

Tasks:

1. add MCP client abstraction
2. map MCP tools into the internal tool framework
3. apply the same policy and audit rules

Completed so far:

- an MCP client abstraction is now in place
- filesystem-backed MCP server manifests can be loaded from `mcp/servers/`
- MCP tools are mapped into the internal tool framework through a dedicated adapter
- MCP tools flow through the same runtime policy checks and audit logging as local tools
- bootstrap composes local tools and MCP tools into one registry
- MCP loading, execution, and policy enforcement are covered by automated tests

Remaining:

- replace the manifest-backed MVP adapter with a real MCP transport when operational requirements justify it
- add richer result normalization for multi-part MCP tool outputs

## Completion Rule

A stage should not be treated as complete until:

- unit tests pass
- at least one integration path is verified
- documentation is updated if contracts changed
