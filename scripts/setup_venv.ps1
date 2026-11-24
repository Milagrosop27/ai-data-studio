$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        & py -3 -m venv (Join-Path $root ".venv")
    } else {
        & python -m venv (Join-Path $root ".venv")
    }
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo crear el entorno virtual .venv."
    }
}

& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo actualizar pip dentro de .venv."
}
& $python -m pip install -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "No se pudieron instalar las dependencias de requirements.txt."
}
Write-Output "OK: dependencias instaladas en .venv."
