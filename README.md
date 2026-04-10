# LightClaw

LightClaw is a lightweight personal AI agent framework inspired by OpenClaw-style systems.

## Current State

This repository currently includes:

- a modular Python codebase under `src/lightclaw`
- FastAPI and CLI entrypoints
- SQLite-backed persistence
- OpenAI-compatible, Anthropic, and mock providers
- a schema-backed tool framework
- Telegram integration
- Feishu integration
- structured memory and extraction flow
- jobs and scheduler support
- declarative skills
- manifest-backed MCP tool loading

## Recommended Setup

This project is now set up to use `uv` as the primary environment manager.

On this machine, the validated workflow is:

1. create and sync the isolated `.venv` with `uv`
2. run the project from source with `PYTHONPATH=src`
3. use the provided PowerShell scripts instead of manually activating environments

## Quick Start on Windows PowerShell

### 1. Initialize the isolated environment

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-init.ps1
```

What this does:

- creates `.venv` with `uv`
- creates `uv.lock` if needed
- installs third-party dependencies with `uv sync --extra dev --no-install-project`
- copies `.env.example` to `.env` if missing
- runs database migrations

### 2. Check database status

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 db status
```

Expected result:

- `current_version` matches `latest_version`
- `pending_versions=none`

### 3. Start the API

```powershell
.\scripts\run-api.cmd
```

This command starts Uvicorn in the foreground. That is expected: the terminal will stay occupied while the API is running.

The validated startup command behind `run-api.cmd` is:

```powershell
.\.venv\Scripts\python.exe -m uvicorn lightclaw.main:app --factory --host 127.0.0.1 --port 8000 --app-dir .\src
```

The API is ready only after Uvicorn prints `Uvicorn running on http://127.0.0.1:8000`.

Default local endpoints:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/console`
- `http://127.0.0.1:8000/docs`

### 3.1 Open the Web Console

After the API is running, open:

- `http://127.0.0.1:8000/console`

The console provides:

- provider and runtime setup
- browser-based chat
- first-run bootstrap and local login
- streaming chat output
- session history inspection
- scheduled job management
- local user management and per-user console isolation
- skills and tools inventory
- provider connection testing
- execution log viewing
- system and migration status

`openai_compatible` means "OpenAI-style API schema", not "OpenAI only".
You can use it with:

- OpenAI
- OpenRouter
- self-hosted or third-party OpenAI-compatible gateways

OpenRouter example:

```env
LIGHTCLAW_PROVIDER_BACKEND=openai_compatible
LIGHTCLAW_PROVIDER_BASE_URL=https://openrouter.ai/api/v1
LIGHTCLAW_PROVIDER_MODEL=openai/gpt-4o-mini
LIGHTCLAW_PROVIDER_API_KEY=your-openrouter-key
LIGHTCLAW_PROVIDER_EXTRA_HEADERS_JSON={"HTTP-Referer":"https://your-app.example","X-Title":"LightClaw"}
```

### 4. Test the CLI in another terminal

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 chat "hello"
```

Interactive CLI:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 repl
```

## Basic Verification

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

If you are unsure whether the API is really up, check for the `Uvicorn running` line in the API terminal or verify that port `8000` is listening in another terminal.

Chat request:

```powershell
curl -X POST http://127.0.0.1:8000/chat `
  -H "Content-Type: application/json" `
  -d "{\"session_id\":\"demo\",\"user_id\":\"demo-user\",\"message\":\"hello\",\"channel\":\"api\"}"
```

List skills:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 skills list
```

Run a tool:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 chat "/tool echo.text hello-tool"
```

## Feishu Setup

LightClaw now supports Feishu event callbacks, signed requests, encrypted callbacks, and outbound message replies.

Configure the following environment variables in `.env` or from the Web Console:

```env
LIGHTCLAW_FEISHU_APP_ID=cli_xxx
LIGHTCLAW_FEISHU_APP_SECRET=xxx
LIGHTCLAW_FEISHU_VERIFICATION_TOKEN=xxx
LIGHTCLAW_FEISHU_ENCRYPT_KEY=xxx
```

Feishu webhook endpoint:

```text
POST /feishu/webhook
```

For a local API running on port `8000`, the full callback URL looks like:

```text
http://127.0.0.1:8000/feishu/webhook
```

In the Feishu developer console:

1. create or open a custom app
2. enable the bot capability
3. subscribe to the `im.message.receive_v1` event
4. set the request URL to your LightClaw `/feishu/webhook` endpoint
5. copy the App ID, App Secret, Verification Token, and Encrypt Key into LightClaw
6. grant the message event and message send permissions required by your bot
7. publish the app version inside your tenant and add the bot to the target chat

Current Feishu support in LightClaw includes:

- text message event intake
- URL verification handling
- verification token validation
- request signature validation
- encrypted callback decryption
- replying back to Feishu chats
- sending scheduled job output to Feishu when `target_channel=feishu`

For scheduled jobs, `target_destination` can be either a plain chat ID or an explicit prefixed target such as:

```text
chat_id:oc_xxx
open_id:ou_xxx
user_id:xxxx
email:user@example.com
```

## Browser Automation Setup

LightClaw now includes a Playwright-backed browser automation backend in addition to the default mock backend.

Enable it in `.env`:

```env
LIGHTCLAW_BROWSER_ENABLED=true
LIGHTCLAW_BROWSER_BACKEND=playwright
LIGHTCLAW_BROWSER_HEADLESS=true
LIGHTCLAW_BROWSER_ALLOWED_DOMAINS=wttr.in,mail.google.com,example.com
LIGHTCLAW_BROWSER_ALLOW_PERSISTENT_AUTH=false
LIGHTCLAW_BROWSER_PROFILE_ROOT=.lightclaw/browser
LIGHTCLAW_MAIL_WEB_PROVIDER=gmail
LIGHTCLAW_WEATHER_URL_TEMPLATE=https://wttr.in/{location}
```

Install the browser dependencies into `.venv`:

```powershell
.\.venv\Scripts\python.exe -m uv sync --extra browser --extra dev
.\.venv\Scripts\python.exe -m playwright install chromium
```

Run a smoke check against a real page:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-browser-smoke.ps1 --url https://example.com
```

Run a visible browser for manual debugging:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-browser-smoke.ps1 --headed --url https://example.com
```

Current real-page guidance:

- use `example.com` first to verify Playwright boot, navigation, and DOM extraction
- use `wttr.in` for weather flows after network access is confirmed
- use persistent profiles only for manual-authenticated mail sessions
- Gmail web send automation may require a one-time manual login in a persistent profile

## Database Commands

Migration files live under [src/lightclaw/infrastructure/persistence/migration_files](/E:/西电/研二/dmx/lightClaw/src/lightclaw/infrastructure/persistence/migration_files).

Useful commands:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 db status
powershell -ExecutionPolicy Bypass -File .\scripts\run-cli.ps1 db migrate
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Docker

Build:

```powershell
docker build -t lightclaw:local .
```

Run:

```powershell
docker run --rm -p 8000:8000 lightclaw:local
```

## Additional Docs

- Local runbook: [docs/planning/06-local-runbook.md](/E:/西电/研二/dmx/lightClaw/docs/planning/06-local-runbook.md)
- Roadmap: [docs/planning/05-implementation-roadmap.md](/E:/西电/研二/dmx/lightClaw/docs/planning/05-implementation-roadmap.md)
- Chinese README: [README.zh-CN.md](/E:/西电/研二/dmx/lightClaw/README.zh-CN.md)
