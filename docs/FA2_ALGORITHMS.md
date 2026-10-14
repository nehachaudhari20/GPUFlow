# FA2 Algorithms Summary

| Topic | Implementation |
|-------|----------------|
| Lamport clocks | `synchronization/lamport_clock.py` |
| Vector clocks | `synchronization/vector_clock.py` |
| Cristian sync | `synchronization/clock_sync.py` |
| Bully election | `coordination/bully_election.py` |
| Ricart–Agrawala locks | `coordination/distributed_lock.py` — defer if local `(T, id)` is smaller; enter after REPLY from all other members |
| Wait-for deadlock | `coordination/deadlock_detector.py` |
| Retry / migration | `recovery/recovery_manager.py` |
| Primary-writer replication | `replication/replication_manager.py` |
