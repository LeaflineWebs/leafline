@echo off
REM ============================================================
REM  Double-click to publish the latest version to EVERYONE:
REM    - the website (and every phone with it on the home screen)
REM    - the desktop apps (they update themselves next time they open)
REM  Needs Git (free):  https://git-scm.com/download/win   (install once, accept the defaults)
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Leafline - publish update

where git >nul 2>&1 || (
  echo Git is not installed. Opening the download page. Install it with the default options, then run this again.
  start https://git-scm.com/download/win
  goto :fail
)
set PY=python
where python >nul 2>&1 || set PY=py
%PY% --version >nul 2>&1 || ( echo Python is not installed. & goto :fail )
set REPO=
for /f "usebackq eol=# tokens=*" %%r in ("github.txt") do if not defined REPO set "REPO=%%r"
echo %REPO% | findstr /i "YOUR-GITHUB" >nul && (
  echo You have not connected GitHub yet. Run SETUP_GITHUB.bat first.
  goto :fail
)
if not defined REPO ( echo github.txt is empty. Run SETUP_GITHUB.bat first. & goto :fail )

echo [1/5] Building the website from the app...
%PY% tools\build_web.py || goto :fail

if exist github_workflows (
  if not exist .github\workflows mkdir .github\workflows
  copy /y github_workflows\*.yml .github\workflows\ >nul
)

echo [2/5] Getting the files ready...
if not exist .git (
  git init -q || goto :fail
  git branch -M main
)
git remote get-url origin >nul 2>&1 || git remote add origin https://github.com/%REPO%.git
for /f "delims=" %%n in ('git config user.name') do set GN=%%n
if not defined GN git config user.name "Leafline"
for /f "delims=" %%n in ('git config user.email') do set GE=%%n
if not defined GE git config user.email "leafline@users.noreply.github.com"
git add -A

echo [3/5] Safety check: no private keys may leave this computer...
git diff --cached --name-only | findstr /i /r "\.env$ session\.json \.db$" >nul && (
  echo STOPPED: a private file was about to be published. It was not sent.
  git reset -q
  goto :fail
)
git grep -I -n -E --cached "sb_secre[t]_" -- . ":(exclude)tests" >nul 2>&1 && (
  echo STOPPED: a secret key was found in a file that was about to be published. It was not sent.
  git reset -q
  goto :fail
)

set "MSG=Update"
set /p MSG=What changed? (short note, or just press Enter): 
if "!MSG!"=="" set "MSG=Update"
git commit -q -m "!MSG!" >nul 2>&1
echo [4/5] Publishing the website...
git push -u origin main >nul 2>&1 || (
  echo Merging with what is already on GitHub, then trying again...
  git pull origin main --no-rebase --allow-unrelated-histories -X ours --no-edit >nul 2>&1
  git push -u origin main
) || (
  echo Replacing the older copy on GitHub with this one...
  git push --force -u origin main
) || (
  echo.
  echo The upload did not work. Common reasons:
  echo  - The repository %REPO% does not exist yet, or was created with a README. Create a NEW empty one.
  echo  - Windows asked you to sign in to GitHub and it was closed. Run this again and sign in.
  goto :fail
)

for /f %%v in ('node -p "require('./package.json').version"') do set VER=%%v
git rev-parse "v%VER%" >nul 2>&1 && (
  echo [5/5] Desktop version %VER% was already published. Nothing new for the desktop apps.
  goto :done
)
echo [5/5] Publishing desktop version %VER% (the installer is built online, about 8 minutes)...
git tag "v%VER%" && git push origin "v%VER%" || goto :fail
:done
echo.
echo  Done.
echo   Website : https://%REPO:/=.github.io/%/   (updates within about a minute)
echo   Desktop : https://github.com/%REPO%/actions   (watch the build; apps update when it finishes)
echo.
pause
exit /b 0
:fail
echo.
echo  Not published. Fix the message above and run this again.
pause
exit /b 1
