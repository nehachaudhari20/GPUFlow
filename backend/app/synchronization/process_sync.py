from __future__ import annotations

import logging
import threading
from typing import Dict, Optional, Tuple

from backend.app.synchronization.lamport_clock import LamportClock
from backend.app.synchronization.vector_clock import VectorClock

logger = logging.getLogger(__name__)

COORDINATOR_NODE_ID = "coordinator"

_worker_registry: Dict[str, "ProcessSynchronization"] = {}
_registry_lock = threading.Lock()
_coordinator_sync: Optional["ProcessSynchronization"] = None
_coordinator_lock = threading.Lock()


class ProcessSynchronization:
    """Per-process Lamport + vector clocks."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self.lamport = LamportClock()
        self.vector = VectorClock(node_id)

    def on_local_event(self) -> Tuple[int, Dict[str, int]]:
        lamport = self.lamport.tick()
        vector = self.vector.increment()
        return lamport, vector

    def on_send(self) -> Tuple[int, Dict[str, int]]:
        lamport = self.lamport.send_event()
        vector = self.vector.increment()
        return lamport, vector

    def on_receive(
        self, remote_lamport: int, remote_vector: Dict[str, int]
    ) -> Tuple[int, Dict[str, int]]:
        lamport = self.lamport.receive_event(remote_lamport)
        vector = self.vector.receive(remote_vector, self.node_id)
        return lamport, vector


def get_coordinator_sync() -> ProcessSynchronization:
    global _coordinator_sync
    with _coordinator_lock:
        if _coordinator_sync is None:
            _coordinator_sync = ProcessSynchronization(COORDINATOR_NODE_ID)
        return _coordinator_sync


def get_worker_sync(node_id: str) -> ProcessSynchronization:
    with _registry_lock:
        sync = _worker_registry.get(node_id)
        if sync is None:
            sync = ProcessSynchronization(node_id)
            _worker_registry[node_id] = sync
        return sync


def reset_sync_registry() -> None:
    global _coordinator_sync
    with _coordinator_lock:
        _coordinator_sync = None
    with _registry_lock:
        _worker_registry.clear()
