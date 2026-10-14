# GPUFlow on AWS (CPU-only workers)

Use this guide when GPU quota is unavailable. Three EC2 workers (`gpuflow-1`, `gpuflow-2`, `gpuflow-3`) run the worker daemon with **real CPU/RAM** and **GPU=0**. The control plane (scheduler + UI + MongoDB) runs on your laptop or a separate EC2 instance.

## Architecture

```
[Laptop or control EC2]                    [Worker EC2 instances]
  docker compose -f docker-compose.control.yml
  UI :80, API :8000, gRPC :50051  ──gRPC──►  gpuflow-1 (t2.large)
                                              gpuflow-2 (t2.xlarge)
                                              gpuflow-3 (t2.2xlarge)
```

Workers register outbound to the scheduler. The scheduler calls workers back on **port 50052** using each worker's **private IP** (`WORKER_HOSTNAME`).

## 1. Security groups

### Control plane SG (laptop or scheduler EC2)

| Direction | Port  | Source        | Purpose              |
|-----------|-------|---------------|----------------------|
| Inbound   | 80    | Your IP       | Dashboard            |
| Inbound   | 8000  | Your IP       | API (optional)       |
| Inbound   | 50051 | Worker SG     | Worker registration  |
| Outbound  | 50052 | Worker SG     | Assign tasks to workers |

### Worker SG (gpuflow-1/2/3)

| Direction | Port  | Source        | Purpose              |
|-----------|-------|---------------|----------------------|
| Inbound   | 22    | Your IP       | SSH                  |
| Inbound   | 50052 | Control SG    | gRPC task assignment |
| Outbound  | 50051 | Control SG    | Register + heartbeat |

All instances should be in the **same VPC/subnet** (or peered) so private IPs work.

## 2. Control plane on your laptop (recommended)

No separate scheduler EC2 needed. Run everything from your machine:

```powershell
powershell -File scripts/start-laptop-control.ps1
```

Or manually:

```powershell
docker compose -f docker-compose.control.yml up -d --build
powershell -File scripts/start-scheduler-tunnels.ps1
```

Open **http://localhost**.

### Why SSH tunnels?

Workers in AWS must call the scheduler on port **50051**. Your laptop is behind a router, so workers cannot reach `your-public-ip:50051` directly. Each tunnel forwards `laptop:50051` → `worker:127.0.0.1:50051`. Workers use `SCHEDULER_ADDRESS=127.0.0.1:50051`.

When the scheduler assigns a job, it calls back to each worker at **`WORKER_HOSTNAME:50052`** (worker public IP). Open **inbound 50052** on worker security groups from your laptop's public IP.

## 2b. Control plane on EC2 (optional)

Only if you cannot keep your laptop running during the demo.

## 3. Install each worker

SSH into each instance (`gpuflow-1`, `gpuflow-2`, `gpuflow-3`):

```bash
# Copy project (from your machine)
scp -r D:/PROJECTS/GPUFlow ubuntu@<public-ip>:/opt/gpuflow

# On the worker
cd /opt/gpuflow
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip -r backend/requirements.txt
python -m grpc_tools.protoc -I protobufs \
  --python_out=protobufs --grpc_python_out=protobufs protobufs/gpuflow.proto
```

Create `/opt/gpuflow/worker.env` from `deploy/aws-worker.env.example`:

```bash
# gpuflow-1 (t2.large — 2 vCPU, 8 GB RAM)
SIMULATE_GPUS=False
SCHEDULER_ADDRESS=10.0.1.10:50051    # control private IP
WORKER_HOSTNAME=10.0.1.21            # THIS instance private IP
WORKER_GRPC_PORT=50052
WORKER_NAME=gpuflow-1
```

Repeat for `gpuflow-2` and `gpuflow-3` with their private IPs and names.

Enable systemd:

```bash
sudo cp deploy/systemd/gpuflow-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gpuflow-worker
sudo journalctl -u gpuflow-worker -f
```

You should see `registered` with real `cpu=` and `gpu=0.0`.

## 4. Instance sizing reference

| Instance     | vCPU | RAM  | Example job limits      |
|--------------|------|------|-------------------------|
| t2.large     | 2    | 8 GB | 1 CPU, 2–4 GB RAM       |
| t2.xlarge    | 4    | 16 GB| 2 CPU, 4–8 GB RAM       |
| t2.2xlarge   | 8    | 32 GB| 4 CPU, 8–16 GB RAM      |

Leave headroom for the OS (~1 CPU, ~1 GB RAM).

## 5. Submit workloads

In the UI (**Submit Workload**):

- **GPU = 0**, **VRAM = 0**
- CPU/RAM within the target instance capacity
- Jobs auto-start when a worker is free (Priority + FCFS)

If jobs stay queued, check **Cluster Nodes** — you need 3 ONLINE workers. Common fixes:

- Wrong `WORKER_HOSTNAME` (must be private IP reachable from control)
- Security group missing port 50052 from control → worker
- Job still requests GPU > 0

## 6. Verify

```bash
curl http://localhost/nodes
curl http://localhost/cluster
```

`cluster` should show `cpu_only_mode: true`, `gpu_total: 0`, and `online_nodes: 3`.

## 7. Local dev vs AWS

| Setting            | Local Docker (`docker-compose.yml`) | AWS workers              |
|--------------------|-------------------------------------|--------------------------|
| `SIMULATE_GPUS`    | `True`                              | `False`                  |
| `CPU_ONLY_MODE`    | `False`                             | `True` (control plane)   |
| Workers            | 3 containers                        | 3 EC2 instances          |
| Default submit GPU | 1                                   | 0 (UI adapts automatically) |
