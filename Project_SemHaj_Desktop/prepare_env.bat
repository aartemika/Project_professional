@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Готовит папку .venv на этом компьютере. Вызывается из run.bat, run_analysis.bat и setup.bat.

if not exist ".venv\Scripts\python.exe" goto create
".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
if not errorlevel 1 goto install
echo Папка .venv создана на другом компьютере. Создаю заново...
rmdir /s /q ".venv"

:create
echo Первый запуск на этом компьютере: создаю окружение. Это займёт несколько минут, нужен интернет.
set "PY="
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY goto check
python -c "import sys" >nul 2>&1
if not errorlevel 1 set "PY=python"
if not defined PY goto nopython

:check
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto oldpython
%PY% -m venv .venv
if errorlevel 1 goto fail

:install
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto fail
exit /b 0

:nopython
echo Python не найден. Установите Python 3.10 или новее с сайта python.org, отметьте «Add python.exe to PATH» и запустите файл снова.
exit /b 1

:oldpython
echo Нужен Python 3.10 или новее. Установите свежий с сайта python.org и запустите файл снова.
exit /b 1

:fail
echo Не удалось подготовить окружение. Проверьте интернет и запустите файл ещё раз.
exit /b 1
