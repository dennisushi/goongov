#!/bin/bash
# Run Flask backend server

cd "$(dirname "$0")"

echo "Starting Flask backend server on http://localhost:5000"
echo "Press Ctrl+C to stop"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run Flask app
python -m flask --app backend.app run --port 5000 --debug

