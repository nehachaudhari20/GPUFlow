# CPUFlow Architecture

The architecture illustrates a client-server distributed model paired with direct worker-to-worker side-channels.

## Data Flow
`User` → `Frontend Dashboard` → `FastAPI REST Interface` → `Workload Queue` → `Scheduler Kernel` → `Resource Manager` → `gRPC Stubs` → `Remote Worker Node` → `Local Task Executor`

## Functional Subsystems

### 1. Node Registration & Heartbeat
Workers broadcast their presence directly to the Scheduler via a gRPC `RegisterNode` request which shares identification vectors and port mapping. Following registration, an internal thread initiates a `SendHeartbeat` payload at an interval specifying utilization. 

### 2. Failure Detection
The `ClusterState` manager maintains a monotonic timer on all connected nodes. If a background sweeper thread detects a heartbeat absence exceeding `15s`, it generates a `NODE_OFFLINE` system event and prohibits the worker from participating in the next scheduling phase.

### 3. Scheduling & Allocation
Upon evaluation cycles, workloads are shifted sequentially from `QUEUED` via the Node Filter subsystem which purges endpoints lacking sufficient raw resources or those failing health checks. Remaining resources are shifted to the `Node Scorer`.

### 4. Task Execution & Reporting
Following a successful `AssignTask` request, the Scheduler records an optimistic reservation while the remote Worker initiates a background simulation thread. Post-execution, the worker makes a `ReportTaskStatus` invocation to notify completion allowing the Scheduler's `Resource Manager` to safely detach resource locks.

### 5. Monitoring & Broadcasting
Event hooks are decoupled from logic using an `EventManager` pipeline. When logic completes an operation, an event structure is emitted. These structures are consumed asynchronously and piped through WebSocket conduits back to the frontend.
