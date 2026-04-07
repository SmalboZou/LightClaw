param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path ".lightclaw\tmp" | Out-Null
New-Item -ItemType Directory -Force -Path ".lightclaw\uv-cache" | Out-Null
$env:TEMP = (Resolve-Path ".lightclaw\tmp").Path
$env:TMP = $env:TEMP
$env:UV_CACHE_DIR = (Resolve-Path ".lightclaw\uv-cache").Path
$env:PYTHONPATH = (Resolve-Path "src").Path

if (Test-Path ".\.venv\Scripts\python.exe") {
    & ".\.venv\Scripts\python.exe" -m lightclaw.interfaces.cli.main @Args
    exit $LASTEXITCODE
}

throw ".venv is missing. Run scripts/dev-init.ps1 first."
