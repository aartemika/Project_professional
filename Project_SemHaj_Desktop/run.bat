@echo off
chcp 65001 >nul
cd /d "%~dp0"
call prepare_env.bat
if errorlevel 1 (
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py
pause
