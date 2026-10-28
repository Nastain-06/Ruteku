@echo off
title Server Ruteku (FastAPI + Mobile Ready)
cd /d "%~dp0backend"
set "PYTHONPATH=%~dp0backend\.venv\Lib\site-packages;%~dp0backend"
set "UV_PY=%APPDATA%\uv\python\cpython-3.12-windows-x86_64-none\python.exe"
echo ===================================================
echo   Menjalankan Server Ruteku di Port 8000...
echo   - Buka di Laptop : http://localhost:8000
echo   - Buka via IP    : http://127.0.0.1:8000
echo   - Swagger API    : http://localhost:8000/docs
echo   (Jangan tutup jendela ini selama membuka web)
echo ===================================================
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8000"
if exist "%UV_PY%" (
    "%UV_PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
) else (
    .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
)
pause
