@echo off
REM Portin Quick Setup for Windows
REM Double-click this file to set up the project automatically

echo ========================================
echo Portin Setup Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed!
    echo Please install Python 3.9+ from https://python.org/downloads
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [1/6] Creating virtual environment...
python -m venv venv 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Standard venv failed, trying without pip...
    python -m venv venv --without-pip
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment
        echo.
        echo SOLUTION: Install Python from python.org (not Microsoft Store)
        echo           Make sure to check "Add Python to PATH" during installation
        pause
        exit /b 1
    )
)

echo [2/6] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/6] Ensuring pip is installed...
REM Check if pip exists in venv
if not exist "venv\Scripts\pip.exe" (
    echo [INFO] Pip not found, installing manually...
    curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python get-pip.py --quiet
    del get-pip.py
) else (
    python -m pip install --upgrade pip --quiet
)

echo [4/6] Installing dependencies (this may take a few minutes)...
pip install -r requirements.txt --quiet

echo [5/6] Installing Playwright browser...
playwright install chromium

echo [6/6] Verifying installation...
python -c "import flask; print('[OK] Flask installed')"
python -c "import google.generativeai; print('[OK] Gemini SDK installed')"

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Copy .env.example to .env
echo 2. Add your Gemini API key to .env
echo 3. Run: python run.py
echo.
pause
