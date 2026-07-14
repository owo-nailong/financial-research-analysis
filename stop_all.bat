@echo off
chcp 65001 >nul
echo Stopping listeners on 8010 / 5173 ...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8010 .*LISTENING"') do taskkill /F /PID %%p 2>nul
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 .*LISTENING"') do taskkill /F /PID %%p 2>nul
echo Done.
pause
