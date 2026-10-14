# FA2 Demo Guide

1. `docker compose -f docker-compose.control.yml up -d --build`
2. Optional workers: `docker compose up -d worker-1 worker-2 worker-3`
3. Open UI → **FA2 Distributed** tab
4. Submit a workload (FA1) and watch synchronization events
5. `curl http://localhost:8000/fa2/coordination/leader`
