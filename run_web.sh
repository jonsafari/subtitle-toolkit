#!/bin/bash

# Simple script to run the subtitle toolkit web interface

echo "Starting Subtitle Toolkit Web Interface..."
echo "Make sure you have installed the dependencies with:"
echo "pip install -r requirements-web.txt"
echo ""

# Check if dependencies are installed
if ! python -c "import fastapi" &> /dev/null; then
    echo "Error: FastAPI not found. Please install dependencies with:"
    echo "pip install -r requirements-web.txt"
    exit 1
fi

# Run the web interface
python web/app.py