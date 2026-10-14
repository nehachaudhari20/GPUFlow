from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

from backend.app.events.event_manager import EventType, SystemEvent, event_manager
from backend.app.synchronization.process_sync import (
    ProcessSynchronization,
    get_coordinator_sync,
)


def stamp_local_event(
    sync: ProcessSynchronization,
) -> Tuple[int, Dict[str, int], float]:
    lamport, vector = sync.on_local_event()
    return lamport, vector, time.time()


def log_synchronized_event(
    event_type: EventType,
    sync: Optional[ProcessSynchronization] = None,
    source: str = "SCHEDULER",
    destination: Optional[str] = None,
    job_id: Optional[str] = None,
    node_id: Optional[str] = None,
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> SystemEvent:
    process_sync = sync or get_coordinator_sync()
    lamport, vector, physical = stamp_local_event(process_sync)
    meta = dict(metadata or {})
    meta["physical_timestamp_ms"] = int(physical * 1000)
    event = SystemEvent(
        event_type=event_type,
        source=source,
        destination=destination,
        job_id=job_id,
        node_id=node_id,
        message=message,
        metadata=meta,
        lamport_timestamp=lamport,
        vector_clock=vector,
        timestamp=physical,
    )
    event_manager.emit(event)
    return event


def apply_received_clocks(
    sync: ProcessSynchronization,
    remote_lamport: int,
    remote_vector: Dict[str, int],
) -> Tuple[int, Dict[str, int]]:
    return sync.on_receive(remote_lamport, remote_vector)


def log_event_with_clocks(
    event_type: EventType,
    lamport: int,
    vector: Dict[str, int],
    source: str = "SCHEDULER",
    destination: Optional[str] = None,
    job_id: Optional[str] = None,
    node_id: Optional[str] = None,
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> SystemEvent:
    physical = time.time()
    meta = dict(metadata or {})
    meta["physical_timestamp_ms"] = int(physical * 1000)
    event = SystemEvent(
        event_type=event_type,
        source=source,
        destination=destination,
        job_id=job_id,
        node_id=node_id,
        message=message,
        metadata=meta,
        lamport_timestamp=lamport,
        vector_clock=vector,
        timestamp=physical,
    )
    event_manager.emit(event)
    return event
