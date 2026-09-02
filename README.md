# GPUFlow - Distributed GPU-Aware Workload Scheduling Platform

GPUFlow is an academic distributed systems prototype exploring resource management, remote invocation, component orchestration, and stream-oriented monitoring across a simulated computing grid. Developed for Distributed Systems FA1, it implements a highly decoupled architecture mapping user workloads to appropriate worker nodes based on real-time multi-criteria telemetry matching.

## Architecture

At a high-level, GPUFlow acts as a centralized orchestrator maintaining continuous connections to independently running worker node daemons.

**User → Frontend Dashboard** (React SPA)
**Frontend Dashboard → FastAPI** (REST via HTTP/1.1 and live events via WebSockets)
**FastAPI → Custom Scheduling Engine** (Score-based Allocation Policy)
**Scheduling Engine → Worker Nodes** (RPC via gRPC / protobufs)

## Core Components

- **Frontend:** Provides 9 distinct operational views exposing system state, telemetry, queue statuses, scheduling decisions, and timeline tracing.
- **Backend API & Workload Queue:** Accepts HTTP definitions to inject AI workload definitions directly into an in-memory priority queue.
- **Node Filter & Scorer Engine:** Continuously prunes offline/deficient servers and algorithmically grades eligible candidates utilizing metrics like CPU, RAM, and GPU usage alongside current network health.
- **Worker Daemon (Node):** Autonomous python processes tracking simulated host diagnostics, binding dynamic ports, and broadcasting heartbeats to the centralized scheduler. Contains capability to emulate long-running tasks.
- **gRPC Communication Layer:** Defined via `.proto` definitions ensuring strict type structures for high-performance distributed invocation (`AssignTask`, `SendHeartbeat`, `ReportTaskStatus`).

## Getting Started

### Local Docker Compose (Recommended)
This requires Docker and Docker Compose. GPUFlow simulates heterogeneous resources within containers.
```bash
docker compose up --build
```
Access the dashboard via: `http://localhost:3000`

### Local Python Environment
If testing without Docker:
1. Start the main backend server (port 8000 & gRPC server on 50051)
   ```bash
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
   ```
2. Start simulated worker nodes in separate terminals
   ```bash
   export SIMULATED_GPU_COUNT=4.0
   python backend/app/worker/node.py
   ```
3. Start frontend
   ```bash
   cd frontend && npm install && npm run dev
   ```

## Academic Focus
- **Middleware Integration:** gRPC mapping procedure calls cleanly to distributed worker logic.
- **Simulated Hardware:** Environment variables (`SIMULATED_GPU_COUNT`) override hardware requirements seamlessly allowing multi-node cluster abstraction on single-developer machines. 
- **Message-Oriented Tracing:** Event tracking logs every state transition into a coherent stream mapping distributed flow from `JOB_SUBMITTED` locally to `TASK_COMPLETED` remotely.
