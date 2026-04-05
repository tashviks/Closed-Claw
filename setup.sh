#!/bin/bash
# ClosedClaw Full Setup Script
set -e

echo "🦀 ClosedClaw Setup"
echo "=================="

# Check Node.js
if ! command -v node &> /dev/null; then
  echo "❌ Node.js not found. Install from https://nodejs.org (v18+)"
  exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
  echo "❌ Python 3 not found. Install from https://python.org (3.10+)"
  exit 1
fi

echo "✅ Node.js $(node --version)"
echo "✅ Python $(python3 --version)"

# Install frontend deps
echo ""
echo "Installing frontend dependencies..."
npm install

# Setup backend
echo ""
echo "Setting up Python backend..."
cd backend
bash setup.sh
cd ..

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To run in development mode:"
echo "  1. cd backend && source venv/bin/activate && uvicorn main:app --host 127.0.0.1 --port 8765 --reload"
echo "  2. npm run dev:react"
echo "  3. npm run dev:electron"
echo ""
echo "Or use: npm run dev (starts all together)"
