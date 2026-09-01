# GPUFlow Project Specification

## Problem Statement
AI workloads are resource-intensive and require efficient scheduling across distributed GPU clusters.

## Objectives
Build a custom workload scheduler capable of evaluating resource requirements and selecting the optimal worker node for execution.

## Users
Data scientists and ML engineers submitting compute jobs.

## FA1 Scope (Current implementation)
- Basic Distributed Systems setup (Unit 1 & 2).
- gRPC communication.
- Worker node registration and heartbeat-based failure detection.
- Custom resource manager with atomic allocation/release.
- Priority-aware workload queue with MongoDB persistence (optional).
- **Custom GPU-aware scheduler** (see below).
- Health-checks and REST API.

## FA2 Future Scope (Pending)
- Lamport clocks and clock synchronization.
- Global state algorithms.
- Distributed deadlock detection.
- Leader election.

## Technology Stack
- Frontend: React, Tailwind, Recharts
- Backend: FastAPI, Python, gRPC
- Database: MongoDB

## Important Design Decisions
- Scheduling algorithm is completely custom. Frameworks like Kubernetes, Ray, or Celery are intentionally avoided for node placement decisions.

---

## Custom Scheduling Algorithm (FA1)

### Pipeline

```
JOB → Priority Queue → Read Cluster State → Filter Ineligible Nodes
    → Calculate Resource Scores → Select Best Node → Reserve Resources
    → Return Scheduling Decision
```

### Priority Queue
Jobs are ordered by priority (`CRITICAL` > `HIGH` > `MEDIUM` > `LOW`), with FCFS tie-breaking on `created_at`. The queue policy is extensible via a custom sort key.

### Node Eligibility (`NodeFilter`)
A node is eligible only if:
- Status is `ONLINE` (healthy)
- `available GPU >= required GPU`
- `available GPU memory >= required GPU memory`
- `available CPU >= required CPU`
- `available RAM >= required RAM`

Ineligible nodes are recorded with explicit rejection reasons. If no node qualifies, the job remains `QUEUED`.

### Scoring (`NodeScorer` + `SchedulingPolicy`)
Eligible nodes receive a weighted score (0–100). Individual components are normalized to `[0, 1]` before combining:

| Component | Default Weight | Normalization |
|-----------|---------------|---------------|
| GPU availability | 40% | Average of `gpu_available/gpu_total` and `gpu_mem_available/gpu_mem_total` |
| CPU availability | 25% | `cpu_available / cpu_total` |
| RAM availability | 15% | `ram_available / ram_total` |
| Node health | 10% | `1.0` if ONLINE, else `0.0` |
| Load balance | 10% | `1 - (node_workloads / max_workloads_in_cluster)` |

**Total score** = sum of `(weight × normalized_component) × 100`

Weights are configurable via environment variables (`SCHEDULE_GPU_WEIGHT`, etc.) and must sum to 1.0.

The scheduler selects the **highest-scoring** eligible node, not the first available.

### Resource Reservation
After selection, `ResourceManager.allocate_resources()` atomically reserves resources under a lock. If allocation fails (e.g., concurrent change), the job stays `QUEUED` with an explanatory reason.

### Scheduling Decision
Every scheduling attempt returns an explainable `SchedulingDecision` containing:
- Job ID and workload name
- Candidate nodes with individual resource scores and total score
- Rejected nodes with reasons
- Selected node (if any)
- Allocation result
- Timestamp

### API Endpoints
- `POST /scheduler/run-next` — schedule the next queued job
- `POST /scheduler/run` — schedule all queued jobs in priority order
- `POST /scheduler/workloads/{job_id}/schedule` — schedule a specific job

### Modules
| Module | Responsibility |
|--------|---------------|
| `Scheduler` | Orchestrates the full pipeline |
| `SchedulingPolicy` | Configurable scoring weights |
| `NodeFilter` | Eligibility checks |
| `NodeScorer` | Normalized weighted scoring |
| `SchedulingDecision` | Explainable result model |
