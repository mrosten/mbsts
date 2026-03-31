#!/bin/bash
# Quick Fix for Missing Dependencies
echo "🔧 Fixing missing dependencies..."

# Copy correct requirements from parent directory
cp ../requirements.txt ./requirements.txt
echo "✅ Updated requirements.txt"

# Install missing dependencies directly
pip install eth-account py-clob-client
echo "✅ Installed eth-account and py-clob-client"

echo "🚀 Try running: python3 ./scripts/run_pulse.py"
