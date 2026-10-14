# SSH tunnel: expose laptop scheduler (localhost:50051) on gpuflow-1 VPC IP
# Run this on your laptop while docker-compose.control.yml is up.
# Workers use SCHEDULER_ADDRESS=172.31.0.164:50051

$Key = "$env:USERPROFILE\.ssh\gpuflow.pem"
$RelayHost = "13.201.134.27"
$RelayUser = "ec2-user"

Write-Host "Starting scheduler tunnel via gpuflow-1..."
Write-Host "Workers should use SCHEDULER_ADDRESS=172.31.0.164:50051"
Write-Host "Press Ctrl+C to stop."

ssh -i $Key -N -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes `
  -R "0.0.0.0:50051:127.0.0.1:50051" "${RelayUser}@${RelayHost}"
