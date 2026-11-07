@echo off
setlocal
title Leafline admin tools
cd /d "%~dp0tools"
if not exist .env (echo tools\.env is missing. Run RUN_SETUP.bat first. & pause & exit /b 1)
python --version >nul 2>&1 || (echo Python was not found. Install Python and tick "Add to PATH". & pause & exit /b 1)
python -m pip install requests tzdata --quiet

:menu
cls
echo ==========================================
echo   Leafline admin tools  (this computer only)
echo ==========================================
echo.
echo   1  Add a new employee
echo   2  Reset someone's password
echo   3  Reactivate someone who was deactivated
echo   4  Back up the shared database now
echo   5  Check the database is healthy
echo   6  Quit
echo.
echo   (To deactivate someone, use the Admin page inside the app.)
echo.
set "C="
set /p C=Choose 1-6: 
if "%C%"=="1" goto add
if "%C%"=="2" goto reset
if "%C%"=="3" goto react
if "%C%"=="4" goto backup
if "%C%"=="5" goto check
if "%C%"=="6" exit /b 0
goto menu

:askname
set "N="
set /p N=First name (letters only, e.g. Sarah): 
echo %N%| findstr /r /c:"^[A-Za-z][A-Za-z]*$" >nul || (echo That is not a valid name. & set "N=")
exit /b 0

:add
call :askname
if "%N%"=="" (pause & goto menu)
python seed_users.py add %N%
echo.
echo Give them the temporary password above. They must choose their own at first sign-in.
echo Their login name is: %N%
pause & goto menu

:reset
call :askname
if "%N%"=="" (pause & goto menu)
python seed_users.py reset %N%
pause & goto menu

:react
call :askname
if "%N%"=="" (pause & goto menu)
python seed_users.py reactivate %N%
pause & goto menu

:backup
if not exist "%~dp0backups" mkdir "%~dp0backups"
python backup.py "%~dp0backups"
echo.
echo Saved in the backups folder next to this file.
pause & goto menu

:check
python verify_db.py
pause & goto menu
