# LightClaw Development Guide for Future Agents

## 1. Purpose

This document tells future development agents how to implement the project without drifting from the intended architecture.

## 2. Source of Truth

- `PRO.md` is the canonical product requirements document
- files under `docs/planning/` explain design intent and implementation constraints

If there is a conflict, follow this order:

1. `PRO.md`
2. `docs/planning/02-architecture-design.md`
3. `docs/planning/03-technical-selection.md`

## 3. Delivery Priorities

Build in this order:

1. project skeleton and config system
2. provider abstraction and one provider adapter
3. core agent runtime loop
4. session persistence
5. CLI interface
6. HTTP API
7. tool framework and policy enforcement
8. Telegram integration
9. memory extraction
10. scheduler
11. skills
12. MCP

Do not start with MCP or a large plugin system before the core runtime works.

## 4. Hard Architectural Constraints

- keep a modular monolith first
- keep domain contracts independent from SDKs and transport libraries
- do not let channel adapters contain business logic
- do not let provider-specific payloads leak into domain models
- all sensitive tool actions must go through policy enforcement

## 5. Coding Guidance

- use strong typing
- keep interfaces explicit
- prefer small, composable services over magic registries
- avoid hidden global state
- prefer structured return objects over loose dictionaries

## 6. Persistence Guidance

At minimum, persist:

- sessions
- messages
- memory records
- scheduled jobs
- execution logs for sensitive actions

Do not couple persistence models too tightly to any single channel provider.

## 7. Tool Guidance

Every tool implementation should provide:

- clear schema
- timeout
- deterministic error surface
- explicit permission scope
- audit logging hook

Do not implement unrestricted shell access in the first version.

## 8. Testing Guidance

Before expanding features, ensure:

- the agent loop can complete a full tool-call cycle
- policy checks can deny dangerous operations
- sessions survive restarts
- one scheduled task can execute end to end
- one non-CLI channel can send and receive messages correctly

## 9. Common Failure Modes to Avoid

- overbuilding abstractions before MVP
- mixing domain and infrastructure concerns
- letting tools bypass policy checks
- storing secrets in logs
- making every channel a first-class priority too early
- adding vector databases before structured memory is working

## 10. Definition of "Ready for Phase 2"

Phase 1 should be considered complete only when:

- CLI and HTTP API both work
- at least one real provider works reliably
- session and memory persistence are in place
- tool execution is policy-controlled
- logs are sufficient to debug failures

Only after that should broader channel support and the skills system become the focus.
