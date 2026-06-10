@echo off
cd /d %~dp0
start "PrintLab Server" /min venv\Scripts\python.exe app.py
timeout /t 2 /nobreak >nul
set EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe
if exist "%EDGE%" (
  start "" "%EDGE%" --app=http://127.0.0.1:8123
) else (
  start "" http://127.0.0.1:8123
)
