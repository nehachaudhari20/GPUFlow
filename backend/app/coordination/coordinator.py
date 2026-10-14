from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set

from backend.app.coordination.beacon_manager import BeaconManager
from backend.app.coordination.deadlock_detector import DeadlockDetector
from backend.app.coordination.distributed_lock import distributed_lock_coordinator
from backend.app.coordination.bully_election import ElectionRecord

logger = logging.getLogger(__name__)


class CoordinationService:
    """
    Aggregated coordination state on the laptop scheduler.

    Workload scheduling authority remains the scheduler; elected worker
    coordinators handle coordination duties (locks, election gossip), not FA1 scheduling.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._members: Dict[str, Dict[str, Any]] = {}
        self._coordinator_node_id: Optional[str] = None
        self._coordinator_election_id: int = -1
        self._membership_epoch: int = 1
        self._election_history: List[ElectionRecord] = []
        self._beacons = BeaconManager()
        self._deadlock = DeadlockDetector()
        self._algorithm = "bully"

    def register_member(
        self,
        node_id: str,
        election_id: int,
        hostname: str,
        grpc_port: int,
    ) -> None:
        with self._lock:
            stale = [
                mid
                for mid, m in self._members.items()
                if m.get("hostname") == hostname and mid != node_id
            ]
            for mid in stale:
                self._members.pop(mid, None)
            self._members[node_id] = {
                "node_id": node_id,
                "election_id": election_id,
                "hostname": hostname,
                "grpc_port": grpc_port,
                "registered_at": time.time(),
            }
        from backend.app.replication.replication_manager import replication_manager

        replication_manager.register_replica(node_id, hostname=hostname, role="follower")

    def report_coordinator(
        self, node_id: str, election_id: int, election_record: Optional[Dict[str, Any]] = None
    ) -> None:
        with self._lock:
            if node_id not in self._members:
                return
            same = (
                node_id == self._coordinator_node_id
                and election_id == self._coordinator_election_id
            )
            changed = (not same) and election_id >= self._coordinator_election_id
            if changed:
                self._coordinator_node_id = node_id
                self._coordinator_election_id = election_id
        if election_record:
            self.ingest_election_report(election_record)
        elif changed:
            self.ingest_election_report(
                {
                    "election_id": f"report-{node_id}-{int(time.time())}",
                    "initiator_node_id": node_id,
                    "participating_nodes": list(self._members.keys()),
                    "elected_coordinator_node_id": node_id,
                    "start_timestamp": time.time(),
                    "end_timestamp": time.time(),
                    "duration_ms": 0.0,
                    "reason": "coordinator_announcement",
                    "events": [{"type": "COORDINATOR", "node_id": node_id}],
                }
            )

    def record_election(self, record: ElectionRecord) -> None:
        with self._lock:
            self._election_history.append(record)
            if len(self._election_history) > 100:
                self._election_history = self._election_history[-100:]

    def ingest_election_report(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self._election_history.append(
                ElectionRecord(
                    election_id=data.get("election_id", ""),
                    initiator_node_id=data.get("initiator_node_id", ""),
                    participating_nodes=data.get("participating_nodes", []),
                    elected_coordinator_node_id=data.get("elected_coordinator_node_id"),
                    start_timestamp=data.get("start_timestamp", time.time()),
                    end_timestamp=data.get("end_timestamp"),
                    duration_ms=data.get("duration_ms"),
                    reason=data.get("reason", ""),
                    events=data.get("events", []),
                )
            )

    def ingest_beacon(self, **kwargs: Any) -> None:
        self._beacons.record_beacon(**kwargs)

    def get_leader(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "algorithm": self._algorithm,
                "coordinator_node_id": self._coordinator_node_id,
                "coordinator_election_id": self._coordinator_election_id,
                "membership_epoch": self._membership_epoch,
                "scheduling_authority": "laptop_scheduler",
                "note": (
                    "Elected worker coordinator manages coordination state only; "
                    "it does not replace the laptop scheduler on failure."
                ),
            }

    def list_members(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._members.values())

    def list_elections(self) -> List[Dict[str, Any]]:
        with self._lock:
            out = []
            for r in self._election_history:
                out.append(
                    {
                        "election_id": r.election_id,
                        "initiator": r.initiator_node_id,
                        "participating_nodes": r.participating_nodes,
                        "elected_coordinator": r.elected_coordinator_node_id,
                        "start_timestamp": r.start_timestamp,
                        "end_timestamp": r.end_timestamp,
                        "duration_ms": r.duration_ms,
                        "reason": r.reason,
                        "events": r.events,
                    }
                )
            return out

    def peer_map(self) -> Dict[str, int]:
        with self._lock:
            return {m["node_id"]: int(m["election_id"]) for m in self._members.values()}

    def peer_targets(self) -> Dict[str, tuple[str, int]]:
        with self._lock:
            return {
                m["node_id"]: (m["hostname"], int(m["grpc_port"]))
                for m in self._members.values()
            }

    def membership_epoch(self) -> int:
        with self._lock:
            return self._membership_epoch

    def bump_epoch(self) -> None:
        with self._lock:
            self._membership_epoch += 1

    def drop_member(self, node_id: str, reason: str = "member_failure") -> Optional[Dict[str, Any]]:
        with self._lock:
            member = self._members.pop(node_id, None)
            was_coord = self._coordinator_node_id == node_id
            self._membership_epoch += 1
        if member is None:
            return None
        from backend.app.replication.replication_manager import replication_manager

        replication_manager.mark_replica_status(node_id, "STALE")
        if was_coord:
            return self.elect_highest(reason="coordinator_failure")
        return self.get_leader()

    def elect_highest(self, reason: str = "re_election") -> Dict[str, Any]:
        with self._lock:
            if not self._members:
                self._coordinator_node_id = None
                self._coordinator_election_id = -1
                winner = None
                participating: List[str] = []
            else:
                winner = max(self._members.values(), key=lambda m: int(m["election_id"]))
                self._coordinator_node_id = winner["node_id"]
                self._coordinator_election_id = int(winner["election_id"])
                participating = list(self._members.keys())
        if winner:
            self.ingest_election_report(
                {
                    "election_id": f"failover-{winner['node_id']}-{int(time.time())}",
                    "initiator_node_id": winner["node_id"],
                    "participating_nodes": participating,
                    "elected_coordinator_node_id": winner["node_id"],
                    "start_timestamp": time.time(),
                    "end_timestamp": time.time(),
                    "duration_ms": 0.0,
                    "reason": reason,
                    "events": [
                        {"type": "ELECTION", "detail": reason},
                        {"type": "COORDINATOR", "node_id": winner["node_id"]},
                    ],
                }
            )
        return self.get_leader()

    def check_beacons(self) -> None:
        self._beacons.check_timeouts()

    def clear(self) -> None:
        with self._lock:
            self._members.clear()
            self._coordinator_node_id = None
            self._coordinator_election_id = -1
            self._election_history.clear()
        self._beacons.clear()
        self._deadlock.clear()
        distributed_lock_coordinator.clear()
        from backend.app.coordination.ra_demo import ra_demo

        ra_demo.clear()


coordination_service = CoordinationService()
