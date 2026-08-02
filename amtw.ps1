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
#
# The runtime is looked up through several candidates rather than trusting
# $env:LOCALAPPDATA alone. That variable came back looking correct in an error
# message while Test-Path still failed on it, which is what stray whitespace
# does: invisible when printed, fatal when resolved. So candidates are trimmed,
# and if none match the script prints every path it tried instead of asserting
# the venv is missing.

$candidates = @()
if ($env:AMTW_RUNTIME) { $candidates += $env:AMTW_RUNTIME.Trim() }
if ($env:VSR_RUNTIME)  { $candidates += $env:VSR_RUNTIME.Trim() }
if ($env:LOCALAPPDATA) { $candidates += (Join-Path $env:LOCALAPPDATA.Trim() "VocalStemRegen") }
if ($env:USERPROFILE)  { $candidates += (Join-Path $env:USERPROFILE.Trim() "AppData\Local\VocalStemRegen") }

$py = $null
$tried = @()
foreach ($root in $candidates) {
    $exe = Join-Path $root "venvs\main\Scripts\python.exe"
    $tried += $exe
    if (Test-Path -LiteralPath $exe) { $py = $exe; break }
}

if (-not $py) {
    Write-Host "amtw: could not find the main venv's python." -ForegroundColor Red
    Write-Host "Tried:"
    foreach ($t in $tried) { Write-Host ("  [{0}]" -f $t) }
    Write-Host ""
    Write-Host "Raw environment (brackets show stray whitespace):"
    Write-Host ("  AMTW_RUNTIME = [{0}]" -f $env:AMTW_RUNTIME)
    Write-Host ("  LOCALAPPDATA = [{0}]" -f $env:LOCALAPPDATA)
    Write-Host ("  USERPROFILE  = [{0}]" -f $env:USERPROFILE)
    Write-Host ""
    Write-Host "If the runtime is elsewhere, set it and retry:"
    Write-Host '  $env:AMTW_RUNTIME = "D:\path\to\VocalStemRegen"'
    Write-Host "Otherwise build it with: scripts\setup_runtime.ps1"
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
