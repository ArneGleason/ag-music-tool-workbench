# One resolver for launchers and installers. LOCALAPPDATA can be virtualized
# by packaged apps (Claude); a per-user pointer prevents a second installation.
$ErrorActionPreference = 'Stop'
if ($env:AMTW_RUNTIME) { return $env:AMTW_RUNTIME.Trim() }
if ($env:VSR_RUNTIME) { return $env:VSR_RUNTIME.Trim() }
$pointer = Join-Path $env:USERPROFILE '.config\amtw\runtime.json'
if (Test-Path -LiteralPath $pointer) {
    $config = Get-Content -LiteralPath $pointer -Raw | ConvertFrom-Json
    if (-not $config.runtime_root) { throw "runtime_root missing in $pointer" }
    return [string]$config.runtime_root
}
# Fallbacks support existing installs. Prefer a complete model runtime over a
# harmony-only runtime, but do not search the entire drive on every launch.
$candidates = @(
    (Join-Path $env:USERPROFILE 'AppData\Local\VocalStemRegen'),
    (Join-Path $env:USERPROFILE 'AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\VocalStemRegen')
)
foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath (Join-Path $candidate 'models\apollo\model_apollo_vocals_ep_54.ckpt')) { return $candidate }
}
foreach ($candidate in $candidates) { if (Test-Path -LiteralPath $candidate) { return $candidate } }
return $candidates[0]
