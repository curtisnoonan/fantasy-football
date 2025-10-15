@echo off
REM Launch the Fantasy Football Config GUI
SETLOCAL ENABLEDELAYEDEXPANSION

REM Navigate to the repo root (this script's directory)
set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%"

REM Prefer virtualenv pythonw if present
set PY=".\.venv\Scripts\pythonw.exe"
if exist %PY% goto run

REM Otherwise try system pythonw, then python
where pythonw >NUL 2>&1
if %ERRORLEVEL%==0 (
  set PY=pythonw
) else (
  set PY=python
)

:run
%PY% -m fantasy_football.gui
if %ERRORLEVEL% NEQ 0 (
  echo GUI failed with %PY%. Falling back to console python for error details...
  python -m fantasy_football.gui
  pause
)

popd
ENDLOCAL

