#!/bin/bash
# Run script for Terminal Browser

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3.7 or higher."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
if [ ! -f "venv/installed" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
    touch venv/installed
fi

# Run the application
echo "Starting Terminal Browser..."
python main.py

# Deactivate virtual environment on exit
deactivate

