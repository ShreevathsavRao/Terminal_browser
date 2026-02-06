@echo off
REM Run script for Terminal Browser (Windows)

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed. Please install Python 3.7 or higher.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
if not exist "venv\installed" (
    echo Installing dependencies...
    pip install -r requirements.txt
    type nul > venv\installed
)

REM Run the application
echo Starting Terminal Browser...
python main.py

REM Deactivate virtual environment
deactivate

