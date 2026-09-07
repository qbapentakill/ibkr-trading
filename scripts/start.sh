#!/bin/bash
# Start all services on Linux / macOS
# Usage: ./scripts/start.sh

echo "🚀 IBKR Trading System Startup Script"
echo "===================================="
echo ""

# Check Python
if ! command -v python3.11 &> /dev/null; then
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3.11+ not found"
        exit 1
    fi
    PYTHON=python3
else
    PYTHON=python3.11
fi

PYTHON_VERSION=$($PYTHON --version)
echo "✅ Python: $PYTHON_VERSION"

# Check venv
if [ ! -d ".venv" ]; then
    echo ""
    echo "📦 Creating venv..."
    $PYTHON -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

echo ""
echo "📝 Checking .env..."
if [ ! -f ".env" ]; then
    echo "❌ .env not found. Copying .env.example..."
    cp .env.example .env
    echo "⚠️  Edit .env and set IBKR parameters!"
    exit 1
fi

echo "✅ .env found"
echo ""
echo "🎯 Starting system..."
echo ""
echo "Components:" 
echo "  1. Backend API (port 8000)"
echo "  2. Streamlit Panel (port 8501)"
echo "  3. Logur logger (logs/)"
echo ""
echo "⏳ Launching..."
echo ""

# Terminal 1: Backend
$PYTHON main.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Terminal 2: Frontend
streamlit run panel/frontend/dashboard.py &
FRONTEND_PID=$!

echo ""
echo "✅ System started!"
echo ""
echo "📊 Addresses:"
echo "  API:    http://localhost:8000 (docs: /docs)"
echo "  Panel:  http://localhost:8501"
echo ""
echo "📋 Logs: tail -f logs/system.log"
echo ""
echo "💡 Tip: Open .env and check IBKR configuration"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Keep running
wait $BACKEND_PID $FRONTEND_PID
