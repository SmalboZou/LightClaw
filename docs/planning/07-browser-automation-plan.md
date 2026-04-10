# LightClaw Browser Automation Plan

## 1. Purpose

This document defines the first browser-automation expansion for LightClaw.

The goal is to add OpenClaw-like browser-driven task execution without collapsing the project into a general desktop GUI agent.

The first milestone should make LightClaw capable of:

- opening and managing a controlled browser session
- navigating websites and reading page state
- completing browser-based weather lookup
- completing browser-based webmail send flows
- exposing these capabilities through the existing runtime, policy, channel, and job systems

This document is intentionally implementation-oriented so a follow-up agent can execute it without filling in missing product decisions.

## 2. Product Goal and Success Criteria

### 2.1 Goal

Extend LightClaw from a text-and-tool agent into a browser-capable agent that can execute real web tasks through structured browser control.

### 2.2 Success Criteria

The first browser-automation iteration is successful when all of the following are true:

- the runtime can open a managed browser session through a dedicated browser service
- the agent can navigate a page, inspect state, click, type, wait, and extract structured content through explicit browser tools
- weather lookup can be completed through a browser-backed workflow
- email sending can be completed through a browser-backed webmail workflow
- browser actions are governed by explicit policy and domain allowlists
- browser sessions, errors, and significant actions are recorded in execution logs
- the capability is available to CLI, API, Web Console, Telegram, Feishu, and scheduled jobs through the existing runtime path
- automated tests cover browser policy, workflow orchestration, and deterministic mocked browser pages

### 2.3 Non-Goals for the First Milestone

The first milestone must not include:

- unrestricted desktop GUI automation
- arbitrary keyboard and mouse control outside the browser
- OCR-driven screen understanding
- CAPTCHA solving or anti-bot evasion
- generic multi-app orchestration across browser and native desktop applications
- broad multi-provider email support
- broad multi-site weather provider selection

## 3. Design Direction

### 3.1 Primary Approach

Implement browser automation as a governed infrastructure subsystem backed by Playwright.

The agent runtime should not gain raw desktop-control powers. Instead, it should invoke a dedicated browser service through structured tools with defined schemas, policies, and logging.

This keeps the implementation aligned with the current LightClaw architecture:

- domain layer remains tool-driven
- application layer remains orchestration-focused
- infrastructure owns browser SDK details
- policy enforcement remains explicit

### 3.2 Why Not a GUI Agent First

General GUI-agent behavior is broader, less deterministic, harder to test, and harder to secure.

For the current project stage, browser automation solves the target use cases:

- open a browser
- navigate a site
- check weather
- log into webmail
- send an email

That is enough for the first functional milestone while preserving a clean extension path for future desktop automation.

### 3.3 Future Extension Boundary

The design should reserve a future boundary for desktop GUI automation, but that future subsystem should remain separate from the browser automation MVP.

Recommended future boundary:

- `infrastructure/gui/`
- optional `application/services/gui_*`
- future `gui_agent` planning document when the product actually needs it

Browser automation remains the preferred solution for browser tasks even after any GUI subsystem exists.

## 4. Architecture Changes

### 4.1 New Subsystem

Add a browser automation subsystem with these responsibilities:

- create and close managed browser sessions
- maintain session-scoped browser state
- provide deterministic page interaction primitives
- sanitize outputs before they re-enter the runtime
- enforce navigation and side-effect boundaries

This subsystem belongs in infrastructure and should be surfaced through the tool framework rather than directly from interfaces or provider adapters.

### 4.2 Integration with Current Layers

#### Interfaces Layer

No new interface entrypoint is required for the first milestone.

Existing interfaces should all be able to trigger browser-backed workflows through the same runtime path:

- CLI
- HTTP API
- Web Console
- Telegram
- Feishu
- scheduler jobs

#### Application Layer

The application layer should orchestrate browser execution in the same way it already orchestrates tool execution.

