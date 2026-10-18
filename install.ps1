param(
    [ValidateSet('all','knit','cape','winter')][string]$Outfit = 'all',
    [string]$CodexHome = '',
    [switch]$DryRun,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
$arguments = @((Join-Path $PSScriptRoot 'tools/petctl.py'), 'install', '--outfit', $Outfit)
if ($CodexHome) { $arguments += @('--home', $CodexHome) }
if ($DryRun) { $arguments += '--dry-run' }
if ($Force) { $arguments += '--force' }
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 @arguments
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python @arguments
} else {
    throw 'Python 3.10+ is required. Alternatively copy the three folders under pets/ into $env:USERPROFILE/.codex/pets/.'
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
