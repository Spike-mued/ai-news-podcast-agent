@echo off
chcp 65001 >nul
title AI-News-Podcast-Agent

echo ==============================================
echo   AI News Podcast Agent
echo   24/7 不间断AI新闻播客系统
echo ==============================================
echo.

cd /d "%~dp0"

echo [1/2] Installing dependencies...
pip install -e . >nul 2>&1
if %errorlevel% neq 0 (
    echo Warning: pip install failed, trying with --no-deps...
    pip install -e . --no-deps
)

echo [2/2] Starting server on port 9800...
echo.
echo Web UI:     http://localhost:9800
echo API Docs:  http://localhost:9800/docs
echo Health:    http://localhost:9800/api/health
echo.
echo Press Ctrl+C to stop
echo ==============================================
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 9800 --reload
pause
