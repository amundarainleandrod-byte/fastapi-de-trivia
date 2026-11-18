@echo off
setlocal

cd /d "%~dp0"

echo Instalando dependencias...
py -m pip install -r requirements.txt
if errorlevel 1 (
    python -m pip install -r requirements.txt
)

echo.
echo Iniciando el servidor en http://127.0.0.1:8000
echo (Presiona Ctrl+C para detener)
echo.

py main.py
if errorlevel 1 (
    python main.py
)
if errorlevel 1 (
    py -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
)
if errorlevel 1 (
    python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
)

pause
