# Sync-Bless.ps1
# Automates uploading of Darwin logs and Web logs to the 'bless' SSH host.

$SSH_HOST = "bless"
$LOCAL_ROOT = "C:\MyStuff\coding\turbindo-master\poly_sim_shell\vortex_pulse"
$REMOTE_ROOT = "/home/user/myfavoritemalshin.space" # Adjust if necessary

# Ensure we use the full path to scp.exe if not in PATH
$SCP_EXE = "C:\Windows\System32\OpenSSH\scp.exe"
if (-not (Test-Path $SCP_EXE)) {
    $SCP_EXE = "scp" # Fallback to PATH
}

function Sync-File {
    param($LocalPath, $RemoteSubDir)
    
    $RemotePath = "$SSH_HOST`:$REMOTE_ROOT/$RemoteSubDir"
    Write-Host "Syncing $LocalPath to $RemotePath..." -ForegroundColor Cyan
    
    & $SCP_EXE -r $LocalPath $RemotePath
}

# Example Usage:
# Sync-File -LocalPath "$LOCAL_ROOT/verification.html" -RemoteSubDir "."
# Sync-File -LocalPath "$LOCAL_ROOT/darwin/observations.md" -RemoteSubDir "darwin/"

Write-Host "SSH Sync Utility for 'bless' initialized." -ForegroundColor Green
Write-Host "Usage: Sync-File -LocalPath 'path/to/file' -RemoteSubDir 'remote/dir'"
