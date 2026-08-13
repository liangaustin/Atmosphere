@echo off
chcp 65001 >nul
title 风速仪表盘
cd /d "%~dp0"
echo ============================================
echo   风速仪表盘启动中...
echo   启动后浏览器打开 http://localhost:3000
echo   关闭本窗口 = 停止仪表盘
echo ============================================
node server.js
pause
