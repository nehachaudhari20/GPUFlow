from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.app.config import settings

logger = logging.getLogger(__name__)


class BeaconHealth(str, Enum):
    HEALTHY = "HEALTHY"
    SUSPECTED = "SUSPECTED"
    CONFIRMED_TIMEOUT = "CONFIRMED_TIMEOUT"
    RECOVERED = "RECOVERED"


@dataclass
class BeaconRecord:
    node_id: str
    sequence: int
    coordinator_node_id: Optional[str]
    membership_epoch: int
    lamport_timestamp: int
    vector_clock: Dict[str, int]
    cpu_available: float
    ram_available: float
    status: str
    health: BeaconHealth
    last_seen: float
    missed_beacons: int = 0


class BeaconManager:
    """Structured beacon tracking layered on heartbeat traffic."""

    def __init__(self, suspect_after: int = 2, timeout_after: int = 4) -> None:
        self._lock = threading.Lock()
        self._beacons: Dict[str, BeaconRecord] = {}
        self._suspect_after = suspect_after
        self._timeout_after = timeout_after
        self._events: List[Dict[str, Any]] = []

    def record_beacon(
        self,
        node_id: str,
        sequence: int,
        coordinator_node_id: Optional[str],
        membership_epoch: int,
        lamport_timestamp: int,
        vector_clock: Dict[str, int],
        cpu_available: float,
        ram_available: float,
        status: str,
    ) -> BeaconRecord:
        now = time.time()
        with self._lock:
            prev = self._beacons.get(node_id)
            missed = 0 if prev is None else max(0, sequence - prev.sequence - 1)
            health = BeaconHealth.HEALTHY
            if prev and prev.health == BeaconHealth.CONFIRMED_TIMEOUT:
                health = BeaconHealth.RECOVERED
                self._events.append(
                    {
                        "timestamp": now,
                        "type": "BEACON_RECOVERED",
                        "node_id": node_id,
                    }
                )
            record = BeaconRecord(
                node_id=node_id,
                sequence=sequence,
                coordinator_node_id=coordinator_node_id,
                membership_epoch=membership_epoch,
                lamport_timestamp=lamport_timestamp,
                vector_clock=dict(vector_clock),
                cpu_available=cpu_available,
                ram_available=ram_available,
                status=status,
                health=health,
                last_seen=now,
                missed_beacons=missed,
            )
            self._beacons[node_id] = record
            return record

    def check_timeouts(self) -> List[str]:
        now = time.time()
        timed_out: List[str] = []
        with self._lock:
            for node_id, rec in self._beacons.items():
                gap = now - rec.last_seen
                if gap > settings.heartbeat_timeout:
                    if rec.health != BeaconHealth.CONFIRMED_TIMEOUT:
                        rec.health = BeaconHealth.CONFIRMED_TIMEOUT
                        self._events.append(
                            {
                                "timestamp": now,
                                "type": "BEACON_TIMEOUT",
                                "node_id": node_id,
                            }
                        )
                        timed_out.append(node_id)
                elif gap > settings.heartbeat_interval * self._suspect_after:
                    if rec.health == BeaconHealth.HEALTHY:
                        rec.health = BeaconHealth.SUSPECTED
                        self._events.append(
                            {
                                "timestamp": now,
                                "type": "BEACON_SUSPECTED",
                                "node_id": node_id,
                            }
                        )
        return timed_out

    def list_beacons(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "node_id": b.node_id,
                    "sequence": b.sequence,
                    "coordinator_node_id": b.coordinator_node_id,
                    "membership_epoch": b.membership_epoch,
                    "lamport_timestamp": b.lamport_timestamp,
                    "vector_clock": b.vector_clock,
                    "cpu_available": b.cpu_available,
                    "ram_available": b.ram_available,
                    "status": b.status,
                    "health": b.health.value,
                    "last_seen": b.last_seen,
                    "missed_beacons": b.missed_beacons,
                }
                for b in self._beacons.values()
            ]

    def list_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._events[-limit:])

    def clear(self) -> None:
        with self._lock:
            self._beacons.clear()
            self._events.clear()
