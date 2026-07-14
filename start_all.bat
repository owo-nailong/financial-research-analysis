@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set NO_PROXY=127.0.0.1,localhost
set no_proxy=127.0.0.1,localhost
set HTTP_PROXY=
set HTTPS_PROXY=

if not exist "logs" mkdir logs

echo [1/2] Starting FastAPI on http://127.0.0.1:8010 ...
start "智研AI-后端" /MIN cmd /c "cd /d "%~dp0" && set NO_PROXY=127.0.0.1,localhost&& set HTTP_PROXY=&& set HTTPS_PROXY=&& python -c "import sys; sys.path.insert(0, r'%~dp0backend'); import uvicorn; uvicorn.run('main:app', host='127.0.0.1', port=8010, reload=False)" >> "%~dp0logs\backend.log" 2>&1"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Vue frontend on http://127.0.0.1:5173 ...
start "智研AI-前端" /MIN cmd /c "cd /d "%~dp0frontend" && set NO_PROXY=127.0.0.1,localhost&& set HTTP_PROXY=&& set HTTPS_PROXY=&& npm.cmd run dev -- --host 127.0.0.1 --port 5173 >> "%~dp0logs\frontend.log" 2>&1"

timeout /t 5 /nobreak >nul

echo.
echo ============================================
echo  请用浏览器打开:
echo    http://127.0.0.1:5173
echo  后端 API:
echo    http://127.0.0.1:8010/api/health
echo  日志目录:
echo    %~dp0logs\
echo ============================================
echo  说明: 两个窗口最小化在后台运行。
echo  关掉对应标题的窗口才会停服务。
echo  不要依赖 AI 对话会话里的临时进程。
echo ============================================
echo.
pause
