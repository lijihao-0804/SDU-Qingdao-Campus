@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
if defined SDU_PYTHON goto override_python
if exist "%~dp0运行环境\Python\python.exe" goto bundled_python
if exist "%~dp0..\运行环境\Python\python.exe" goto parent_python
if exist "%~dp0.venv\Scripts\python.exe" goto venv_python
where py.exe >nul 2>nul
if errorlevel 1 goto plain_python
py -3.11 -B -X utf8 "%~dp0tools\rebuild_portable.py" %*
goto finish
:plain_python
python -B -X utf8 "%~dp0tools\rebuild_portable.py" %*
goto finish
:override_python
set "RUNPY=%SDU_PYTHON%"
goto run
:bundled_python
set "RUNPY=%~dp0运行环境\Python\python.exe"
goto run
:parent_python
set "RUNPY=%~dp0..\运行环境\Python\python.exe"
goto run
:venv_python
set "RUNPY=%~dp0.venv\Scripts\python.exe"
:run
"%RUNPY%" -B -X utf8 "%~dp0tools\rebuild_portable.py" %*
:finish
set "rc=%errorlevel%"
if "%~1"=="" pause
exit /b %rc%
