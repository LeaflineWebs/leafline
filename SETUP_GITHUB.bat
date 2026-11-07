@echo off
REM ============================================================
REM  Run this ONCE. It remembers which GitHub repository holds your app,
REM  so the website and the desktop updates know where to look.
REM ============================================================
setlocal
cd /d "%~dp0"
title Leafline - connect to GitHub
echo.
echo  1) Make a free account at https://github.com  (skip if you have one)
echo  2) Click the + at the top right -^> New repository
echo     Name it  leafline   (or anything you like)
echo     Choose PUBLIC.  Do NOT tick "Add a README".  Click Create repository.
echo.
set /p GHUSER=Type your GitHub username and press Enter: 
if "%GHUSER%"=="" goto :eof
set "GHREPO=leafline"
set /p GHREPO=Repository name (press Enter for "leafline"): 
if "%GHREPO%"=="" set "GHREPO=leafline"
> github.txt echo # Written by SETUP_GITHUB.bat:  your-github-username/repository-name
>> github.txt echo %GHUSER%/%GHREPO%
where node >nul 2>&1 && node tools\set_repo.js
echo.
echo  Saved. Your website will be:  https://%GHUSER%.github.io/%GHREPO%/
echo  Next: double-click PUSH_UPDATE.bat
echo.
pause
