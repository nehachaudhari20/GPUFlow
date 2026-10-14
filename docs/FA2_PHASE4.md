# FA2 Phase 4 — Distributed Services (Unit 4)

## Storage prototype

Replicated file storage via worker gRPC `StoreFile` / `RetrieveFile` on distinct worker hosts.

## Serverless-style functions

Allowlisted registry only (`/fa2/functions`). The scheduler reserves a CPU worker, then the worker executes `InvokeFunction` over gRPC. Computation runs **on the worker process**, not on the FastAPI host.

## Autoscaling

Decision-only engine at `/fa2/autoscaling/status` — does not create/terminate EC2.
