#!/data/data/com.termux/files/usr/bin/bash
# Vortex Pulse - Termux (Android) Setup
# This script creates a virtual environment and installs all dependencies.

echo "--- Vortex Pulse Termux Setup ---"

# 1. Update and install system dependencies
echo "[1/4] Installing system dependencies (pkg update)..."
pkg update
pkg install -y python python-pip libjpeg-turbo libpng binutils 

# 2. Create Virtual Environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "[2/4] Creating Virtual Environment..."
    python -m venv venv
else
    echo "[2/4] Virtual Environment already exists."
fi

# 3. Upgrade Pip
echo "[3/4] Upgrading Pip..."
source venv/bin/activate
pip install --upgrade pip

# 4. Install Requirements
echo "[4/4] Installing Project Dependencies (Graphics & AI)..."
# Pillow might need LDFLAGS/CFLAGS on some Termux versions, but usually pkg install libjpeg-turbo is enough
pip install -r requirements.txt "google-generativeai>=0.8.3"

echo ""
echo "Setup Complete!"
echo "To activate: source ./scripts/load_venv.sh"
echo "To run: python ./scripts/run_pulse.py"
