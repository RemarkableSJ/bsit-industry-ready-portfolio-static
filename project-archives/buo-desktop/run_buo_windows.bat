@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Buo is not set up yet. Run setup_buo_windows.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python main.py
if errorlevel 1 (
  echo Buo closed with an error. Read the traceback above and share it for troubleshooting.
  pause
)
