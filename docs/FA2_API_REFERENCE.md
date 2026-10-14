# FA2 API Reference

All routes are under `/fa2` unless noted. Read-only except storage upload and function invoke.

## Phase 1
- `/fa2/synchronization/clocks`, `/events`, `/causality`, `/offsets`
- `/fa2/global-state/snapshots`, `/latest`

## Phase 2
- `/fa2/coordination/leader`, `/elections`, `/members`, `/locks`, `/beacons`, `/deadlocks`

## Phase 3
- `/fa2/recovery/summary`, `/history`, `/jobs/{job_id}`
- `/fa2/replication/status`, `/replicas`

## Phase 4
- `/fa2/storage/files` GET/POST, `/files/{id}`, `/replicas/{id}`
- `/fa2/functions`, `/functions/invoke`, `/functions/invocations/{id}`
- `/fa2/autoscaling/status`, `/decisions`