It should remain responsible for:

- policy resolution
- session context resolution
- job isolation
- audit logging
- workflow composition for weather and mail scenarios

#### Domain Layer

The domain layer should gain:

- browser-related tool definitions
- browser-related policy scopes
- browser-oriented execution result contracts

The domain layer must not depend on Playwright APIs or browser-specific SDK types.

#### Infrastructure Layer

The infrastructure layer should gain:

- Playwright-backed browser runtime
- browser session store or manager
- browser tool implementations
- deterministic page summarization helpers
- output sanitization helpers

## 5. Browser Tool Model

### 5.1 Principle

Do not expose one unconstrained "do anything in the browser" tool.

Instead, define a small, explicit tool surface with JSON-schema-backed arguments and predictable outputs.

### 5.2 MVP Tool Set

#### `browser.open`

Purpose:

- start or attach to a named browser session

Inputs:

- `session_name`
- `headless`
- `start_url` optional
- `persistent_profile` optional

Outputs:

- `session_id`
- active URL
- page title

#### `browser.navigate`

Purpose:

- move the active page to a specific URL

Inputs:

- `session_id`
- `url`

Outputs:

- final URL
- page title
- load status summary

#### `browser.snapshot`

Purpose:

- return a normalized summary of the current page

Inputs:

- `session_id`

Outputs:

- URL
- title
- visible text excerpt
- summarized forms
- summarized clickable elements
- page state metadata useful for next actions

#### `browser.click`

Purpose:

- click a specific element on the page

Inputs:

- `session_id`
- `selector` or a stable element token derived from `browser.snapshot`

Outputs:

- success status
- page change summary

#### `browser.type`

Purpose:

- type text into a page field

Inputs:

- `session_id`
- `selector`
- `text`
- `secret` optional

Outputs:

- success status
- field interaction summary

If `secret=true`, the typed value must never be stored in logs or tool outputs.

#### `browser.wait`

Purpose:

- block until a page condition is satisfied

Inputs:

- `session_id`
- `selector` optional
- `url_contains` optional
- `timeout_seconds`

Outputs:

- matched condition
- elapsed time

#### `browser.extract`

Purpose:

- extract structured information from the page

Inputs:

- `session_id`
- `selector` optional
- `mode`

Outputs:

- extracted visible text, attribute value, or structured page fragment

#### `browser.close`

Purpose:

- close an active browser session

Inputs:

- `session_id`

Outputs:

- closed status

### 5.3 Explicit MVP Exclusions

The browser tool set should not initially include:

- file upload/download workflows
- arbitrary JavaScript execution exposed to the model
- full tab-management primitives
- screenshot-heavy workflows as a primary control mode
- PDF workflows
- canvas-only interactions

## 6. Policy and Safety Model

### 6.1 New Browser Scopes

Extend policy handling to support browser-specific permissions.

Recommended scopes:

- `browser_read`
- `browser_write`
- `browser_auth`

Meaning:

- `browser_read`: safe page open, navigate, snapshot, extract
- `browser_write`: clicks and non-sensitive input that can change page state
- `browser_auth`: credential entry or login-related actions

### 6.2 Why Separate Browser Scopes

Browser automation should not be hidden inside `process_exec`.

This keeps auditability and user control explicit. It also prevents the browser system from inheriting the much broader power envelope of shell execution.

### 6.3 Domain Allowlisting

Browser navigation must be limited by configuration in the first milestone.

Recommended config:

- `LIGHTCLAW_BROWSER_ALLOWED_DOMAINS`

Behavior:

- browser tools deny navigation to domains outside the allowlist
- redirect chains should still be validated against the allowlist
- mail workflow domains and weather workflow domains must be explicitly allowed

### 6.4 Secret Handling

The system must treat browser-entered secrets as sensitive values.

Rules:

