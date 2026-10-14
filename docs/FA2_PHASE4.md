# FA2 Phase 4 — Distributed Services (Unit 4)

## Storage prototype

Replicated file storage via worker gRPC `StoreFile` / `RetrieveFile` on distinct worker hosts.

## Serverless-style functions

Allowlisted registry only (`/fa2/functions`). Invocations run in a subprocess with timeout.

## Autoscaling

Decision-only engine at `/fa2/autoscaling/status` — does not create/terminate EC2.
