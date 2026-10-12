@echo off
rem ASCII only. UTF-8 text makes cmd.exe split "%~dp0" into the bogus command p0".
cd /d "%~dp0"

set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (where py >nul 2>nul && set "PY=py -3")
if not defined PY set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"

if not defined PY (
  echo [x] Python was not found. Install Python 3 and add it to PATH.
  pause
  exit /b 1
)

echo [i] Python: %PY%
%PY% serve.py %*
if errorlevel 1 pause
