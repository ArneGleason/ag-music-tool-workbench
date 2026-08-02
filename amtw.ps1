# Launcher: runs the amtw CLI with the main venv's python, from anywhere.
#   .\amtw.ps1 workbench
#   .\amtw.ps1 run input\my_vocal.wav
#   .\amtw.ps1 doctor
$py = Join-Path $env:LOCALAPPDATA "VocalStemRegen\venvs\main\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "main venv missing ($py). Run scripts\setup_runtime.ps1 — see README."
    exit 1
}
Push-Location $PSScriptRoot
try {
    & $py -m amtw @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
