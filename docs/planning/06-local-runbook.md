# LightClaw Local Runbook

## Purpose

This document gives a concrete local setup and verification flow for developers.

## 1. Initialize the Environment

On Windows PowerShell:

```powershell
./scripts/dev-init.ps1
```

This script:

- creates `.venv` if needed
- copies `.env.example` to `.env` if missing
- creates a `uv`-managed virtual environment
- resolves and installs third-party dependencies with `uv`
- runs the project from source via `PYTHONPATH=src`
- runs database migrations

## 2. Check Database Status

```powershell
./scripts/run-cli.ps1 db status
```

Expected result:

- `current_version` should match `latest_version`
- `pending_versions` should be `none`

## 3. Run the API

```powershell
./scripts/run-api.cmd
```

This command runs Uvicorn in the foreground. The shell staying occupied is expected and does not mean the server is stuck.

Validated direct command:

```powershell
.\.venv\Scripts\python.exe -m uvicorn lightclaw.main:app --factory --host 127.0.0.1 --port 8000 --app-dir .\src
```

The API is ready only after Uvicorn prints `Uvicorn running on http://127.0.0.1:8000`.

Default local endpoints:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/console`
- `http://127.0.0.1:8000/docs`

## 4. Run the CLI

Single-turn:

```powershell
./scripts/run-cli.ps1 chat "hello"
```

Interactive:

```powershell
./scripts/run-cli.ps1 repl
```

## 5. Verify Core Features

Basic API health:

```powershell
curl http://127.0.0.1:8000/health
```

Basic API chat:

```powershell
curl -X POST http://127.0.0.1:8000/chat `
  -H "Content-Type: application/json" `
  -d "{\"session_id\":\"demo\",\"user_id\":\"demo-user\",\"message\":\"hello\",\"channel\":\"api\"}"
```

List skills:

```powershell
./scripts/run-cli.ps1 skills list
```

Run a tool:

```powershell
./scripts/run-cli.ps1 chat "/tool echo.text hello-tool"
```

## 6. Run Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 7. Docker

Build:

```powershell
docker build -t lightclaw:local .
```

Run:

```powershell
docker run --rm -p 8000:8000 lightclaw:local
```
