# PowerShell Setup Script for MBSTS V4
Write-Host "=== Setting up MBSTS V4 Environment ===" -ForegroundColor Cyan

# 1. Check for Python
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python is not installed or not in PATH." -ForegroundColor Red
    exit
}

# 2. Install requirements
Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[SUCCESS] All dependencies installed successfully." -ForegroundColor Green
} else {
    Write-Host "`n[ERROR] Installation failed. Please check the output above." -ForegroundColor Red
}

Write-Host "`nPress any key to exit..."
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null