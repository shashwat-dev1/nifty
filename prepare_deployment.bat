@echo off
cd /d "%~dp0"
call npm --prefix web ci
if errorlevel 1 goto fail
call npm --prefix web run build
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -X utf8 -m private_demo.session check
if errorlevel 1 goto fail
echo READY: Local deployment checks passed. No public tunnel was started.
pause
exit /b 0
:fail
echo NOT READY: A required check failed. Do not start sharing.
pause
exit /b 1
