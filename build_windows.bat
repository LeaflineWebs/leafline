@echo off
REM ============================================================
REM  Double-click this file to build the Windows installer:
REM    Leafline-Lead-Finder-Setup-VERSION.exe (in the dist folder)
REM  Needs (install once): Python 3.10+  and  Node.js LTS
REM ============================================================
setlocal
cd /d "%~dp0"
title Building Leafline Lead Finder installer

findstr /c:"leafline-lead-finder" package.json >nul 2>&1 || (
  echo This is not the leafline-app folder, or its package.json was replaced.
  echo Delete any package.json / package-lock.json you made yourself and use the ones from the zip.
  goto :fail
)

REM --- Windows blocks build tools in Downloads / Desktop / Documents / OneDrive. Build from a plain folder instead.
if not "%LEAFLINE_MOVED%"=="1" (
  echo %CD% | findstr /i /c:"\Downloads" /c:"\Desktop" /c:"\Documents" /c:"OneDrive" >nul && (
    set "DEST=%LOCALAPPDATA%\LeaflineBuild"
    echo Copying the project to %LOCALAPPDATA%\LeaflineBuild so Windows does not block the build...
    robocopy "%CD%" "%LOCALAPPDATA%\LeaflineBuild" /E /XD node_modules dist backend-dist pyi /NFL /NDL /NJH /NJS /NP >nul
    if errorlevel 8 goto :fail
    set LEAFLINE_MOVED=1
    cd /d "%LOCALAPPDATA%\LeaflineBuild"
    call build_windows.bat
    exit /b %errorlevel%
  )
)

set PY=python
where python >nul 2>&1 || set PY=py
%PY% --version >nul 2>&1 || (
  echo Python is not installed. Get it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  start https://www.python.org/downloads/
  goto :fail
)
where node >nul 2>&1 || (
  echo Node.js is not installed. Get the LTS version from https://nodejs.org/ then run this again.
  start https://nodejs.org/
  goto :fail
)

powershell -NoProfile -Command "Get-ChildItem -Recurse -File '%CD%' | Unblock-File" >nul 2>&1

echo [1/4] Installing Python packages...
%PY% -m pip install -r requirements.txt || goto :fail
if exist backend-dist rmdir /s /q backend-dist

echo [2/4] Packaging the app engine...
%PY% -m PyInstaller --noconfirm --name leafline_backend --distpath backend-dist --workpath build\pyi --specpath build\pyi --collect-all playwright --collect-data tzdata backend\leafline_backend.py || goto :fail

echo [3/4] Installing Electron (first time takes a few minutes)...
call npm install || goto :fail
node tools\set_repo.js

REM --- The installer step runs a small helper program from the Windows temp folder, which security software can block (spawn EPERM).
REM --- Use a temp folder inside this build folder instead (the same folder Defender is told to skip).
if not exist "%CD%\.tmp" mkdir "%CD%\.tmp"
set "TEMP=%CD%\.tmp"
set "TMP=%CD%\.tmp"

echo Checking that Windows lets the installer tool run...
call :canrun
if errorlevel 1 (
  echo.
  echo Windows security is blocking a build tool ^(this is the "spawn EPERM" error^).
  echo A Windows permission prompt will open now. Click Yes - it only tells Windows Defender
  echo to skip THIS build folder: %CD%
  powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-Command','Add-MpPreference -ExclusionPath ''%CD%'''" >nul 2>&1
  timeout /t 3 >nul
  call :canrun
  if errorlevel 1 (
    echo.
    echo Still blocked. Another antivirus or Windows "Controlled folder access" is stopping it.
    echo Fix: open your antivirus ^(or Windows Security ^> Virus ^& threat protection ^> Manage settings^),
    echo add this folder as an exclusion: %CD%
    echo and, if you see "Protection history", allow app-builder.exe. Then run this file again.
    goto :fail
  )
)

echo [4/4] Building the installer...
call npm run dist:win || goto :fail

echo.
echo ============================================================
echo  Done! Opening the folder with your installer...
echo ============================================================
explorer "%CD%\dist"
pause
exit /b 0

:canrun
node -e "const r=require('child_process').spawnSync(process.argv[1],['--help'],{timeout:20000});process.exit(r.error?1:0)" "%CD%\node_modules\app-builder-bin\win\x64\app-builder.exe"
exit /b %errorlevel%

:fail
echo.
echo Build stopped - read the message above. Copy it to Claude if you need help.
pause
exit /b 1
