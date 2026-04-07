# LightClaw Product Requirements Document

## 1. Overview

### 1.1 Product Name
`LightClaw` (working name)

### 1.2 Product Positioning
LightClaw is a lightweight, extensible personal AI agent framework inspired by OpenClaw-style agent systems. It is designed to support both:

- end users who want a usable assistant with minimal setup
- developers who want a controllable, hackable, self-hosted agent runtime

### 1.3 Product Vision
The product should let users deploy a personal or team-level AI agent once, connect their own model credentials, and interact with it through familiar channels such as CLI, HTTP APIs, and messaging platforms. The agent should behave like a practical digital operator rather than only a chatbot.

### 1.4 Core Principles
- BYOK first: users bring their own LLM credentials
- lightweight by default: avoid heavyweight orchestration frameworks unless they solve a clear problem
- channel-agnostic core: business logic must be decoupled from channel-specific integrations
- tool-enabled agent loop: the system is designed for action, not only conversation
- safe extensibility: tools, skills, and MCP integrations must have clear trust boundaries

## 2. Goals and Non-Goals

### 2.1 Goals
- Provide a reusable agent runtime with a standard think-act-observe-reply loop
- Support multiple LLM providers through a unified provider layer
- Expose the agent through a unified channel abstraction
- Support persistent session history and structured long-term memory
- Support built-in tools, declarative skills, and MCP-based external integrations
- Offer a deployment path simple enough for individual users and teams

### 2.2 Non-Goals for MVP
- full no-code workflow builder
- autonomous multi-agent planning framework
- enterprise-grade RBAC across many organizations
- full browser automation stack
- native support for every chat platform in the first release

## 3. Target Users

### 3.1 General Users
Users with little or no coding experience who want a private AI assistant after a simple deployment and configuration flow.

### 3.2 Developers and Builders
Users who want to self-host the system, add tools, write skills, connect MCP servers, or customize prompts and policies.

### 3.3 Teams and Small Organizations
Groups that want a shared assistant connected to team communication channels and internal services.

## 4. Primary Use Cases

### 4.1 Cross-Channel Assistant
The user can contact the same agent from different channels and keep a coherent working context.

### 4.2 Scheduled Automation
The agent can run scheduled tasks, collect information, summarize state, and deliver results to configured channels.

### 4.3 Tool-Driven Operations
The agent can execute constrained filesystem, shell, web, and service operations under explicit policy controls.

### 4.4 Extensible Capability Loading
Developers can add new skills and MCP-backed capabilities without modifying the core runtime.

## 5. Functional Requirements

### 5.1 Agent Runtime
- Implement a standard loop: `plan -> act -> observe -> respond`
- Support tool calling, retries, loop limits, and guardrails
- Support both synchronous request-response interactions and asynchronous background jobs
- Support configurable system prompt composition from identity, memory, policies, and enabled skills

### 5.2 Model Provider Layer
- Support OpenAI-compatible APIs as the baseline abstraction
- Support Anthropic-style providers through an adapter
- Support Azure OpenAI through provider configuration
- Support local model endpoints that expose OpenAI-compatible APIs
- Normalize model invocation, streaming, token usage, tool call payloads, and error handling

### 5.3 Channel Integration Layer
- Provide a base channel contract for inbound and outbound messages
- Normalize user identity, conversation identity, attachments, metadata, and delivery status
- Required initial channels:
  - CLI
  - HTTP API
  - Telegram
- Planned channels after MVP:
  - Slack
  - Discord
  - Feishu
  - DingTalk
  - WeCom
  - WebSocket frontend
- WhatsApp should be treated as a bridge integration, not a core MVP target

### 5.4 Tool System
- Built-in tool categories:
  - filesystem read and controlled write
  - shell command execution
  - HTTP fetch and web content extraction
  - optional search adapter
- Each tool must define:
  - input schema
  - output schema
  - timeout
  - permission policy
  - audit log entry

### 5.5 Skills System
- Support declarative skill packaging using Markdown plus YAML metadata
- Support dependency checks for environment variables, binaries, and optional services
- Support always-on and on-demand skill loading
- Skills must be able to contribute:
  - prompt fragments
  - tool definitions
  - configuration requirements
  - usage instructions

