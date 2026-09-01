# GPUFlow Project Specification

## Problem Statement
AI workloads are resource-intensive and require efficient scheduling across distributed GPU clusters.

## Objectives
Build a custom workload scheduler capable of evaluating resource requirements and selecting the optimal worker node for execution.

## Users
Data scientists and ML engineers submitting compute jobs.

## FA1 Scope (Current implementation)
- Basic Distributed Systems setup (Unit 1 & 2).
- gRPC communication.
- Base scheduling and worker architecture.
- Health-checks and API skeleton.

## FA2 Future Scope (Pending)
- Lamport clocks and clock synchronization.
- Global state algorithms.
- Distributed deadlock detection.
- Leader election.

## Technology Stack
- Frontend: React, Tailwind, Recharts
- Backend: FastAPI, Python, gRPC
- Database: MongoDB

## Important Design Decisions
- Scheduling algorithm is completely custom. Frameworks like Kubernetes or Celery are intentionally avoided for this component.
