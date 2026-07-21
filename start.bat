@echo off
REM Havas Pilot Starter - запуск трекера посетителей

cd /d "%~dp0"

REM Активировать venv
call venv\Scripts\activate.bat

REM Установить переменные окружения
set HEADLESS=1
set SUPABASE_URL=
set SUPABASE_KEY=
set CAMERA_URL=rtsp://admin:admin@192.168.1.64:554/stream1
set STORE_NAME=havas_tashkent

REM Запустить скрипт
python main.py

pause
