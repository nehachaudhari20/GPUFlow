# Laptop control plane + EC2 workers (recommended for demos)
#
# Architecture:
#   Laptop: UI (:80) + scheduler gRPC (:50051) via docker-compose.control.yml
#   EC2:    worker daemon only (:50052)
#
# Workers cannot reach your home IP directly (router/firewall), so SSH reverse
# tunnels expose localhost:50051 on each worker as 127.0.0.1:50051.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "=== GPUFlow: laptop scheduler + EC2 workers ===" -ForegroundColor Cyan
Write-Host ""

# 1. Control plane
Write-Host "[1/2] Starting control plane (UI + scheduler + Mongo)..." -ForegroundColor Yellow
Push-Location $Root
docker compose -f docker-compose.control.yml up -d --build
Pop-Location
Write-Host "      Dashboard: http://localhost" -ForegroundColor Green

# 2. SSH tunnels so workers can register with laptop scheduler
Write-Host "[2/2] Starting SSH scheduler tunnels to EC2 workers..." -ForegroundColor Yellow
& "$Root/scripts/start-scheduler-tunnels.ps1"

Write-Host ""
Write-Host "Ready. Workers should show ONLINE at http://localhost (Cluster Nodes)." -ForegroundColor Green
Write-Host ""
Write-Host "Before submitting jobs, confirm AWS security groups:" -ForegroundColor Gray
Write-Host "  Option A (easiest): use SSH tunnels only - run this script each session"
Write-Host "  Option B: open INBOUND tcp 50052 on each worker from your laptop public IP"
Write-Host ""
Write-Host "Submit workloads with GPU=0. Example: 1 CPU, 2 GB RAM, 30s duration."
Write-Host ""
Write-Host "To add gpuflow-3: edit scripts/start-scheduler-tunnels.ps1 and deploy-aws-workers-fast.ps1"
