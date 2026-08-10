@echo off
rem One-click launcher for THE LAST REACTOR (double-click me!)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
if errorlevel 1 pause
