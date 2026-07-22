@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 尚未建立 Python 環境，請先執行：python -m venv .venv
  echo 然後執行：.venv\Scripts\python.exe -m pip install -e .
  pause
  exit /b 1
)
start "" http://127.0.0.1:4173
".venv\Scripts\python.exe" -m uvicorn google_route_generator.web:app --host 127.0.0.1 --port 4173
