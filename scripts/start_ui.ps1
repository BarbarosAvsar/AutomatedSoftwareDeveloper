$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'AutoSD UI Launcher'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir '..')).Path
Set-Location $RepoRoot

Write-Host 'Launching AutoSD UI...' -ForegroundColor Cyan
if (-not (Get-Command autosd -ErrorAction SilentlyContinue)) {
  Write-Host 'autosd command not found.' -ForegroundColor Red
  Write-Host 'Install with: py -3.11 -m pip install -e .[dev]' -ForegroundColor Yellow
  exit 1
}

autosd ui serve @args
exit $LASTEXITCODE
