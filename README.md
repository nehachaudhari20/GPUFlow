# GPUFlow - Distributed GPU-Aware Workload Scheduling Platform

GPUFlow is an academic distributed systems prototype exploring resource management, remote invocation, component orchestration, and stream-oriented monitoring across a computing grid. Developed for Distributed Systems **FA1** (scheduling) and **FA2** (clocks, coordination, recovery, storage, UI). FA1 maps workloads to workers via score-based scheduling; FA2 adds `/fa2/*` APIs and the **FA2 Distributed** sidebar in the dashboard.

## Architecture

At a high-level, GPUFlow acts as a centralized orchestrator maintaining continuous connections to independently running worker node daemons.

**User → Frontend Dashboard** (React SPA)  
**Frontend Dashboard → FastAPI** (REST via HTTP/1.1 and live events via WebSockets)  
**FastAPI → Custom Scheduling Engine** (Score-based Allocation Policy)  
**Scheduling Engine → Worker Nodes** (RPC via gRPC / protobufs)

## Core Components

- **Frontend:** Operational views for cluster state, telemetry, queue status, scheduling decisions, and event timeline.
- **Backend API & Workload Queue:** Accepts HTTP workload definitions into a priority queue (MongoDB-backed when configured).
- **Node Filter & Scorer Engine:** Prunes offline/busy nodes and scores eligible candidates using CPU, RAM, GPU, health, and load balance.
- **Worker Daemon (Node):** Autonomous Python processes probing real or simulated host resources, registering with the scheduler, and executing assigned tasks.
- **gRPC Communication Layer:** Defined via `.proto` for `RegisterNode`, `SendHeartbeat`, `AssignTask`, and status reporting.

## Getting Started

### Local Docker Compose (Recommended)

Requires Docker and Docker Compose. Local workers simulate heterogeneous GPUs inside containers.

```bash
docker compose up --build
```

Access the dashboard at **http://localhost** (port 80).

### AWS CPU-only workers

For cloud deployment without GPU quota, run the control plane locally or on EC2 and install workers on three EC2 instances. See **[deploy/AWS.md](deploy/AWS.md)** for security groups, env files, and systemd setup.

```bash
docker compose -f docker-compose.control.yml up --build
```

Set `CPU_ONLY_MODE=True` on the control plane and `SIMULATE_GPUS=False` on each worker. Submit jobs with **GPU=0**.

### Local Python Environment

1. Start the backend (port 8000 + gRPC 50051):
   ```bash
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
   ```
2. Start worker nodes in separate terminals:
   ```bash
   export SIMULATED_GPU_COUNT=4.0
   python backend/app/worker/node.py
   ```
3. Start frontend:
   ```bash
   cd frontend && npm install && npm run dev
   ```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SIMULATE_GPUS` | `True` | Local demo: fake GPU counts on workers |
| `CPU_ONLY_MODE` | `False` | Rebalance scheduler for 0-GPU clusters |
| `WORKER_GRPC_PORT` | `0` | Fixed port for AWS (e.g. `50052`); `0` = dynamic |
| `WORKER_HOSTNAME` | auto | Private IP workers advertise to scheduler |
| `SCHEDULER_ADDRESS` | `localhost:50051` | Where workers register |

## Academic Focus

- **Middleware Integration:** gRPC mapping procedure calls to distributed worker logic.
- **Hardware probing:** Real CPU/RAM via `psutil`; optional NVIDIA detection; simulation for local dev.
- **Message-Oriented Tracing:** Event stream from `JOB_SUBMITTED` to `TASK_COMPLETED`.
