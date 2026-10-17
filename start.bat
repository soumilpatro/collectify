@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto error
)
".venv\Scripts\python.exe" -c "import flask, sqlalchemy, PIL, pymysql, psycopg" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto error
)
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto error
exit /b 0
:error
echo Setup failed. Install Python 3.11 or newer and follow README.md.
pause
exit /b 1
