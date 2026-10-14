from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.app.events.event_manager import event_manager
from backend.app.scheduler.cluster_state import cluster_state
from backend.app.scheduler.resource_manager import resource_manager
from backend.app.services.workload_service import workload_service
from backend.app.synchronization.clock_sync import clock_sync_registry
from backend.app.synchronization.process_sync import get_coordinator_sync

logger = logging.getLogger(__name__)


class GlobalSnapshotService:
    """
    Assembles a monitoring snapshot from recent cluster observations.

    This is NOT a Chandy-Lamport consistent distributed snapshot (no marker protocol).
    """

    def __init__(self) -> None:
        self._snapshots: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._max_snapshots = 50

    def capture(self) -> Dict[str, Any]:
        captured_at = time.time()
        coordinator = get_coordinator_sync()
        lamport_time, vector_clock = coordinator.on_local_event()

        nodes_copy = cluster_state.get_all_nodes()
        failure_events = cluster_state.get_failure_events()
        cluster_resources = resource_manager.get_cluster_resources().model_dump()

        workloads = workload_service.list_workloads()
        queued = [w.model_dump() for w in workloads if w.status.value == "QUEUED"]
        running = [w.model_dump() for w in workloads if w.status.value == "RUNNING"]

        reservations = resource_manager.list_active_reservations()

        recent_events = [
            e.model_dump() for e in event_manager.get_events(limit=100)
        ]

        snapshot = {
            "snapshot_id": str(uuid.uuid4()),
            "timestamp": captured_at,
            "snapshot_type": "monitoring_assembled",
            "consistent_distributed_snapshot": False,
            "coordinator_logical_timestamp": lamport_time,
            "coordinator_vector_clock": vector_clock,
            "registered_nodes": [n.model_dump() for n in nodes_copy],
            "online_nodes": [n.node_id for n in nodes_copy if n.status == "ONLINE"],
            "offline_nodes": [n.node_id for n in nodes_copy if n.status != "ONLINE"],
            "cluster_resources": cluster_resources,
            "queued_workloads": queued,
            "running_workloads": running,
            "active_resource_reservations": reservations,
            "failure_events": [e.model_dump() for e in failure_events],
            "recent_distributed_events": recent_events,
            "clock_offsets": [
                o.__dict__ for o in clock_sync_registry.list_offsets()
            ],
        }

        with self._lock:
            self._snapshots.append(snapshot)
            if len(self._snapshots) > self._max_snapshots:
                self._snapshots = self._snapshots[-self._max_snapshots :]

        logger.info("Captured monitoring snapshot %s", snapshot["snapshot_id"])
        return snapshot

    def list_snapshots(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._snapshots[-limit:])

    def latest(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self._snapshots:
                return None
            return dict(self._snapshots[-1])

    def clear(self) -> None:
        with self._lock:
            self._snapshots.clear()


global_snapshot_service = GlobalSnapshotService()
