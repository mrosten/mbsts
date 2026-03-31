#!/bin/bash
# Vortex Pulse - Linux (Google VM) Setup
# This script creates a virtual environment and installs all dependencies.

echo "--- Vortex Pulse Linux Setup ---"

# 1. Update and install system dependencies
echo "[1/4] Installing system dependencies (sudo required)..."
sudo apt update
sudo apt install -y python3-venv python3-pip libjpeg-dev zlib1g-dev build-essential

# 2. Create Virtual Environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "[2/4] Creating Virtual Environment..."
    python3 -m venv venv
else
    echo "[2/4] Virtual Environment already exists."
fi

# 3. Upgrade Pip
echo "[3/4] Upgrading Pip..."
source venv/bin/activate
pip install --upgrade pip

# 4. Install Requirements
echo "[4/4] Installing Project Dependencies (Graphics, AI & Trading)..."
pip install -r requirements.txt "eth-account>=0.13.0" "py-clob-client>=2.0.0"

echo ""
echo "Setup Complete!"
echo "To activate the environment: source ./scripts/load_venv.sh"
echo "To run the app: python ./scripts/run_pulse.py"
