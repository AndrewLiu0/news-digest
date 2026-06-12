#!/bin/bash

# Change directory to the location of the script
cd "$(dirname "$0")"

echo "--- CCCW 2026: US-China Strategic Briefing Setup ---"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null
then
    echo "Error: python3 could not be found."
    echo "Please install Python from https://www.python.org/downloads/macos/"
    read -p "Press enter to exit..."
    exit
fi

# Check for Virtual Environment
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Creating it now..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment."
        read -p "Press enter to exit..."
        exit 1
    fi
    
    echo "Activating environment and installing requirements..."
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "Activating existing environment..."
    source .venv/bin/activate
fi

# Run the script
echo ""
echo "Starting Workflow..."
python3 run_workflow.py

echo ""
echo "--- Process Finished ---"
read -p "Press enter to close this window..."
