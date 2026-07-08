@echo off
echo Starting FastAPI Backend Server on 0.0.0.0:8000
cd backend
call venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
