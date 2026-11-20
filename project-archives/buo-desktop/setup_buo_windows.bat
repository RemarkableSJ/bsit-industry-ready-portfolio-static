@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher was not found. Install Python 3.13 or 3.12 from python.org and enable the Python Launcher.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  py -3.13 -m venv .venv 2>nul
  if errorlevel 1 py -3.12 -m venv .venv
  if errorlevel 1 (
    echo Could not create the virtual environment. Install Python 3.13 or 3.12.
    pause
    exit /b 1
  )
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements-desktop.txt
if errorlevel 1 (
  echo Dependency installation failed. Check internet access and Python version.
  pause
  exit /b 1
)
echo.
echo Buo desktop dependencies installed successfully.
echo Run run_buo_windows.bat to start the app.
pause
