#!/bin/bash
# Vortex Pulse - Linux Dependency Installer
# This script installs all necessary libraries for graphs and saving to work.
# Tailored for Python 3.14 + Linux

echo -e "\e[36m--- Vortex Pulse Dependency Setup (Linux) ---\e[0m"

# 1. Ensure we are in a virtual environment or find the local one
VENV_PATH="./venv/bin/python"
if [ ! -f "$VENV_PATH" ]; then
    echo -e "\e[33m[!] Virtual environment not found at ./venv/. Attempting to use 'python3'...\e[0m"
    VENV_PATH="python3"
fi

# 2. Upgrade Pip
echo -e "\e[33m[1/2] Upgrading Pip...\e[0m"
$VENV_PATH -m pip install --upgrade pip

# 3. Install Project Dependencies (Graphics & AI)
echo -e "\e[33m[2/2] Installing Pillow & Google AI...\e[0m"
# Note: On some Linux distros, you might need libjpeg-dev or zlib1g-dev if wheels aren't found.
$VENV_PATH -m pip install "Pillow>=12.1.1" "google-generativeai>=0.8.3" --verbose

echo ""
echo -e "\e[32mSetup Complete! If you saw 'Successfully installed', you are ready to go.\e[0m"
echo -e "\e[36mPlease restart the application to apply changes.\e[0m"
