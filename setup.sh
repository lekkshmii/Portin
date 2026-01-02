#!/bin/bash
# Portin Quick Setup for Mac/Linux
# Run this script to set up the project automatically: bash setup.sh

echo "========================================"
echo "Portin Setup Script"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed!"
    echo "Please install Python 3.9+ from https://python.org/downloads"
    exit 1
fi

echo "[1/5] Creating virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to create virtual environment"
    exit 1
fi

echo "[2/5] Activating virtual environment..."
source venv/bin/activate

echo "[3/5] Upgrading pip..."
python -m pip install --upgrade pip --quiet

echo "[4/5] Installing dependencies (this may take a few minutes)..."
pip install -r requirements.txt --quiet

echo "[5/5] Installing Playwright browser..."
playwright install chromium

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env"
echo "2. Add your Gemini API key to .env"
echo "3. Run: python run.py"
echo ""
