param(
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path ".lightclaw\tmp" | Out-Null
New-Item -ItemType Directory -Force -Path ".lightclaw\uv-cache" | Out-Null
$env:TEMP = (Resolve-Path ".lightclaw\tmp").Path
$env:TMP = $env:TEMP
$env:UV_CACHE_DIR = (Resolve-Path ".lightclaw\uv-cache").Path
$env:PYTHONPATH = (Resolve-Path "src").Path
$env:PYTHONUNBUFFERED = "1"

if (Test-Path ".\.venv\Scripts\python.exe") {
    $appDir = (Resolve-Path "src").Path
    $uvicornArgs = @(
        "-m", "uvicorn",
        "lightclaw.main:app",
        "--factory",
        "--host", "127.0.0.1",
        "--port", "8000",
        "--app-dir", $appDir,
        "--log-level", "debug"
    )

    if ($Reload) {
        $uvicornArgs += "--reload"
    }

    & ".\.venv\Scripts\python.exe" @uvicornArgs
    exit $LASTEXITCODE
}

throw ".venv is missing. Run scripts/dev-init.ps1 first."
