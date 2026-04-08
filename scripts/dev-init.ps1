param(
    [switch]$StopProjectPython
)

$ErrorActionPreference = "Stop"

$workspaceVenv = [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path ".venv"))
$activeVenv = $env:VIRTUAL_ENV
if ($activeVenv) {
    $resolvedActiveVenv = [System.IO.Path]::GetFullPath($activeVenv)
    if ($resolvedActiveVenv.StartsWith($workspaceVenv, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Host "Detected active project .venv in current shell. Temporarily clearing inherited venv activation for bootstrap."
        Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
        Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
        if ($env:PATH) {
            $pathEntries = $env:PATH -split ';' | Where-Object {
                $_ -and -not ([System.IO.Path]::GetFullPath($_).StartsWith($workspaceVenv, [System.StringComparison]::OrdinalIgnoreCase))
            }
            $env:PATH = ($pathEntries -join ';')
        }
    }
}

foreach ($envName in @(
    "CONDA_DEFAULT_ENV",
    "CONDA_PREFIX",
    "CONDA_PROMPT_MODIFIER",
    "CONDA_PYTHON_EXE",
    "CONDA_EXE",
    "PYTHONSTARTUP",
    "PYTHONHOME"
)) {
    Remove-Item "Env:$envName" -ErrorAction SilentlyContinue
}

function Resolve-BootstrapPython {
    $preferred = @(
        "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python312\python.exe",
        "D:\Anaconda\anaconda\python.exe"
    )

    foreach ($candidate in ($preferred | Select-Object -Unique)) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $workspaceRoot = (Get-Location).Path
    $venvPrefix = [System.IO.Path]::GetFullPath((Join-Path $workspaceRoot ".venv"))
    foreach ($cmd in (Get-Command python -All -ErrorAction SilentlyContinue)) {
        $source = $cmd.Source
        if (-not $source) {
            continue
        }

        $fullSource = [System.IO.Path]::GetFullPath($source)
        if ($fullSource.StartsWith($venvPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            continue
        }

        if ($fullSource -like "*WindowsApps*") {
            continue
        }

        if (Test-Path $fullSource) {
            return $fullSource
        }
    }

    throw "Unable to find a bootstrap Python interpreter."
}

function Test-VenvNeedsRebuild {
    param(
        [Parameter(Mandatory = $true)]
        [string]$VenvPath,

        [Parameter(Mandatory = $true)]
        [string]$BootstrapPython
    )

    $cfgPath = Join-Path $VenvPath "pyvenv.cfg"
    if (-not (Test-Path $cfgPath)) {
        return $false
    }

    $cfgText = Get-Content $cfgPath -Raw
    $bootstrapHome = Split-Path $BootstrapPython -Parent
    if ($cfgText -match [regex]::Escape("home = D:\Anaconda\anaconda")) {
        return $true
    }
    if ($cfgText -match "^home = (.+)$") {
        $venvHome = $Matches[1].Trim()
        if ($venvHome -and ($venvHome -ne $bootstrapHome)) {
            return $true
        }
    }
    return $false
}

function Get-ProjectPythonProcesses {
    param(
        [Parameter(Mandatory = $true)]
        [string]$VenvRoot
    )

    Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -and $_.Path.StartsWith($VenvRoot, [System.StringComparison]::OrdinalIgnoreCase)
    }
}

New-Item -ItemType Directory -Force -Path ".lightclaw\tmp" | Out-Null
New-Item -ItemType Directory -Force -Path ".lightclaw\uv-cache" | Out-Null
$env:TEMP = (Resolve-Path ".lightclaw\tmp").Path
$env:TMP = $env:TEMP
$env:UV_CACHE_DIR = (Resolve-Path ".lightclaw\uv-cache").Path
$env:PYTHONPATH = (Resolve-Path "src").Path

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

$bootstrapPython = Resolve-BootstrapPython
$venvPython = ".\.venv\Scripts\python.exe"
$venvRoot = [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path ".venv"))
$projectPythonProcesses = @(Get-ProjectPythonProcesses -VenvRoot $venvRoot)

if ($projectPythonProcesses.Count -gt 0) {
    $processSummary = ($projectPythonProcesses | ForEach-Object { "$($_.Id):$($_.Path)" }) -join ", "
    if ($StopProjectPython) {
        Write-Host "Stopping project Python processes before initialization: $processSummary"
        $projectPythonProcesses | Stop-Process -Force
        Start-Sleep -Milliseconds 500
    } else {
        throw "Project Python processes are already running and may lock the virtual environment or database. Stop them first, then rerun dev-init.ps1. Running processes: $processSummary"
    }
}

if ((Test-Path $venvPython) -and (Test-VenvNeedsRebuild -VenvPath $venvRoot -BootstrapPython $bootstrapPython)) {
    if (-not $venvRoot.StartsWith([System.IO.Path]::GetFullPath((Get-Location).Path), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to rebuild venv outside workspace: $venvRoot"
    }
    Write-Host "[1/3] Rebuilding .venv with bootstrap Python: $bootstrapPython"
    Remove-Item -LiteralPath $venvRoot -Recurse -Force
}

if (-not (Test-Path $venvPython)) {
    Write-Host "[1/3] Creating virtual environment with bootstrap Python..."
    & $bootstrapPython -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        throw "Virtual environment creation failed with exit code $LASTEXITCODE."
    }
}

if (Test-Path $venvPython) {
    if (-not (Test-Path ".\uv.lock")) {
        Write-Host "[2/3] Generating uv.lock..."
        & $bootstrapPython -m uv lock
    }

    Write-Host "[2/3] Syncing dependencies into .venv..."
    & $bootstrapPython -m uv sync --extra dev --no-install-project --locked --quiet
    Write-Host "[3/3] Applying database migrations..."
    $migrationCommand = @'
from lightclaw.config.settings import AppSettings
from lightclaw.infrastructure.persistence.database import create_session_factory, get_migration_status

settings = AppSettings()
create_session_factory(settings.database_url)
status = get_migration_status(settings.database_url)
print('database_url=' + str(settings.database_url))
print('current_version=' + str(status['current_version']))
print('pending_versions=none')
'@
    $migrationScriptPath = Join-Path $env:TEMP "lightclaw-db-migrate.py"
    $migrationStdoutPath = Join-Path $env:TEMP "lightclaw-db-migrate.stdout.log"
    $migrationStderrPath = Join-Path $env:TEMP "lightclaw-db-migrate.stderr.log"
    Set-Content -LiteralPath $migrationScriptPath -Value $migrationCommand -Encoding UTF8
    if (Test-Path $migrationStdoutPath) {
        Remove-Item -LiteralPath $migrationStdoutPath -Force
    }
    if (Test-Path $migrationStderrPath) {
        Remove-Item -LiteralPath $migrationStderrPath -Force
    }

    $migrationProcess = Start-Process `
        -FilePath $venvPython `
        -ArgumentList @($migrationScriptPath) `
        -WorkingDirectory (Get-Location).Path `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $migrationStdoutPath `
        -RedirectStandardError $migrationStderrPath

    if (Test-Path $migrationStdoutPath) {
        Get-Content -LiteralPath $migrationStdoutPath | Write-Host
    }

    if ($migrationProcess.ExitCode -ne 0) {
        if (Test-Path $migrationStderrPath) {
            Get-Content -LiteralPath $migrationStderrPath | Write-Error
        }
        throw "Database migration apply failed with exit code $($migrationProcess.ExitCode)."
    }

    Write-Host "Development environment initialized with uv-managed .venv."
    exit 0
}

throw "Failed to initialize uv-managed .venv."
