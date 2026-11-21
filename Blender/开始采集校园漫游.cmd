@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONNOUSERSITE=1"
set "RUNPY=%~dp0运行环境\Python\python.exe"
if not exist "%RUNPY%" (
    echo 请完整解压工程，找不到包内的运行环境。
    if "%~1"=="" pause
    exit /b 1
)
"%RUNPY%" -B -X utf8 -u "%~dp0tools\bay_film\manual_capture.py" %*
set "RESULT=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %RESULT%
