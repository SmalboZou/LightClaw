@echo off
setlocal
cd /d "%~dp0.."
if not exist ".lightclaw\tmp" mkdir ".lightclaw\tmp"
if not exist ".lightclaw\uv-cache" mkdir ".lightclaw\uv-cache"
set "TEMP=%CD%\.lightclaw\tmp"
set "TMP=%CD%\.lightclaw\tmp"
set "UV_CACHE_DIR=%CD%\.lightclaw\uv-cache"
set "PYTHONPATH=%CD%\src"
set "APP_DIR=%CD%\src"
set "PYTHONUNBUFFERED=1"
"%CD%\.venv\Scripts\python.exe" -m uvicorn lightclaw.main:app --factory --host 127.0.0.1 --port 8000 --app-dir "%APP_DIR%" --log-level debug
exit /b %ERRORLEVEL%
