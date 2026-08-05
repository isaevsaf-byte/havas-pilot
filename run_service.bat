@echo off
REM Havas Pilot - боевой сервис с автоперезапуском
REM Запускается через Планировщик заданий Windows при старте системы

cd /d "%~dp0"

REM Активировать venv
call venv\Scripts\activate.bat

REM Установить переменные окружения
set HEADLESS=1
set SUPABASE_URL=
set SUPABASE_KEY=
set CAMERA_URL=rtsp://Division:ZAQwsx147!@172.30.11.254:8084/Streaming/Channels/2402
set STORE_NAME=havas_tashkent

REM Папка для логов
if not exist logs mkdir logs

:loop
echo [%date% %time%] Запуск main.py >> logs\service.log
python main.py >> logs\service.log 2>&1
echo [%date% %time%] main.py остановился, перезапуск через 10 сек >> logs\service.log
ping -n 11 127.0.0.1 >nul
goto loop
