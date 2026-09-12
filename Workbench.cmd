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
start "AG Music Tool Workbench" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0amtw.ps1" workbench
