$venvPath = "venv"

# 1. Create the venv if it doesn't exist
if (-not (Test-Path -Path $venvPath)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv $venvPath
}

# 2. Activate for the current session
if (Test-Path -Path "$venvPath\Scripts\Activate.ps1") {
    . "$venvPath\Scripts\Activate.ps1"
    Write-Host "Venv '$venvPath' is now active." -ForegroundColor Green
} else {
    Write-Error "Activation script not found. Check if Python is installed correctly."
}