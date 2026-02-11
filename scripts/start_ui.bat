@echo off
setlocal
set SCRIPT_DIR=%~dp0
for %%I in ("%SCRIPT_DIR%..") do set REPO_ROOT=%%~fI
cd /d "%REPO_ROOT%"
title AutoSD UI Launcher
where autosd >nul 2>&1
if errorlevel 1 (
  echo autosd command not found.
  echo Install with: py -3.11 -m pip install -e .[dev]
  exit /b 1
)
autosd ui serve %*
exit /b %errorlevel%
