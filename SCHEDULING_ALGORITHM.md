# Custom GPU-Aware Scheduling Algorithm

GPUFlow avoids generic clustering architectures (like Kubernetes or Celery) in favor of a specialized heuristic algorithm bridging AI workload constraints with heterogeneous clustered hardware.

## Lifecycle 

1. **Receive workload:** The API processes an HTTP POST establishing GPU/CPU/RAM minimums.
2. **Validate requirements:** Reject invalid bounds.
3. **Queue insertion:** Submits the task under a Priority queue configuration (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
4. **Obtain current node state:** Poll all registered node topologies from `ClusterState`.
5. **Filter nodes:** Isolate workers presently identified as `ONLINE`.
6. **Reject nodes:** Reject workers possessing capacities beneath the workload minimum boundaries.
7. **Calculate node scores:** Evaluate normalization across hardware limits (see matrix below).
8. **Selection:** Identify the highest-scoring candidate structure. 
9. **Reserve resources:** Immediately lock logical resources within the `Resource Manager` to prevent race conditions.
10. **Dispatch task:** Initiate `gRPC.AssignTask` sending the task remotely.
11. **Track execution:** Reconcile node telemetry to task success.
12. **Release resources:** Detach resource locks immediately tracking `TASK_COMPLETED` or `TASK_FAILED`.
13. **Reconsider queued jobs:** Trigger loops if queued buffers possess unallocated items.

## Weighted Scoring Matrix
The scheduler employs a multi-criteria scoring algorithm to optimize placement balancing capacity versus existing density.

**Score** = 
- `40% GPU Availability` (Prioritize AI compute availability over all other vectors)
- `25% CPU Availability` 
- `15% RAM Availability`
- `10% Node Health`
- `10% Load Balance`

*Implementation Details:* By multiplying scaled availability components by predetermined constants, GPUFlow natively disperses compute-heavy processing away from stressed nodes, significantly improving general availability uptime without demanding a global state sync.
