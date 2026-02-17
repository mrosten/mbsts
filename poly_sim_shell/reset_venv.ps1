$venvPath = "venv"

# 1. Deactivate if currently active
if ($env:VIRTUAL_ENV) {
    Write-Host "Deactivating current environment..." -ForegroundColor Yellow
    deactivate
}

# 2. Force remove the existing venv folder
if (Test-Path -Path $venvPath) {
    Write-Host "Removing existing venv at $venvPath..." -ForegroundColor Red
    Remove-Item -Path $venvPath -Recurse -Force -ErrorAction SilentlyContinue
}

# 3. Create a fresh venv
Write-Host "Creating fresh virtual environment..." -ForegroundColor Cyan
python -m venv $venvPath

# 4. Activate the new venv
if (Test-Path -Path "$venvPath\Scripts\Activate.ps1") {
    . "$venvPath\Scripts\Activate.ps1"
    Write-Host "Fresh venv is active." -ForegroundColor Green
} else {
    Write-Error "Failed to create the new virtual environment."
}