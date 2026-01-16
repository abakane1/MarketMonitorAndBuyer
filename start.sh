#!/bin/bash

# Navigate to the script's directory ensures it runs from the correct place
cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Setting up..."
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi

# Activate venv and run
echo "Starting A-Share Monitor..."
source venv/bin/activate
streamlit run main.py
