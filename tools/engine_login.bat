@echo off
title PrintLab - one-time engine login
set "CLAUDE=%~1"
if "%CLAUDE%"=="" (
  for /f "delims=" %%D in ('dir /b /ad /o-d "%APPDATA%\Claude\claude-code" 2^>nul') do (
    if not defined CLAUDE set "CLAUDE=%APPDATA%\Claude\claude-code\%%D\claude.exe"
  )
)
if not exist "%CLAUDE%" (
  echo Could not find the Claude engine on this PC.
  pause
  exit /b 1
)
echo(
echo  ============================================================
echo   PRINTLAB - ONE-TIME ENGINE LOGIN
echo(
echo   1. Claude opens below.
echo   2. Type /login and press Enter.
echo   3. Pick your Claude account and finish in the browser.
echo   4. Once it says you're logged in, close this window.
echo  ============================================================
echo(
"%CLAUDE%"
echo(
pause
