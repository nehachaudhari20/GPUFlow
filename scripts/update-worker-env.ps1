# Update worker.env for laptop-scheduler + SSH tunnel assign ports
param(
    [string]$KeyPath = "$env:USERPROFILE\.ssh\gpuflow.pem",
    [string]$SshUser = "ec2-user",
    [array]$Workers = @(
        @{ Ip = "13.201.134.27"; Name = "gpuflow-1"; AdvertisePort = 15052 },
        @{ Ip = "3.111.41.226";  Name = "gpuflow-2"; AdvertisePort = 15053 }
    )
)

foreach ($w in $Workers) {
    $envContent = @"
SIMULATE_GPUS=False
SCHEDULER_ADDRESS=127.0.0.1:50551
WORKER_HOSTNAME=host.docker.internal
WORKER_GRPC_PORT=50052
WORKER_ADVERTISE_GRPC_PORT=$($w.AdvertisePort)
WORKER_NAME=$($w.Name)
"@
    $f = Join-Path $env:TEMP "worker-$($w.Name).env"
    [IO.File]::WriteAllText($f, $envContent)
    scp -i $KeyPath -q $f "${SshUser}@$($w.Ip):/opt/gpuflow/worker.env"
    scp -i $KeyPath -q "D:\PROJECTS\GPUFlow\backend\app\worker\node.py" "${SshUser}@$($w.Ip):/opt/gpuflow/backend/app/worker/node.py"
    ssh -i $KeyPath "${SshUser}@$($w.Ip)" "sudo systemctl restart gpuflow-worker"
    Write-Host "Updated $($w.Name): listen :50052, advertise host.docker.internal:$($w.AdvertisePort)"
}
