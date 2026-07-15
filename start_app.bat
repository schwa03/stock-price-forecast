@echo off
echo ==============================================
echo Starting Servers...
echo ==============================================

cd /d "%~dp0"

echo 1. Starting Backend (FastAPI)...
start cmd /k "cd backend && set PYTHONUTF8=1&& .\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000"

echo 2. Starting Frontend (React/Vite)...
start cmd /k "cd frontend && npm run dev"

echo ==============================================
echo All processes started.
echo Please open http://localhost:5173 in your browser.
echo ==============================================
pause

