$ErrorActionPreference = "Stop"

$env:PYTHONPATH = (Resolve-Path "src").Path
& ".\.venv\Scripts\python.exe" ".\scripts\browser-smoke.py" @args
