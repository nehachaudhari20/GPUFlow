# Deploy CPUFlow workers to AWS EC2 (Amazon Linux / ec2-user)
param(
    [string]$KeyPath = "$env:USERPROFILE\.ssh\gpuflow.pem",
    [string]$SchedulerIp = "117.198.136.17",
    [string]$SshUser = "ec2-user",
    [string[]]$Workers = @(
        "13.201.134.27|gpuflow-1",
        "3.111.41.226|gpuflow-2"
    )
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RemoteDir = "/opt/gpuflow"
$StagingTar = Join-Path $env:TEMP "gpuflow-deploy.tar.gz"

Write-Host "==> CPUFlow AWS worker deploy" -ForegroundColor Cyan
Write-Host "    Project: $ProjectRoot"
Write-Host "    Key:     $KeyPath"
Write-Host "    Scheduler: ${SchedulerIp}:50051"

if (-not (Test-Path $KeyPath)) {
    throw "Key not found: $KeyPath. Run scripts/setup-ssh-key.ps1 first."
}

# Pack project (exclude heavy dirs)
Write-Host "==> Creating deployment archive..."
if (Test-Path $StagingTar) { Remove-Item $StagingTar -Force }
Push-Location $ProjectRoot
tar --exclude=.git --exclude=node_modules --exclude=frontend/node_modules `
    --exclude=__pycache__ --exclude=.venv --exclude="*.pyc" `
    -czf $StagingTar .
Pop-Location

foreach ($entry in $Workers) {
    if ($entry -match '^\s*#') { continue }
    $parts = $entry -split '\|'
    if ($parts.Count -lt 2) { continue }
    $ip = $parts[0].Trim()
    $name = $parts[1].Trim()
    if (-not $ip) { continue }

    Write-Host "`n==> Deploying $name ($ip)..." -ForegroundColor Yellow

    ssh -i $KeyPath -o StrictHostKeyChecking=accept-new "${SshUser}@${ip}" "sudo mkdir -p $RemoteDir && sudo chown ${SshUser}:${SshUser} $RemoteDir"

    scp -i $KeyPath $StagingTar "${SshUser}@${ip}:/tmp/gpuflow-deploy.tar.gz"

    $workerEnv = @"
SIMULATE_GPUS=False
SCHEDULER_ADDRESS=${SchedulerIp}:50051
WORKER_HOSTNAME=${ip}
WORKER_GRPC_PORT=50052
WORKER_NAME=${name}
"@

    $localEnv = Join-Path $env:TEMP "worker-$name.env"
    Set-Content -Path $localEnv -Value $workerEnv -NoNewline
    scp -i $KeyPath $localEnv "${SshUser}@${ip}:${RemoteDir}/worker.env"

    $remoteCmd = "set -e; cd $RemoteDir; tar -xzf /tmp/gpuflow-deploy.tar.gz; chmod +x scripts/remote-install-worker.sh; bash scripts/remote-install-worker.sh"

    ssh -i $KeyPath "${SshUser}@${ip}" $remoteCmd
    Write-Host "    Done: $name" -ForegroundColor Green
}

Remove-Item $StagingTar -Force -ErrorAction SilentlyContinue
Write-Host "`n==> All workers deployed. Check http://localhost/nodes" -ForegroundColor Cyan
Write-Host "    Ensure EC2 security groups allow:"
Write-Host "      - Workers OUT to ${SchedulerIp}:50051"
Write-Host "      - Workers IN on 50052 from ${SchedulerIp}"
Write-Host "      - Windows firewall allows IN on 50051"
