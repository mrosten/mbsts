# Activate Windows Virtual Environment
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    . .\venv\Scripts\Activate.ps1
    Write-Host "Venv Activated (Windows)" -ForegroundColor Green
} else {
    Write-Host "Venv not found! Run .\scripts\setup_windows.ps1 first." -ForegroundColor Red
}
