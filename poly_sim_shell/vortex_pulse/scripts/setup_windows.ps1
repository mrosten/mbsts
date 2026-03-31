# Vortex Pulse - Windows Setup
# This script creates a virtual environment and installs all dependencies.

Write-Host "--- Vortex Pulse Windows Setup ---" -ForegroundColor Cyan

# 1. Create Virtual Environment if it doesn't exist
if (!(Test-Path "venv")) {
    Write-Host "[1/3] Creating Virtual Environment..." -ForegroundColor Yellow
    python -m venv venv
} else {
    Write-Host "[1/3] Virtual Environment already exists." -ForegroundColor Gray
}

# 2. Upgrade Pip
Write-Host "[2/3] Upgrading Pip..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" -m pip install --upgrade pip

# 3. Install Requirements
Write-Host "[3/3] Installing Project Dependencies (Graphics & AI)..." -ForegroundColor Yellow
# Using legacy-certs workaround for Pillow if needed (common in restricted environments)
$env:PIP_USE_DEPRECATED = "legacy-certs"
& ".\venv\Scripts\python.exe" -m pip install -r requirements.txt "google-generativeai>=0.8.3" --verbose

Write-Host ""
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "You can now run '.\scripts\load_venv.ps1' to activate the environment." -ForegroundColor Cyan
Write-Host "Then run 'python .\scripts\run_pulse.py' to start the app." -ForegroundColor White
