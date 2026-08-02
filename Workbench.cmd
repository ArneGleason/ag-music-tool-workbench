@echo off
rem Double-click this to open the workbench. Pin it to the taskbar or put a
rem shortcut on the desktop -- it is the only entry point you should need.
rem
rem It opens a minimised console window: that is the server. Close it to stop.
cd /d "%~dp0"
set PY=%LOCALAPPDATA%\VocalStemRegen\venvs\main\Scripts\python.exe
if not exist "%PY%" (
    echo main venv missing at "%PY%" -- run scripts\setup_runtime.ps1, see README.
    pause
    exit /b 1
)
start "AG Music Tool Workbench" /min "%PY%" -m amtw workbench
