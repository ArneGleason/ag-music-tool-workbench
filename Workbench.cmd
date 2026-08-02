@echo off
rem Double-click this to open the workbench. Pin it to the taskbar or put a
rem shortcut on the desktop -- it is the only entry point you should need.
rem
rem It opens a console window: THAT WINDOW IS THE SERVER. Close it to stop.
rem Closing the browser tab does not stop it.
rem
rem The window is deliberately not minimised. It used to be, which meant any
rem startup failure scrolled past inside a hidden window and the whole thing
rem just looked like "double-click does nothing".
cd /d "%~dp0"
set PY=%LOCALAPPDATA%\VocalStemRegen\venvs\main\Scripts\python.exe
if not exist "%PY%" (
    echo main venv missing at "%PY%" -- run scripts\setup_runtime.ps1, see README.
    pause
    exit /b 1
)
start "AG Music Tool Workbench" "%PY%" -m amtw workbench
