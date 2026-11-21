@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3.11 -m venv .venv || goto fail
)
".venv\Scripts\python.exe" -c "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8517/_stcore/health', timeout=1).read().strip()==b'ok'" >nul 2>nul
if not errorlevel 1 (
    start "" "http://127.0.0.1:8517"
    exit /b 0
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt || goto fail
".venv\Scripts\python.exe" -m streamlit run dashboard.py --server.port 8517 --server.address 127.0.0.1 --browser.gatherUsageStats false
if errorlevel 1 goto fail
exit /b 0
:fail
echo Setup or startup failed. Check the message above and confirm Python 3.11 is installed.
pause
exit /b 1