- secret values must be masked in logs
- secret values must be removed from tool outputs
- secret values must never be stored in execution logs, session history, or browser result summaries
- browser login helpers should prefer persistent authenticated sessions after first setup

### 6.5 Persistent Auth Control

Add an explicit setting:

- `LIGHTCLAW_BROWSER_ALLOW_PERSISTENT_AUTH`

Behavior:

- disabled: browser sessions are ephemeral and do not intentionally persist login state
- enabled: browser sessions may use a dedicated persistent profile directory for approved flows like webmail

## 7. Runtime and Configuration Changes

### 7.1 Settings Additions

Add browser-related settings to `AppSettings`.

Recommended fields:

- `browser_enabled`
- `browser_headless`
- `browser_profile_root`
- `browser_allowed_domains`
- `browser_allow_persistent_auth`
- `mail_web_provider`
- `weather_web_provider`

### 7.2 Runtime Reload Expectations

These settings should flow through the same config service and runtime reload path as existing provider/channel settings.

Expected behavior:

- enable/disable browser automation through config
- expose masked config state in the Web Console
- reload most browser settings hot where safe
- require restart only if a future implementation proves that a given browser resource cannot safely hot-reload

### 7.3 Web Console Expectations

The console should expose browser config fields for:

- browser enablement
- headless mode
- allowed domains
- persistent auth enablement
- selected mail provider
- selected weather provider

The console is not required to implement a full browser-session inspector in the first milestone, but it should surface enough configuration and diagnostics to operate the feature.

## 8. Browser Session Management

### 8.1 Session Ownership

Browser sessions should be isolated and explicit.

Defaults:

- interactive user requests use session-scoped browser sessions
- scheduled jobs use job-scoped browser sessions
- sessions are never shared across users

### 8.2 Browser Profile Storage

Recommended storage root:

- `.lightclaw/browser/`

Recommended substructure:

- ephemeral session data
- optional persistent profiles
- temporary extracted artifacts if required later

Do not store repo-tracked files there.

### 8.3 Lifecycle

The browser service should define:

- session create
- session reuse by id
- inactivity timeout cleanup
- explicit close
- crash recovery and cleanup behavior

For MVP, explicit close and process cleanup are sufficient; advanced browser recovery can remain future work.

## 9. Weather Workflow Design

### 9.1 Goal

Support a simple end-user request such as:

- "check the weather in Shanghai"

through browser automation rather than a native weather API.

### 9.2 Workflow Shape

The weather workflow should:

1. open a browser session
2. navigate to one selected weather site
3. locate the requested city
4. extract normalized weather fields
5. return a structured summary to the user

### 9.3 Fixed Provider in MVP

Do not plan a site-selection engine in the first milestone.

Choose one stable weather site during implementation and keep it fixed behind configuration.

The workflow should return at least:

- location
- current temperature
- condition
- high/low
- updated time if visible

### 9.4 Skill and Tooling

Expose weather capability through:

- a browser-backed skill or recipe such as `weather.lookup_web`

The actual extraction should still be powered by the structured browser tools, not by a separate hidden scraping stack.

## 10. Webmail Send Workflow Design

### 10.1 Goal

Support a request such as:

- "open the browser and send an email"

through browser-controlled webmail rather than SMTP or provider APIs in the first milestone.

### 10.2 First Supported Provider

Use one mail provider in MVP to avoid overdesign.

Default recommendation:

- Gmail web

Architecture should remain general enough to support Outlook later.

### 10.3 Workflow Shape

The mail workflow should:

1. open a browser session with optional persistent profile support
2. navigate to the configured mail provider
3. complete login if needed
4. open compose UI
5. fill recipient, subject, and body
6. optionally require confirmation in safety mode
7. send the message
8. return a structured result

### 10.4 First-Time Login vs Reuse

The plan must explicitly distinguish:

- first-time setup flow
- repeat send flow with existing authenticated profile

The preferred operational path after initial setup is:

