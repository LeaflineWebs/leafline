@echo off
REM Runs the app from source (no installer). Needs Python 3.10+ and Node.js 18+.
setlocal
cd /d "%~dp0"
if not exist package.json (echo Run this from the leafline-app folder & pause & exit /b 1)
findstr /c:"leafline-lead-finder" package.json >nul || (echo This folder's package.json is not the Leafline one. Delete it and use the one from the zip. & pause & exit /b 1)
python -m pip install requests playwright tzdata || (pause & exit /b 1)
if not exist node_modules call npm install || (pause & exit /b 1)
call npm start
pause
