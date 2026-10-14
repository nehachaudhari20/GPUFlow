# FA1 Syllabus Mapping

This document maps CPUFlow features directly to the FA1 Distributed Systems syllabus (Units 1 & 2).

| Syllabus Concept | How it is implemented in CPUFlow | Location in Codebase | Viva Demonstration Strategy |
| :--- | :--- | :--- | :--- |
| **Unit 1: Distributed Architecture** | Master-Worker split; Scheduler coordinates autonomous nodes | `backend/app/scheduler/`, `backend/app/worker/` | Open the Cluster tab to view all connected node representations |
| **Unit 1: Middleware** | Protocol Buffers & gRPC bridge scheduler & workers | `protobufs/gpuflow.proto` | Show protobuf schemas and compiled Python gRPC interfaces |
| **Unit 1: Distributed Resource Management** | Heterogeneous resource tracking & allocation across cluster | `backend/app/scheduler/resource_manager.py` | Submit a job requiring more resources than available on node 3 to show allocation behavior |
| **Unit 1: Virtualization** | Multi-container isolation via Docker | `docker-compose.yml`, `Dockerfile` | Run `docker compose up --build` and inspect separate worker containers |
| **Unit 2: RPC / gRPC** | Control plane commands (`AssignTask`, `SendHeartbeat`) | `backend/app/communication/` | Trace gRPC request calls in `test_e2e.py` |
| **Unit 2: Stream Communication** | Real-time WebSocket streaming of cluster state | `backend/app/api/websocket.py` | Show live event updates in Communication Log tab |
| **Unit 2: P2P Messaging** | Direct worker-to-worker gRPC communication | `backend/app/worker/node.py:109` | Show `SendPeerMessage` execution in `test_e2e.py` |
| **Unit 2: Identifiers & Names** | UUID-based system naming (`job_id`, `node_id`, `event_id`) | `backend/app/models/` | Show consistent ID propagation across REST and Event APIs |
| **Unit 2: Basic Fault Detection** | Heartbeat timeout tracking marks failed nodes offline | `backend/app/scheduler/cluster_state.py` | Stop a worker daemon and demonstrate it automatically switching to `OFFLINE` |

---

## FA2 Syllabus Boundary (Future Scope)

The following advanced topics belong to the FA2 syllabus and are **intentionally not implemented** in this FA1 submission:
- **Lamport Clocks & Vector Clocks**: Logical clocks for event ordering across distributed nodes.
- **Leader Election Algorithms**: Bully algorithm or Ring algorithm for scheduler failover.
- **Distributed Mutual Exclusion**: Ricart-Agrawala or Token Ring algorithms.
- **Replicated State & Consensus**: Paxos or Raft consensus engines.
- **Distributed Deadlock Handling**: Edge-chasing algorithms.
- **State Migration & Recovery**: Checkpointing and live migration of running workloads.
