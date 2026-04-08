@echo off
setlocal
set "LIGHTCLAW_DEV_INIT_LOG=%TEMP%\lightclaw-dev-init.log"
if exist "%LIGHTCLAW_DEV_INIT_LOG%" del /f /q "%LIGHTCLAW_DEV_INIT_LOG%" >nul 2>nul
"C:\Users\Degrasse\AppData\Local\Programs\Python\Python312\python.exe" "%~dp0dev-init.py" > "%LIGHTCLAW_DEV_INIT_LOG%" 2>&1
set "LIGHTCLAW_DEV_INIT_EXIT=%ERRORLEVEL%"
type "%LIGHTCLAW_DEV_INIT_LOG%"
exit /b %LIGHTCLAW_DEV_INIT_EXIT%
