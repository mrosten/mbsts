#!/bin/bash
# Activate Linux (Google VM / Termux) Virtual Environment
if [ -f "./venv/bin/activate" ]; then
    source ./venv/bin/activate
    echo "Venv Activated (Linux/Termux)"
else
    echo "Venv not found! Run ./scripts/setup_linux.sh or ./scripts/setup_termux.sh first."
fi
