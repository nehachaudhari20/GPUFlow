# FA2 Phase 1 — Distributed Clocks and Global Snapshots

## Overview

Phase 1 adds **Lamport logical clocks**, **vector clocks**, **Cristian-style physical clock offset estimation**, and **monitoring global snapshots** to GPUFlow without changing FA1 scheduling semantics or AWS deployment flows.

Each **scheduler (coordinator)** and **worker process** owns its own clock state. Timestamps are taken at real execution points (registration, heartbeats, job lifecycle, resource allocation).

## Algorithms

### Lamport logical clock

For local event: `L := L + 1`

For send: increment, attach `L` to the message

For receive with remote `T`: `L := max(L, T) + 1`

Implementation: `backend/app/synchronization/lamport_clock.py`

### Vector clock

Dictionary keyed by stable node IDs (supports dynamic workers).

- Local/send event: increment own component
- Receive: component-wise max with remote, then increment receiver component
- **Happens-before**: all components `a[i] <= b[i]` and at least one strict `<`
- **Concurrent**: neither happens-before the other

Implementation: `backend/app/synchronization/vector_clock.py`

### Cristian clock sync (application-level)

Workers piggyback wall-clock times on heartbeats. The coordinator estimates offset using request/response timing and RTT. **OS clocks on EC2 are not modified.**

When a full prior round-trip is available, `CristianSyncSample` computes:

- `RTT = client_response - client_request`
- `offset = server_midpoint - client_midpoint`

Implementation: `backend/app/synchronization/clock_sync.py`

### Global snapshot

`GlobalSnapshotService.capture()` builds a **monitoring assembled** snapshot from current coordinator observations. It is **not** a Chandy–Lamport consistent snapshot (no marker protocol, no in-transit channel recording).

Fields include nodes, resources, queues, reservations, recent events, and clock offsets.

Implementation: `backend/app/synchronization/global_snapshot.py`

## gRPC integration

Optional fields on existing messages (`protobufs/gpuflow.proto`):

| Message | Fields |
|---------|--------|
| `RegisterNodeRequest` | `lamport_time`, `vector_clock` |
| `HeartbeatRequest` | `lamport_time`, `vector_clock`, `client_wall_time_ms`, `cristian_client_request_ms`, `cristian_client_response_ms` |
| `HeartbeatResponse` | `server_time_ms`, `lamport_time`, `vector_clock` |
| `AssignTaskRequest` | `lamport_time`, `vector_clock` |
| `TaskStatusReportRequest` | `lamport_time`, `vector_clock` |
| `PeerMessageRequest` | `lamport_time`, `vector_clock` |

Wiring:

- `backend/app/communication/scheduler_server.py` — coordinator receive/send rules, Cristian samples, event logging
- `backend/app/worker/node.py` — worker send on register/heartbeat
- `backend/app/communication/worker_client.py` — coordinator send on `AssignTask`
- `backend/app/worker/worker_server.py` — worker receive on assign, send on status reports

## Synchronized events

Events carry `lamport_timestamp` and `vector_clock` when emitted via `log_synchronized_event` / `log_event_with_clocks`:

- `NODE_REGISTERED`, `HEARTBEAT_SENT`, `HEARTBEAT_RECEIVED`
- `JOB_SUBMITTED`, `JOB_QUEUED`
- `NODE_SELECTED`, `RESOURCE_ALLOCATED`, `RESOURCE_RELEASED`
- `TASK_ASSIGNED`, `TASK_STARTED`, `TASK_COMPLETED`, `TASK_FAILED`
- `NODE_OFFLINE`

## REST API (read-only)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/fa2/synchronization/clocks` | Coordinator Lamport + vector snapshot |
| GET | `/fa2/synchronization/events` | Recent events with sync metadata |
| GET | `/fa2/synchronization/causality?event_a_id=&event_b_id=` | Vector-clock causality between two events |
| GET | `/fa2/synchronization/offsets` | Cristian offset estimates per node |
| GET | `/fa2/global-state/snapshots` | Stored monitoring snapshots |
| GET | `/fa2/global-state/latest` | Latest snapshot (captures one if empty) |

Existing FA1 routes are unchanged.

## Testing

From repository root:

```bash
cd backend
pytest tests/ -q
```

FA2-focused tests: `backend/tests/test_fa2_synchronization.py`

## Local run (Phase 1)

```bash
# Control plane (scheduler + API + UI stack)
docker compose -f docker-compose.control.yml up -d --build

# Optional: local workers
docker compose up -d worker-1 worker-2 worker-3

# Hit FA2 endpoints
curl http://localhost:8000/fa2/synchronization/clocks
curl http://localhost:8000/fa2/global-state/latest
```

## Unit 3 syllabus mapping (typical)

| Topic | Implementation |
|-------|----------------|
| Logical time / Lamport clocks | `lamport_clock.py`, gRPC + events |
| Vector clocks / causality | `vector_clock.py`, `/fa2/synchronization/causality` |
| Physical clock synchronization | `clock_sync.py`, heartbeat piggyback |
| Global state | `global_snapshot.py` (monitoring; not Chandy–Lamport) |
| Distributed coordination | Per-process `ProcessSynchronization` |

## Limitations (Phase 1)

- Snapshots are **best-effort assembled**, not consistent distributed snapshots.
- Worker-local synchronized events in worker processes are not merged into the scheduler HTTP event log (scheduler logs worker send timestamps on heartbeat/register).
- Cristian sync quality depends on network RTT and heartbeat interval.
- No change to simulated task duration (`time.sleep`) or AWS provisioning in this phase.
