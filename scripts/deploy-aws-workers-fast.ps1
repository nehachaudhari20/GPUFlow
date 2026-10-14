# Fast worker-only deploy (no frontend, no full backend, no dnf)
param(
    [string]$KeyPath = "$env:USERPROFILE\.ssh\gpuflow.pem",
    [string]$SchedulerIp = "",
    [string]$SshUser = "ec2-user",
    [string[]]$Workers = @(
        "13.201.134.27|gpuflow-1",
        "3.111.41.226|gpuflow-2"
    )
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RemoteDir = "/opt/gpuflow"
$StagingTar = Join-Path $env:TEMP "gpuflow-worker-slim.tar.gz"
$StagingDir = Join-Path $env:TEMP "gpuflow-worker-staging"

if (-not $SchedulerIp) {
    try { $SchedulerIp = (Invoke-RestMethod -Uri "https://api.ipify.org" -TimeoutSec 10) }
    catch { $SchedulerIp = "117.198.136.17" }
}

Write-Host "==> Slim worker deploy | scheduler ${SchedulerIp}:50051" -ForegroundColor Cyan

if (-not (Test-Path $KeyPath)) {
    throw "Key not found: $KeyPath"
}

# Build minimal staging folder
if (Test-Path $StagingDir) { Remove-Item $StagingDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path "$StagingDir/backend/app/worker" | Out-Null
New-Item -ItemType Directory -Force -Path "$StagingDir/backend/app/core" | Out-Null
New-Item -ItemType Directory -Force -Path "$StagingDir/deploy/systemd" | Out-Null
New-Item -ItemType Directory -Force -Path "$StagingDir/scripts" | Out-Null

Copy-Item "$ProjectRoot/backend/app/worker/*" "$StagingDir/backend/app/worker/"
Copy-Item "$ProjectRoot/backend/app/config.py" "$StagingDir/backend/app/"
Copy-Item "$ProjectRoot/backend/app/core/logging.py" "$StagingDir/backend/app/core/"
Copy-Item "$ProjectRoot/backend/requirements-worker.txt" "$StagingDir/backend/"
New-Item -ItemType Directory -Force -Path "$StagingDir/protobufs" | Out-Null
Copy-Item "$ProjectRoot/protobufs/*" "$StagingDir/protobufs/"
New-Item -ItemType Directory -Force -Path "$StagingDir/deploy/wheels" | Out-Null
Copy-Item "$ProjectRoot/deploy/systemd/gpuflow-worker.service" "$StagingDir/deploy/systemd/"
if (Test-Path "$ProjectRoot/deploy/wheels") {
    Copy-Item "$ProjectRoot/deploy/wheels/*.whl" "$StagingDir/deploy/wheels/" -ErrorAction SilentlyContinue
}
Copy-Item "$ProjectRoot/scripts/remote-install-worker-fast.sh" "$StagingDir/scripts/"

if (Test-Path $StagingTar) { Remove-Item $StagingTar -Force }
Push-Location $StagingDir
tar -czf $StagingTar .
Pop-Location
$sizeMb = [math]::Round((Get-Item $StagingTar).Length / 1MB, 2)
Write-Host "    Package size: ${sizeMb} MB" -ForegroundColor Gray

foreach ($entry in $Workers) {
    $parts = $entry -split '\|'
    $ip = $parts[0].Trim()
    $name = $parts[1].Trim()

    Write-Host "`n==> $name ($ip)" -ForegroundColor Yellow

    ssh -i $KeyPath -o ConnectTimeout=20 "${SshUser}@${ip}" "sudo mkdir -p $RemoteDir && sudo chown ${SshUser}:${SshUser} $RemoteDir"
    scp -i $KeyPath -q $StagingTar "${SshUser}@${ip}:/tmp/gpuflow-worker-slim.tar.gz"

    $workerEnv = "SIMULATE_GPUS=False`nSCHEDULER_ADDRESS=${SchedulerIp}:50051`nWORKER_HOSTNAME=${ip}`nWORKER_GRPC_PORT=50052`nWORKER_NAME=${name}"
    $localEnv = Join-Path $env:TEMP "worker-$name.env"
    [System.IO.File]::WriteAllText($localEnv, $workerEnv)
    scp -i $KeyPath -q $localEnv "${SshUser}@${ip}:${RemoteDir}/worker.env"

    ssh -i $KeyPath "${SshUser}@${ip}" "set -e; cd $RemoteDir; tar -xzf /tmp/gpuflow-worker-slim.tar.gz; chmod +x scripts/remote-install-worker-fast.sh; bash scripts/remote-install-worker-fast.sh"

    Write-Host "    OK" -ForegroundColor Green
}

Remove-Item $StagingDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $StagingTar -Force -ErrorAction SilentlyContinue
Write-Host "`n==> Done. Check http://localhost/nodes" -ForegroundColor Cyan
