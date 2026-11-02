@echo off
chcp 65001 >nul
cd /d "%~dp0"
call prepare_env.bat
pause
