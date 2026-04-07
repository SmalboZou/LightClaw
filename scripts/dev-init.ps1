$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path ".lightclaw\tmp" | Out-Null
New-Item -ItemType Directory -Force -Path ".lightclaw\uv-cache" | Out-Null
$env:TEMP = (Resolve-Path ".lightclaw\tmp").Path
$env:TMP = $env:TEMP
$env:UV_CACHE_DIR = (Resolve-Path ".lightclaw\uv-cache").Path

if (-not (Test-Path ".venv")) {
    python -m uv venv .venv
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

$venvPython = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = (Resolve-Path "src").Path

if (Test-Path $venvPython) {
    python -m uv lock
    python -m uv sync --extra dev --no-install-project
    & $venvPython -m lightclaw.interfaces.cli.main db migrate
    Write-Host "Development environment initialized with uv-managed .venv."
    exit 0
}

throw "Failed to initialize uv-managed .venv."