### 5.6 MCP Integration
- Support MCP client connectivity to external tools and servers
- Provide transport abstraction so MCP can be added without changing the agent runtime
- Surface MCP tools as first-class tools with unified policy handling

### 5.7 Memory and Session Management
- Persist session history by channel, user, and conversation
- Support context window management and truncation policies
- Support structured long-term memory with typed records such as:
  - user profile
  - preferences
  - recurring tasks
  - important facts
- Memory writes must be policy-controlled and observable

### 5.8 Scheduling and Background Execution
- Support cron-based task scheduling
- Support heartbeat and health monitoring for long-running workers
- Support retry policies, dead-letter handling, and execution logs for background jobs

### 5.9 Configuration and Deployment
- Support environment-based configuration and file-based configuration
- Provide a minimal Docker deployment path
- Keep first-run setup simple for BYOK users

## 6. Non-Functional Requirements

### 6.1 Maintainability
- Prefer explicit code over framework-heavy abstractions
- Keep module boundaries clear and testable
- Avoid binding business logic to a specific channel or provider

### 6.2 Performance and Concurrency
- Use an async-first architecture for network and IO-heavy paths
- Support concurrent sessions without shared-state corruption
- Ensure background tasks do not block interactive request paths

### 6.3 Security
- Separate secrets from code and from user-visible logs
- Enforce tool permissions and policy checks before execution
- Support sandboxing or allowlist-based controls for shell and filesystem tools
- Provide audit logs for sensitive operations

### 6.4 Reliability
- Gracefully handle provider failures, timeouts, malformed tool calls, and channel delivery errors
- Support idempotent processing where practical
- Provide structured logs and health endpoints

### 6.5 Portability
- Run locally for development
- Run in Docker for self-hosted deployment
- Avoid platform-specific assumptions in the core architecture

## 7. Architecture Requirements

The implementation should follow layered boundaries:

- `interfaces`: CLI, HTTP API, bot/webhook adapters, WebSocket gateway
- `application`: orchestration services, use cases, scheduling, policy enforcement
- `domain`: core models, agent loop, memory contracts, tool contracts, channel contracts
- `infrastructure`: providers, storage, queues, MCP transport, external SDK adapters

Cross-layer dependencies must flow inward. Channel-specific logic must not leak into the domain layer.

## 8. Recommended MVP Scope

### 8.1 In Scope
- single-runtime deployment
- CLI channel
- HTTP API
- Telegram integration
- OpenAI-compatible provider adapter
- Anthropic provider adapter
- SQLite-backed persistence
- filesystem and shell tools with strict policy controls
- basic web fetch tool
- simple long-term memory extraction
- cron scheduler

### 8.2 Out of Scope
- multi-tenant SaaS control plane
- browser automation
- visual workflow builder
- advanced analytics dashboard
- marketplace for third-party extensions

## 9. Acceptance Criteria for MVP

- A developer can start the service locally and talk to the agent through CLI
- The same runtime can expose an HTTP API and Telegram bot integration
- The agent can call at least three built-in tools under policy control
- Session history persists across restarts
- Long-term memory can be stored and retrieved in a structured way
- A scheduled job can trigger a task and send output to a channel
- Logs make it possible to diagnose provider, tool, and channel failures

## 10. Roadmap

### Phase 1: Core Runtime MVP
- establish repository structure and coding conventions
- implement the agent runtime, provider abstraction, CLI, HTTP API, and persistence
- add basic built-in tools and policy layer

### Phase 2: Channel and Memory Expansion
- add Telegram and one team chat platform
- improve session management and memory extraction
- improve observability and operational safety

### Phase 3: Extensibility
- add the declarative skills system
- add MCP integration
- expand supported tools and background workflows

## 11. Open Questions

- Which capabilities should be enabled by default versus opt-in only?
- Should long-term memory be file-backed, relational, vector-backed, or hybrid in the first release?
- How strict should shell and filesystem policies be for personal deployments versus team deployments?
- Which channel after Telegram has the highest implementation priority?

## 12. Canonical Supporting Documents

Detailed supporting documents are stored under [docs/planning/README.md](/E:/西电/研二/dmx/lightClaw/docs/planning/README.md).
