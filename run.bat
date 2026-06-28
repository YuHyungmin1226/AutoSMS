@echo off
chcp 65001 > nul
setlocal

echo [Auto SMS Premium System] Initializing...

set "APP_DIR=%~dp0"
set "VENV_DIR=%APP_DIR%.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

cd /d "%APP_DIR%"

:: 1. Prepare isolated Python environment
if not exist "%PYTHON_EXE%" (
    echo Creating Python virtual environment...
    python -m venv "%VENV_DIR%"
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo [ERROR] Failed to create virtual environment.
        echo Please make sure Python is installed and available in PATH.
        pause
        exit /b 1
    )
)

echo Checking dependencies...
"%PYTHON_EXE%" -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

:: 2. Check for database
if not exist auto_sms.db (
    echo Database not found. Initializing database...
    "%PYTHON_EXE%" database.py
)

:: 3. Run the application
echo Starting the application. Please wait...
"%PYTHON_EXE%" app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application failed to start. 
    echo Please check the error message above.
    pause
    exit /b 1
)
