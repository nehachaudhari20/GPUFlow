from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class NodeClockOffset:
    node_id: str
    measured_offset_ms: float
    round_trip_time_ms: float
    last_sync_time: float
    synchronization_status: str = "synchronized"


@dataclass
class CristianSyncSample:
    """Application-level Cristian offset estimate (does not change OS clock)."""

    node_id: str
    client_request_ms: float
    client_response_ms: float
    server_receive_ms: float
    server_reply_ms: float

    @property
    def round_trip_time_ms(self) -> float:
        return max(0.0, self.client_response_ms - self.client_request_ms)

    @property
    def estimated_offset_ms(self) -> float:
        client_mid = (self.client_request_ms + self.client_response_ms) / 2.0
        server_mid = (self.server_receive_ms + self.server_reply_ms) / 2.0
        return server_mid - client_mid


class ClockSyncRegistry:
    """Stores Cristian-style offsets per worker node."""

    def __init__(self) -> None:
        self._offsets: Dict[str, NodeClockOffset] = {}
        self._lock = threading.Lock()

    def record_cristian_sample(self, sample: CristianSyncSample) -> NodeClockOffset:
        offset = NodeClockOffset(
            node_id=sample.node_id,
            measured_offset_ms=sample.estimated_offset_ms,
            round_trip_time_ms=sample.round_trip_time_ms,
            last_sync_time=time.time(),
            synchronization_status="synchronized",
        )
        with self._lock:
            self._offsets[sample.node_id] = offset
        logger.debug(
            "Clock sync node=%s offset_ms=%.2f rtt_ms=%.2f",
            sample.node_id,
            offset.measured_offset_ms,
            offset.round_trip_time_ms,
        )
        return offset

    def record_simple_sync(
        self,
        node_id: str,
        worker_wall_ms: float,
        server_receive_ms: float,
        server_reply_ms: float,
        client_request_ms: float | None = None,
        client_response_ms: float | None = None,
    ) -> NodeClockOffset:
        """Estimate offset when worker piggybacks wall time on heartbeat."""
        if client_request_ms is not None and client_response_ms is not None:
            sample = CristianSyncSample(
                node_id=node_id,
                client_request_ms=client_request_ms,
                client_response_ms=client_response_ms,
                server_receive_ms=server_receive_ms,
                server_reply_ms=server_reply_ms,
            )
            return self.record_cristian_sample(sample)
        rtt = max(0.0, server_reply_ms - server_receive_ms)
        offset = worker_wall_ms - server_receive_ms
        record = NodeClockOffset(
            node_id=node_id,
            measured_offset_ms=offset,
            round_trip_time_ms=rtt,
            last_sync_time=time.time(),
            synchronization_status="estimated",
        )
        with self._lock:
            self._offsets[node_id] = record
        return record

    def get_offset(self, node_id: str) -> Optional[NodeClockOffset]:
        with self._lock:
            return self._offsets.get(node_id)

    def list_offsets(self) -> List[NodeClockOffset]:
        with self._lock:
            return list(self._offsets.values())

    def clear(self) -> None:
        with self._lock:
            self._offsets.clear()


clock_sync_registry = ClockSyncRegistry()
