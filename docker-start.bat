@echo off
chcp 65001 >nul
cd /d "%~dp0"

where docker >nul 2>&1
if errorlevel 1 (
  echo [错误] 未检测到 Docker。请先安装 Docker Desktop:
  echo   https://www.docker.com/products/docker-desktop/
  pause
  exit /b 1
)

echo ============================================
echo  智研AI · Docker 一键启动
echo ============================================
echo.
echo  模型说明:
echo  - Docker 内 Ollama 默认有独立目录，与本机已下载的模型是两套。
echo  - 若本机已有模型，可先创建 .env 并设置一行，避免重复下载:
echo      OLLAMA_MODELS_DIR=%USERPROFILE%\.ollama
echo  - 或本机 Ollama 已在运行时，可设置:
echo      OLLAMA_BASE_URL=http://host.docker.internal:11434
echo.

echo [1/3] 构建并启动容器（首次较慢，请耐心等待）...
docker compose up -d --build
if errorlevel 1 (
  echo [错误] 启动失败，请确认 Docker Desktop 已运行。
  pause
  exit /b 1
)

echo.
echo [2/3] 检查 AI 模型（已有则跳过下载）...
docker compose exec -T ollama ollama list 2>nul | findstr /I "qwen2.5" >nul
if errorlevel 1 (
  echo       未检测到 qwen2.5，开始拉取...
  docker compose exec -T ollama ollama pull qwen2.5:latest
) else (
  echo       已存在 qwen2.5，跳过下载
)

docker compose exec -T ollama ollama list 2>nul | findstr /I "embeddinggemma" >nul
if errorlevel 1 (
  echo       未检测到 embeddinggemma，开始拉取...
  docker compose exec -T ollama ollama pull embeddinggemma:latest
) else (
  echo       已存在 embeddinggemma，跳过下载
)

echo.
echo [3/3] 完成
echo ============================================
echo  浏览器打开:
echo    http://localhost:8080
echo.
echo  默认账号:
echo    管理员  admin / admin123
echo    用户    user  / user123
echo.
echo  常用命令:
echo    docker compose logs -f backend
echo    docker compose down
echo ============================================
pause
