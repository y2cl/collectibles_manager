#!/bin/bash

# Collectibles Manager - Start Script
# This script installs dependencies and starts both frontend and backend

set -e
# Kill any processes on the ports we need
echo "Cleaning up ports 8002 and 5175..."
lsof -ti:8002 | xargs kill -9 2>/dev/null || true
lsof -ti:5175 | xargs kill -9 2>/dev/null || true
sleep 1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  Collectibles Manager - Setup & Run"
echo "========================================"
echo ""

# Check if nvm is available
if [ -z "$NVM_DIR" ]; then
    export NVM_DIR="$HOME/.nvm"
fi

if [ -s "$NVM_DIR/nvm.sh" ]; then
    echo "[1/5] Loading nvm..."
    . "$NVM_DIR/nvm.sh"
else
    echo "WARNING: nvm not found. Please install nvm: https://github.com/nvm-sh/nvm"
    echo "Continuing without nvm..."
fi

# Set correct Node version
if command -v nvm &> /dev/null; then
    echo "[2/5] Setting Node version..."
    nvm install
    nvm use
fi

# Setup Python virtual environment and backend dependencies
if [ ! -d ".venv-backend" ]; then
    echo "[3/5] Creating Python virtual environment..."
    python3 -m venv .venv-backend
    echo "Installing backend dependencies..."
    .venv-backend/bin/pip install -r backend/requirements.txt
else
    echo "[3/5] Python virtual environment already exists."
    # Check if we need to install/update dependencies
    if [ ! -f ".venv-backend/bin/uvicorn" ]; then
        echo "Installing backend dependencies..."
        .venv-backend/bin/pip install -r backend/requirements.txt
    fi
fi

# Install root npm dependencies (concurrently)
if [ ! -d "node_modules" ]; then
    echo "[4/5] Installing root npm dependencies..."
    npm install
else
    echo "[4/5] Root npm dependencies already installed."
fi

# Install frontend dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo "[5/5] Installing frontend npm dependencies..."
    cd frontend && npm install && cd ..
else
    echo "[5/5] Frontend npm dependencies already installed."
fi

echo ""
echo "========================================"
echo "  Starting Collectibles Manager..."
echo "========================================"
echo ""
echo "Backend will run on:  http://0.0.0.0:8002  (accessible from network)"
echo "Frontend will run on: http://localhost:5175 (Network: http://$(hostname):5175)"
echo ""
echo "Press Ctrl+C to stop both servers."
echo ""

# Run both backend and frontend
npm run dev
