# Fix gpuflow.pem permissions and copy to ~/.ssh for OpenSSH on Windows
$ErrorActionPreference = "Stop"

$src = Join-Path $env:USERPROFILE "Downloads\gpuflow.pem"
$dstDir = Join-Path $env:USERPROFILE ".ssh"
$dst = Join-Path $dstDir "gpuflow.pem"

if (-not (Test-Path $src)) {
    throw "Key not found: $src"
}

# Restore access if previous icacls locked the file
icacls $src /grant:r "${env:USERNAME}:(F)" | Out-Null

New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
Copy-Item -Force $src $dst

icacls $dst /inheritance:r | Out-Null
icacls $dst /grant:r "${env:USERNAME}:(R)" | Out-Null

Write-Host "Key ready: $dst"
Write-Host "Testing SSH to gpuflow-1 (ec2-user@13.201.134.27)..."
ssh -i $dst -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 ec2-user@13.201.134.27 "echo SSH OK && whoami"
