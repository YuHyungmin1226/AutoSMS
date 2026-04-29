@echo off
chcp 65001 > nul
echo [Auto SMS Premium System] Initializing...

:: 1. Check for database
if not exist auto_sms.db (
    echo Database not found. Initializing database...
    python database.py
)

:: 2. Run the application
echo Starting the application. Please wait...
python app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application failed to start. 
    echo Please check if all requirements are installed: pip install -r requirements.txt
    pause
)