- reuse a persistent authenticated browser profile

This avoids repeatedly injecting secrets and reduces login friction.

### 10.5 Safety Behavior

The mail workflow is a side-effectful action.

For the first milestone, the implementation should support a confirmation mode that can block final send until the workflow is ready and validated.

Recommended behavior:

- draft and fill all fields
- optionally return a "ready_to_send" state
- send only if the mode or policy allows final action

### 10.6 Skill and Tooling

Expose mail capability through:

- a browser-backed skill or recipe such as `mail.send_web`

The workflow should not bypass browser tools or policy logging.

## 11. Logging and Diagnostics

### 11.1 New Execution Events

Add browser-specific execution events such as:

- `browser_session_started`
- `browser_navigation_started`
- `browser_navigation_completed`
- `browser_element_clicked`
- `browser_input_typed`
- `browser_snapshot_captured`
- `browser_policy_denied`
- `browser_session_closed`

### 11.2 Log Content Rules

Each event should include:

- browser session id
- runtime session id
- tool name
- sanitized URL or domain
- timing or duration where relevant

Sensitive values must be removed or masked.

### 11.3 Diagnostics Surfaces

Browser events should appear through the same existing diagnostics surfaces:

- execution logs
- session diagnostics
- job run diagnostics
- Web Console logs view

## 12. Testing Strategy

### 12.1 Unit Tests

Add tests for:

- policy denial when browser automation is disabled
- policy denial for disallowed domains
- secret redaction in browser typing
- browser session lifecycle behavior
- page snapshot normalization logic
- browser workflow configuration validation

### 12.2 Integration Tests

Add tests for:

- browser-backed weather flow through API
- browser-backed mail flow through API
- session diagnostics containing browser events
- scheduled job execution with browser-backed workflows
- config persistence and reload of browser settings

### 12.3 Browser Fixture Strategy

Automated tests must not depend on live third-party sites.

Use deterministic local or mocked pages for:

- weather page fixture
- login page fixture
- mail compose/send page fixture

The browser layer should be tested against predictable fixtures so selectors and state transitions remain stable.

### 12.4 End-to-End Validation

After the implementation is complete, perform a manual validation path for:

- one weather request
- one login reuse flow
- one email send flow in a controlled test account

## 13. Rollout Plan

### 13.1 Recommended Delivery Order

Implement in this order:

1. browser service abstraction
2. Playwright-backed session manager
3. browser policy scopes and config
4. core browser tools
5. execution logging for browser actions
6. mocked page fixtures and browser tests
7. weather workflow
8. webmail send workflow
9. Web Console config support
10. job integration and cross-channel validation

### 13.2 Definition of Done

This browser automation phase is complete when:

- browser tools work through the normal agent runtime path
- policy enforcement is explicit and test-covered
- browser actions are logged and diagnosable
- weather workflow works against the browser stack
- webmail send workflow works with at least one provider
- Web Console can configure the capability
- deterministic tests pass without live third-party dependencies

## 14. Concrete File and Module Guidance

Recommended additions:

- `src/lightclaw/infrastructure/browser/`
- `src/lightclaw/domain/browser/` only if shared contracts become large enough to justify it
- browser tools integrated through the existing tool registry composition path
- browser workflow skills under `skills/` if implemented as declarative skills

Recommended updates:

- settings/config service
- execution policy models
- tool registry
- execution logging
- Web Console config models and static UI
- tests for tools, API, jobs, and workflow fixtures

## 15. Summary

The first browser-automation phase should give LightClaw OpenClaw-like web task capability while preserving the project’s current strengths:

- explicit boundaries
- policy-driven execution
- good observability
- channel independence
- testable infrastructure

The correct first step is a controlled browser subsystem, not a broad GUI agent.

That design is sufficient to support the target use cases:

- open a browser
- send email
- check weather

and it leaves a clean path for future desktop automation only when the product truly needs it.
