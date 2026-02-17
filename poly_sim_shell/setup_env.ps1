# Define the name of the virtual environment folder
$venvPath = "venv"

# 1. Check if the virtual environment exists
if (Test-Path -Path "$venvPath\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Cyan
    
    # 2. Activate the environment
    # Note: This requires ExecutionPolicy to be set to RemoteSigned or Unrestricted
    . "$venvPath\Scripts\Activate.ps1"
    
    # 3. Check for requirements.txt and install
    if (Test-Path -Path "requirements.txt") {
        Write-Host "Installing requirements..." -ForegroundColor Cyan
        python -m pip install --upgrade pip
        pip install -r requirements.txt --verbose --no-deps --exists-action i
    } else {
        Write-Warning "requirements.txt not found."
    }
} else {
    Write-Error "Virtual environment '$venvPath' not found in the current directory."
}