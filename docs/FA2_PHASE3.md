# FA2 Phase 3 — Fault Tolerance and Replicated State

## Recovery

`RecoveryManager` reacts to heartbeat timeouts (`cluster_state.check_timeouts`) and schedules restart-based retries with exponential backoff.

- At-least-once execution semantics (documented limitation)
- Attempt IDs + stale status rejection via `validate_status_update`
- Migration records track old/new node and attempt number (restart, not live migration)

## Replication

Primary-writer sequence numbers; optional MongoDB append log when `MONGO_URI` is set.

## API

- `GET /fa2/recovery/summary`
- `GET /fa2/recovery/history`
- `GET /fa2/recovery/jobs/{job_id}`
- `GET /fa2/replication/status`
- `GET /fa2/replication/replicas`

Dev-only: `POST /fa2/recovery/simulate-failure/{node_id}` when `FA2_DEV_CONTROLS_ENABLED=true`.
