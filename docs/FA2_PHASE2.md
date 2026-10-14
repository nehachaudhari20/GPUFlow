# FA2 Phase 2 — Distributed Coordination

## Components

| Module | Purpose |
|--------|---------|
| `bully_election.py` | Bully ELECTION / OK / COORDINATOR over worker P2P gRPC |
| `distributed_lock.py` | Ricart–Agrawala lock manager + reservation ledger view |
| `beacon_manager.py` | Beacon sequences on heartbeats (healthy / suspected / timeout) |
| `deadlock_detector.py` | Wait-for graph cycle detection (prototype) |
| `coordinator.py` | Scheduler-side aggregation (leader, members, elections) |

## Assumptions

- Message delivery is best-effort; partitions may yield conflicting coordinator claims until heal.
- The **laptop scheduler** remains FA1 scheduling authority; elected workers coordinate locks/election only.
- Deadlock detection reflects edges reported to the coordinator, not all hidden worker state.

## API (read-only)

- `GET /fa2/coordination/leader`
- `GET /fa2/coordination/elections`
- `GET /fa2/coordination/members`
- `GET /fa2/coordination/locks`
- `GET /fa2/coordination/beacons`
- `GET /fa2/coordination/deadlocks`

## Tests

```bash
PYTHONPATH=. pytest backend/tests/test_fa2_coordination.py -q
```

## Demo

1. Start control plane + workers.
2. `curl http://localhost:8000/fa2/coordination/leader`
3. `curl http://localhost:8000/fa2/coordination/beacons`
