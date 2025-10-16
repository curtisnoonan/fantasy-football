@echo off
setlocal
cd /d %~dp0

REM Try Python Launcher first, then fallback to python
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -m prop_recommender.gui %*
) else (
  python -m prop_recommender.gui %*
)

endlocal

