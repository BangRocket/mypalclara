#!/bin/bash
# Run MyPalClara Web

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install deps
source venv/bin/activate
pip install -q -r requirements.txt

# Run server
echo ""
echo "Starting Clara..."
echo "   Open http://localhost:8000 in your browser"
echo ""
python app.py
