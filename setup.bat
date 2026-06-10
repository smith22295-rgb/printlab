@echo off
rem One-time setup on a new PC: clone the repo, double-click this.
cd /d %~dp0
echo Setting up PrintLab...
py -m venv venv
venv\Scripts\python.exe -m pip install --quiet --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe tools\make_icon.py
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $lnk = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\PrintLab.lnk'); $lnk.TargetPath = '%~dp0PrintLab.bat'; $lnk.WorkingDirectory = '%~dp0'; $lnk.IconLocation = '%~dp0assets\icon.ico'; $lnk.WindowStyle = 7; $lnk.Description = 'PrintLab - personal 3D print file maker'; $lnk.Save()"
echo(
echo Done. Double-click PrintLab on the Desktop to start it.
echo (First forge on this PC: if the Connect card appears, click Connect,
echo  and the engine will pick up your Claude desktop login.)
pause
