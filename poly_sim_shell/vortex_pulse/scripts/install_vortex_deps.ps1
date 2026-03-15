# Vortex Pulse - Dependency Installer
# This script installs all necessary libraries for graphs and saving to work.
# Especially tailored for Python 3.14 + Windows + pip 26.x

Write-Host "--- Vortex Pulse Dependency Setup ---" -ForegroundColor Cyan

# 1. Upgrade Pip
Write-Host "[1/2] Upgrading Pip..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" -m pip install --upgrade pip

# 2. Install Pillow (with truststore workaround)
Write-Host "[2/2] Installing Pillow (Graphics Engine)..." -ForegroundColor Yellow
$env:PIP_USE_DEPRECATED = "legacy-certs"
& ".\venv\Scripts\python.exe" -m pip install "Pillow>=12.1.1" --verbose

Write-Host ""
Write-Host "Setup Complete! If you saw 'Successfully installed', you are ready to go." -ForegroundColor Green
Write-Host "Please restart the application to apply changes." -ForegroundColor Cyan
