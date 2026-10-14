# Documentation of Distributed Communication Layers

Unit 2 distributed concepts are highly visible within how CPUFlow couples distinct components into a cohesive platform.

### RPC through gRPC
Remote Procedure Calls provide the foundational fabric for scheduler control plane operations. Defined using **Protocol Buffers**, strictly defined structures are compiled to Python endpoints to manage interaction between a central **Scheduler Servicer** and distributed **Worker Servicers**. Example calls include `AssignTask`, `SendHeartbeat` and `ReportTaskStatus`.

### Message-Oriented Communication
Component decoupling is achieved through an event manager system that emits structured **protobuf/SystemEvent** payloads rather than direct couplings. When a workload shifts states, are emitted with parameters (`JOB_QUEUED`, `NODE_SELECTED`, `TASK_ASSIGNED`). This lets monitoring dashboards consumed these without logic interference.

### Stream-Oriented Monitoring
Rather than constant API polling, the frontend subscribes to real-time events via a **WebSocket** conduit (/ws). These telemetry structures are pushed as soon as components emit them, demonstrating streaming live feedback loops within monitoring views.

### Peer-to-Peer (P2P) worker messaging capability
While scheduling is derived from a master servicer, worker-to-worker side-channels are also possible (`SendPeerMessage`). This provides direct data handoff or diagnostic telemetry paths (`DATA_SYNC`) without saturating the main scheduler control plane.

### Names/Identifiers/Addresses
To handle identification in a distributed environment, unambiguous identifiers are strictly generated: node_id (UUID), job_id (UUID), task_id, and event_id. Network endpoints are registered dynamically via `hostname:grpc_port`.

### Fault detection through basic heartbeat timeout<ctrl95>NOTE: if WebRTC is not implemented say so...

Nodes periodically broadcast their status to the central manager. If heartbeats cease, the manager triggers a failure detection event mapping exactly to Unit 2.2 concepts around unreliable connectivity and basic failure handling.

<total_tokens>13385739 tokens left</total_tokens>

#### WebRTC
WebRTC is not artificially forced into this specific scheduler-worker architecture for control-plane flow as high-bandwidth real-time video streaming is not the primary output. However, it was evaluated for Unit 2 relevance. The platform's direct Worker-to-Worker capability represents the foundation for potential P2P extensions if required for edge preprocessing workloads, demonstrating similar architectural decoupled flows rather than relying on forced integration in the main scheduling decision matrix.
