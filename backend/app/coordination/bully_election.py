from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

ELECTION_TIMEOUT_S = 3.0


class ElectionState(str, Enum):
    IDLE = "IDLE"
    ELECTION_IN_PROGRESS = "ELECTION_IN_PROGRESS"
    COORDINATOR = "COORDINATOR"
    FOLLOWER = "FOLLOWER"


@dataclass
class ElectionRecord:
    election_id: str
    initiator_node_id: str
    participating_nodes: List[str]
    elected_coordinator_node_id: Optional[str]
    start_timestamp: float
    end_timestamp: Optional[float] = None
    duration_ms: Optional[float] = None
    reason: str = ""
    events: List[Dict[str, Any]] = field(default_factory=list)


class BullyElectionManager:
    """
    Bully leader election using inter-node messages (ELECTION / OK / COORDINATOR).

    Assumes partial synchrony: messages may be delayed or lost; partitions can
    yield split-brain coordinator claims until connectivity heals. No consensus.
    """

    def __init__(
        self,
        node_id: str,
        election_id: int,
        send_message: Optional[Callable[[str, int, str, str], bool]] = None,
    ) -> None:
        self.node_id = node_id
        self.election_id = election_id
        self._send_message = send_message
        self._lock = threading.RLock()
        self._state = ElectionState.IDLE
        self._coordinator_node_id: Optional[str] = None
        self._coordinator_election_id: int = -1
        self._peers: Dict[str, int] = {}
        self._history: List[ElectionRecord] = []
        self._current: Optional[ElectionRecord] = None
        self._awaiting_ok: set[str] = set()
        self._received_ok_from_higher = False
        self._election_timer: Optional[threading.Timer] = None

    def set_peers(self, peers: Dict[str, int]) -> None:
        with self._lock:
            self._peers = dict(peers)

    def get_state(self) -> ElectionState:
        with self._lock:
            return self._state

    def get_coordinator(self) -> tuple[Optional[str], int]:
        with self._lock:
            return self._coordinator_node_id, self._coordinator_election_id

    def list_history(self) -> List[ElectionRecord]:
        with self._lock:
            return list(self._history)

    def _log_event(self, record: ElectionRecord, kind: str, detail: str) -> None:
        record.events.append(
            {"timestamp": time.time(), "type": kind, "node_id": self.node_id, "detail": detail}
        )

    def _cancel_timer(self) -> None:
        if self._election_timer is not None:
            self._election_timer.cancel()
            self._election_timer = None

    def _finish_election(
        self, winner_node_id: str, winner_election_id: int, reason: str
    ) -> None:
        record = self._current
        if record is None:
            return
        record.elected_coordinator_node_id = winner_node_id
        record.end_timestamp = time.time()
        record.duration_ms = (record.end_timestamp - record.start_timestamp) * 1000.0
        record.reason = reason
        self._coordinator_node_id = winner_node_id
        self._coordinator_election_id = winner_election_id
        if winner_node_id == self.node_id:
            self._state = ElectionState.COORDINATOR
        else:
            self._state = ElectionState.FOLLOWER
        self._history.append(record)
        self._current = None
        self._cancel_timer()
        logger.info(
            "Election %s complete: coordinator=%s (reason=%s)",
            record.election_id,
            winner_node_id,
            reason,
        )

    def _announce_coordinator(self) -> None:
        if self._send_message is None:
            return
        payload = f"COORDINATOR|{self.node_id}|{self.election_id}"
        for peer_id, (host, port) in self._peer_targets().items():
            if peer_id == self.node_id:
                continue
            self._send_message(host, port, "COORDINATOR", payload)

    def _peer_targets(self) -> Dict[str, tuple[str, int]]:
        return getattr(self, "_peer_targets_map", {})

    def set_peer_targets(self, targets: Dict[str, tuple[str, int]]) -> None:
        self._peer_targets_map = dict(targets)

    def start_election(self, reason: str = "manual") -> Optional[ElectionRecord]:
        with self._lock:
            if self._state == ElectionState.ELECTION_IN_PROGRESS:
                return self._current
            self._state = ElectionState.ELECTION_IN_PROGRESS
            self._received_ok_from_higher = False
            record = ElectionRecord(
                election_id=str(uuid.uuid4()),
                initiator_node_id=self.node_id,
                participating_nodes=sorted(self._peers.keys()) + [self.node_id],
                elected_coordinator_node_id=None,
                start_timestamp=time.time(),
                reason=reason,
            )
            self._current = record
            self._log_event(record, "ELECTION", f"Started election: {reason}")

        higher = [
            (pid, eid)
            for pid, eid in self._peers.items()
            if eid > self.election_id
        ]
        if not higher:
            self._log_event(record, "COORDINATOR", "No higher-ID peers; self elected")
            self._finish_election(self.node_id, self.election_id, "highest_id_reachable")
            self._announce_coordinator()
            return record

        self._awaiting_ok = {pid for pid, _ in higher}
        if self._send_message:
            for pid, eid in higher:
                host, port = self._peer_targets().get(pid, ("", 0))
                if port > 0:
                    payload = f"ELECTION|{self.node_id}|{self.election_id}"
                    self._send_message(host, port, "ELECTION", payload)
                    self._log_event(record, "ELECTION", f"Sent ELECTION to {pid}")

        def on_timeout() -> None:
            with self._lock:
                if self._state != ElectionState.ELECTION_IN_PROGRESS:
                    return
                if self._received_ok_from_higher:
                    return
                cur = self._current
                if cur:
                    self._log_event(cur, "COORDINATOR", "Election timeout; self wins")
                self._finish_election(self.node_id, self.election_id, "timeout_no_higher_response")
            self._announce_coordinator()

        self._cancel_timer()
        self._election_timer = threading.Timer(ELECTION_TIMEOUT_S, on_timeout)
        self._election_timer.daemon = True
        self._election_timer.start()
        return record

    def handle_message(self, message_type: str, payload: str, sender_node_id: str) -> None:
        parts = payload.split("|")
        with self._lock:
            record = self._current

        if message_type == "ELECTION" or (parts and parts[0] == "ELECTION"):
            sender_eid = int(parts[2]) if len(parts) > 2 else 0
            if sender_eid > self.election_id:
                if self._send_message:
                    host, port = self._peer_targets().get(sender_node_id, ("", 0))
                    if port > 0:
                        self._send_message(host, port, "OK", f"OK|{self.node_id}")
                self.start_election(reason="higher_id_peer_election")
            else:
                if self._send_message:
                    host, port = self._peer_targets().get(sender_node_id, ("", 0))
                    if port > 0:
                        self._send_message(host, port, "OK", f"OK|{self.node_id}")
            return

        if message_type == "OK" or (parts and parts[0] == "OK"):
            with self._lock:
                self._received_ok_from_higher = True
                if sender_node_id in self._awaiting_ok:
                    self._awaiting_ok.discard(sender_node_id)
                if record:
                    self._log_event(record, "OK", f"Received OK from {sender_node_id}")
            return

        if message_type == "COORDINATOR" or (parts and parts[0] == "COORDINATOR"):
            coord_node = parts[1] if len(parts) > 1 else sender_node_id
            coord_eid = int(parts[2]) if len(parts) > 2 else 0
            with self._lock:
                if coord_eid >= self._coordinator_election_id:
                    self._coordinator_node_id = coord_node
                    self._coordinator_election_id = coord_eid
                    self._state = (
                        ElectionState.COORDINATOR
                        if coord_node == self.node_id
                        else ElectionState.FOLLOWER
                    )
                    if coord_eid > self.election_id and self._state != ElectionState.COORDINATOR:
                        self.start_election(reason="higher_id_coordinator_rejoined")

    def on_coordinator_timeout(self) -> None:
        self.start_election(reason="coordinator_failure")
