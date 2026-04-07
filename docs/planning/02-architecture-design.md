# LightClaw Architecture Design

## 1. Architecture Goals

The architecture should optimize for:

- low implementation complexity
- strong extension boundaries
- async IO performance
- channel and provider independence
- safe execution of tool-enabled agent actions

## 2. Recommended High-Level Architecture

Use a layered modular monolith for the first version.

This is the right tradeoff because:

- the project is early and likely to change quickly
- distributed services would add operational complexity too early
- the system still needs clean boundaries for future extraction

## 3. Layers

### 3.1 Interfaces Layer
Responsible for protocol and platform entrypoints.

Components:

- CLI adapter
- HTTP API server
- Telegram adapter
- future chat platform adapters
- WebSocket gateway

Responsibilities:

- receive external input
- normalize it into internal command/message objects
- deliver outbound responses
- handle channel-specific authentication and transport details

### 3.2 Application Layer
Responsible for orchestration and use-case flow.

Components:

- message dispatch service
- agent session service
- background job service
- scheduler service
- policy enforcement service
- memory coordination service

Responsibilities:

- coordinate domain objects
- manage transactions and retries
- keep policies and workflows explicit
- prevent interfaces from talking directly to infrastructure details

### 3.3 Domain Layer
Responsible for core business rules and contracts.

Core modules:

- `AgentRuntime`
- `ToolRegistry`
- `SkillRegistry`
- `MemoryStore` interfaces
- `SessionStore` interfaces
- `Provider` interfaces
- `ChannelMessage` models
- `ExecutionPolicy` models

This layer must not depend on transport SDKs or provider SDKs.

### 3.4 Infrastructure Layer
Responsible for concrete adapters.

Components:

- OpenAI-compatible provider adapter
- Anthropic adapter
- SQLite repositories
- Redis adapter if introduced later
- MCP client adapter
- HTTP client
- filesystem and shell tool executors
- logging and metrics backends

## 4. Core Runtime Flow

### 4.1 Interactive Message Flow
1. A channel adapter receives a message.
2. The interface layer normalizes the payload into an internal message object.
3. The application layer resolves user, session, and policy context.
4. The application layer loads recent history and relevant memory.
5. The agent runtime builds the model input.
6. The provider returns either a final answer or a tool call request.
7. Tool execution is checked against policy, executed, and logged.
8. Observations are appended and the loop continues until a reply is produced or a limit is hit.
9. The response is persisted and delivered through the originating channel.

### 4.2 Scheduled Task Flow
1. The scheduler triggers a job definition.
2. The application layer constructs an internal task request.
3. The agent runtime executes with job-scoped policy and context.
4. Outputs are saved and optionally delivered to one or more channels.
5. Failures are retried based on job policy and logged for review.

## 5. Message Normalization Design

Use a single internal message contract with at least:

- `message_id`
- `channel_type`
- `channel_user_id`
- `channel_conversation_id`
- `session_id`
- `text`
- `attachments`
- `timestamp`
- `metadata`

Why this matters:

- the agent core should not care whether the message came from CLI or Telegram
- persistence and replay become consistent
- later analytics and debugging become simpler

## 6. Tool Execution Model

Treat every tool call as a governed execution unit.

Each tool definition should include:

- stable name
- JSON schema input
- JSON schema output
- timeout
- side-effect classification
- required permission scope
- human-readable description for the model

Recommended policy classes:

- `read_only`
- `workspace_write`
- `network_access`
- `process_exec`
- `admin_only`

For MVP, filesystem and shell tools should be restricted to an approved workspace root and explicit command allowlists where possible.

## 7. Memory Architecture

Use a hybrid memory model in the first version:

- short-term conversation memory in relational storage
- long-term structured memory in relational tables or JSON columns
- optional vector retrieval later, not required in MVP

Recommended memory record types:

- `profile`
- `preference`
- `project_fact`
- `task_rule`
- `reminder`

Memory writes should flow through an application service so the system can:

- validate the write
- deduplicate records
- log why the write happened
- decide whether the memory is global, per-user, or per-session

## 8. Scheduling Architecture

Use an internal scheduler service instead of embedding scheduling logic in channels or tools.

Job model fields should include:

- `job_id`
- `name`
- `cron`
- `enabled`
- `input_prompt`
- `target_channel`
- `policy_profile`
- `last_run_at`
- `last_status`

## 9. Recommended Repository Structure

```text
lightclaw/
  src/
    lightclaw/
      interfaces/
        cli/
        api/
        telegram/
      application/
        services/
        jobs/
        policies/
      domain/
        agent/
        channels/
        tools/
        skills/
        memory/
        providers/
      infrastructure/
        providers/
        persistence/
        mcp/
        tools/
        logging/
      config/
  tests/
    unit/
    integration/
  docs/
    planning/
```

## 10. Why a Modular Monolith First

This structure keeps the codebase small and agent-friendly while still allowing later extraction of:

- channel workers
- scheduler workers
- MCP bridge services
- dedicated storage services

It is the lowest-risk architecture for the current project stage.
