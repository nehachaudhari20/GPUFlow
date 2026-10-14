# SSH tunnels for laptop scheduler <-> EC2 workers (no AWS SG changes needed)
#  - Reverse -R: worker can reach scheduler at 127.0.0.1:50051
#  - Local   -L: scheduler (in Docker) reaches worker via host.docker.internal:1505x
$Key = "$env:USERPROFILE\.ssh\gpuflow.pem"

# public_ip | local_port_for_assign_task
$Workers = @(
    @{ Ip = "13.201.134.27"; LocalPort = 15052; Name = "gpuflow-1" },
    @{ Ip = "3.111.41.226";  LocalPort = 15053; Name = "gpuflow-2" }
)

Write-Host "Starting GPUFlow SSH tunnels..."
foreach ($w in $Workers) {
    $args = @(
        "-i", $Key, "-N", "-o", "ServerAliveInterval=30", "-o", "ExitOnForwardFailure=yes",
        "-R", "50551:127.0.0.1:50051",
        "-L", "0.0.0.0:$($w.LocalPort):127.0.0.1:50052",
        "ec2-user@$($w.Ip)"
    )
    Start-Process -WindowStyle Hidden -FilePath "ssh" -ArgumentList $args
    Write-Host "  $($w.Name): register via 127.0.0.1:50551 | assign via host.docker.internal:$($w.LocalPort)"
}
Write-Host "Tunnels running in background. Keep laptop on while demoing."
