@echo off
rem Double-click to start the website: runs the Flask server and opens the browser.
rem   /              ResRec website
rem   /classic.html  original dashboard (with CSV upload)
cd /d "%~dp0"
set PORT=8000

if not exist ".venv\Scripts\python.exe" (
  echo .venv not found. Create it first:
  echo   python -m venv .venv
  echo   .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)

rem Server runs in its own window; close that window to stop it.
start "ResRec server - close to stop" ".venv\Scripts\python.exe" src\app.py %PORT%

echo Waiting for the server (the model takes a few seconds to load) ...
set TRIES=0
:wait
curl.exe -s -o nul http://localhost:%PORT%/ && goto ready
set /a TRIES+=1
if %TRIES% geq 60 (
  echo Server did not start. Check the "ResRec server" window for the error.
  pause
  exit /b 1
)
ping -n 2 127.0.0.1 >nul
goto wait

:ready
echo Opening http://localhost:%PORT%/
start "" http://localhost:%PORT%/
