@echo off
setlocal
cd /d "%~dp0"

echo Setting up the shared StarCraft II bot environment...

if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if errorlevel 1 goto :failed
)

".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :failed

".venv\Scripts\python.exe" -c "import sc2; print('Python packages are ready.')"
if errorlevel 1 goto :failed

echo.
echo Setup complete. Double-click run_match.bat to start a match.
pause
exit /b 0

:failed
echo.
echo Setup failed. Check that Python 3.10 or newer is installed, then try again.
pause
exit /b 1
