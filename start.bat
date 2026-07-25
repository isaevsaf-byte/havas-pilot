@echo off
REM Havas Pilot Starter - запуск трекера посетителей

cd /d "%~dp0"

REM Активировать venv
call venv\Scripts\activate.bat

REM Установить переменные окружения
set HEADLESS=1
set SUPABASE_URL=
set SUPABASE_KEY=
set CAMERA_URL=rtsp://Division:ZAQwsx147!@173.30.11.254:8083/Streaming/Channels/2401
set STORE_NAME=havas_tashkent

REM Запустить скрипт
python main.py

pause
