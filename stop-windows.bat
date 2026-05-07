@echo off
chcp 65001 >nul
echo Stopping AI News Podcast Agent...
taskkill /f /im uvicorn.exe >nul 2>&1
taskkill /f /im python.exe /fi "WINDOWTITLE eq AI-News-Podcast-Agent*" >nul 2>&1
echo Done.
pause
