#!/bin/bash
# ClosedClaw Backend Setup Script
set -e

echo "Setting up ClosedClaw backend..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install playwright browsers (for future browser automation)
python3 -m playwright install chromium --with-deps 2>/dev/null || echo "Playwright install skipped (optional)"

echo ""
echo "✅ Backend setup complete!"
echo "Run: source venv/bin/activate && uvicorn main:app --host 127.0.0.1 --port 8765"
