# install_requirements.ps1

Write-Host "Checking for active virtual environment..." -ForegroundColor Cyan

# Check if we are inside a virtual environment by looking for the VIRTUAL_ENV variable
if (-not $env:VIRTUAL_ENV) {
    Write-Host "WARNING: No virtual environment detected!" -ForegroundColor Yellow
    Write-Host "It is recommended to activate your venv first: .\.venv\Scripts\Activate" -ForegroundColor Yellow
    
    $confirmation = Read-Host "Do you want to proceed installing to the global Python scope? (y/n)"
    if ($confirmation -ne 'y') {
        exit
    }
}

Write-Host "Upgrading pip..." -ForegroundColor Green
pip install --upgrade pip

Write-Host "Installing dependencies..." -ForegroundColor Green
# These are the external libraries used in mbsts_sim_auto.py
pip install requests python-dotenv textual web3

Write-Host "--------------------------------" -ForegroundColor Cyan
Write-Host "Installation Complete!" -ForegroundColor Cyan
Write-Host "You can now run the bot using: python mbsts_sim_auto.py" -ForegroundColor Cyan