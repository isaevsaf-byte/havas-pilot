@echo off
REM Havas Pilot Starter - запуск трекера посетителей

cd /d "%~dp0"

REM Активировать venv
call venv\Scripts\activate.bat

REM Установить переменные окружения
set HEADLESS=1
set SUPABASE_URL=
set SUPABASE_KEY=
set CAMERA_URL=rtsp://admin:123654cpq@172.30.11.254:8083/ISAPI/Streaming/Channels/2401
set STORE_NAME=havas_tashkent

REM Запустить скрипт
python main.py

pause
