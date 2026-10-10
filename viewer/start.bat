@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (where py >nul 2>nul && set "PY=py -3")
if not defined PY set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"

if not defined PY (
  echo [x] 未找到 Python，请先安装 Python 3 并加入 PATH
  pause
  exit /b 1
)

echo [i] 使用解释器: %PY%
%PY% serve.py %*
if errorlevel 1 pause
