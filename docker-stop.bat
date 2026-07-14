@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 停止并移除容器（数据卷保留）...
docker compose down
echo 完成。
pause
