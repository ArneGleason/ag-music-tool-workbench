# Minimal runtime for the harmony and Bitwig tools.
#
# setup_runtime.ps1 builds everything: five venvs, CUDA torch, model
# checkpoints, several GB. That is the vocal-restoration pipeline, and none of
# it is needed to read chords, reduce them to a line, or talk to Bitwig.
# Those tools need Python and mido.
#
# This creates the SAME venv (venvs\main) that setup_runtime.ps1 uses, so
# running the full setup later tops this up rather than conflicting with it.
#
# ASCII ONLY -- see the note in amtw.ps1.
[CmdletBinding()]
param(
    # Where the runtime lives. Defaults to what amtw.ps1 and core/paths.py look
    # for; override to test without touching a real install.
    [string]$RuntimeRoot = (Join-Path $env:LOCALAPPDATA "VocalStemRegen"),

    # numpy + soundfile, so harm-render's built-in synth works. About 30 MB.
    # Without them the analysis tools still run; only rendering is unavailable.
    [switch]$WithAudio
)

$ErrorActionPreference = "Stop"

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $pyLauncher) {
    Write-Host "Python launcher 'py' not found. Install Python 3.12 first." -ForegroundColor Red
    exit 1
}

$venv = Join-Path $RuntimeRoot "venvs\main"
$venvPy = Join-Path $venv "Scripts\python.exe"

Write-Host "runtime root : $RuntimeRoot"
Write-Host "venv         : $venv"
Write-Host ""

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

if (Test-Path -LiteralPath $venvPy) {
    Write-Host "venv already exists, reusing it"
} else {
    Write-Host "creating venv with py -3.12 ..."
    & py -3.12 -m venv $venv
    if ($LASTEXITCODE -ne 0) { Write-Host "venv creation failed" -ForegroundColor Red; exit 1 }
}

Write-Host "upgrading pip ..."
& $venvPy -m pip install -q -U pip

# mido is the whole dependency for reading and writing MIDI, which is all the
# harmony analysis, the reducer and the Bitwig bridge actually touch.
$packages = @("mido")
if ($WithAudio) { $packages += @("numpy", "soundfile") }

Write-Host ("installing: " + ($packages -join ", ") + " ...")
& $venvPy -m pip install -q @packages
if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "checking what the workbench can now do:" -ForegroundColor Cyan
Write-Host "(FAIL lines for venvs, clones and checkpoints are EXPECTED here --"
Write-Host " those belong to the vocal pipeline, which this setup skips.)"
Write-Host ""
Push-Location $PSScriptRoot\..
try {
    # Point paths.py at the root we just built. Without this it resolves
    # LOCALAPPDATA and reports on a different runtime than the one installed,
    # which is only visible when -RuntimeRoot is overridden -- exactly when
    # someone is least able to spot it.
    $prev = $env:AMTW_RUNTIME
    $env:AMTW_RUNTIME = $RuntimeRoot
    try { & $venvPy -m amtw doctor } finally { $env:AMTW_RUNTIME = $prev }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Ready. Try:" -ForegroundColor Green
Write-Host '  .\amtw.ps1 harm-read "path\to\chords.mid" --readings'
Write-Host "  .\amtw.ps1 harm-reduce `"path\to\chords.mid`" --mode smooth"
Write-Host "  .\amtw.ps1 bitwig-bridge"
Write-Host ""
Write-Host "Tools needing the audio stack (run, harmonic, detect, defizz, remod)"
Write-Host "will show as unavailable until scripts\setup_runtime.ps1 has run."
if (-not $WithAudio) {
    Write-Host "harm-render needs -WithAudio; re-run this with that switch to add it."
}
