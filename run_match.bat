@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo The match environment is not set up yet.
    echo Double-click setup.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" run_match.py %*
set "match_exit=%errorlevel%"
echo.
pause
exit /b %match_exit%
