# Deprecated shim: the project was renamed to AG Music Tool Workbench.
# Use .\amtw.ps1 -- this forwards so old commands and notes keep working.
Write-Warning "vsr.ps1 is deprecated; use .\amtw.ps1"
& "$PSScriptRoot\amtw.ps1" @args
exit $LASTEXITCODE
