# Launcher: runs the amtw CLI with the main venv's python, from anywhere.
#   .\amtw.ps1 workbench
#   .\amtw.ps1 run input\my_vocal.wav
#   .\amtw.ps1 doctor
#
# ASCII ONLY in this file, deliberately. Windows PowerShell 5.1 reads a .ps1
# with no BOM as ANSI, so a single em-dash in a string became mojibake and took
# the closing quote with it -- the script died with "The string is missing the
# terminator" before it ran a line. PowerShell 7 reads it as UTF-8 and never
# sees the problem, which is exactly why it survived unnoticed.
$py = Join-Path $env:LOCALAPPDATA "VocalStemRegen\venvs\main\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "main venv missing ($py). Run scripts\setup_runtime.ps1 - see README."
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
