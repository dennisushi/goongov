#!/bin/bash
# Run frontend development server

cd "$(dirname "$0")/frontend"

echo "Starting frontend development server on http://localhost:3000"
echo "Backend API should be running on http://localhost:5000"
echo "Press Ctrl+C to stop"
echo ""

# Check if Python 3 is available
if command -v python3 &> /dev/null; then
    # Use Python's built-in HTTP server
    python3 -m http.server 3000
elif command -v python &> /dev/null; then
    # Fallback to python
    python -m http.server 3000
else
    echo "Error: Python not found. Please install Python to run the frontend server."
    exit 1
fi

