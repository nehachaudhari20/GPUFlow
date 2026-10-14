from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class LockRequestState(str, Enum):
    PENDING = "PENDING"
    GRANTED = "GRANTED"
    DEFERRED = "DEFERRED"
    RELEASED = "RELEASED"
    REJECTED = "REJECTED"


@dataclass
class LockRequest:
    request_id: str
    resource_key: str
    node_id: str
    lamport_timestamp: int
    state: LockRequestState = LockRequestState.PENDING
    created_at: float = field(default_factory=time.time)
    granted_at: Optional[float] = None


class RicartAgrawalaLockManager:
    """
    Ricart–Agrawala mutual exclusion for a cluster reservation ledger key.

    Ordering: (lamport_timestamp, node_id). Deferred replies until local CS exit.
    """

    def __init__(
        self,
        node_id: str,
        lamport_provider: Callable[[], int],
        lamport_tick: Callable[[], int],
        send_reply: Optional[Callable[[str, str, int], None]] = None,
    ) -> None:
        self.node_id = node_id
        self._lamport = lamport_provider
        self._lamport_tick = lamport_tick
        self._send_reply = send_reply
        self._lock = threading.Lock()
        self._in_critical_section = False
        self._pending_requests: List[LockRequest] = []
        self._deferred_replies: Set[str] = set()
        self._membership_epoch: int = 1
        self._live_members: Set[str] = set()
        self._history: List[LockRequest] = []
        self._owner: Optional[str] = None
        self._owner_resource: Optional[str] = None

    def set_membership(self, epoch: int, members: Set[str]) -> None:
        with self._lock:
            self._membership_epoch = epoch
            self._live_members = set(members)

    def request_lock(self, resource_key: str) -> LockRequest:
        ts = self._lamport_tick()
        req = LockRequest(
            request_id=str(uuid.uuid4()),
            resource_key=resource_key,
            node_id=self.node_id,
            lamport_timestamp=ts,
        )
        with self._lock:
            self._pending_requests.append(req)
            self._history.append(req)
        return req

    def handle_remote_request(
        self, request_id: str, resource_key: str, remote_node: str, timestamp: int
    ) -> None:
        with self._lock:
            if remote_node not in self._live_members and self._live_members:
                return
            req = LockRequest(
                request_id=request_id,
                resource_key=resource_key,
                node_id=remote_node,
                lamport_timestamp=timestamp,
            )
            self._pending_requests.append(req)
            self._history.append(req)
            should_defer = self._in_critical_section or self._should_defer(req)
        if should_defer:
            with self._lock:
                self._deferred_replies.add(remote_node)
        elif self._send_reply:
            self._send_reply(remote_node, request_id, timestamp)

    def _should_defer(self, incoming: LockRequest) -> bool:
        for local in self._pending_requests:
            if local.node_id == self.node_id and local.state == LockRequestState.PENDING:
                if (incoming.lamport_timestamp, incoming.node_id) < (
                    local.lamport_timestamp,
                    local.node_id,
                ):
                    return True
        return False

    def on_reply(self, from_node: str) -> None:
        with self._lock:
            self._deferred_replies.discard(from_node)

    def try_enter_critical_section(self, resource_key: str) -> bool:
        with self._lock:
            if self._in_critical_section:
                return False
            my_req = next(
                (
                    r
                    for r in self._pending_requests
                    if r.node_id == self.node_id
                    and r.resource_key == resource_key
                    and r.state == LockRequestState.PENDING
                ),
                None,
            )
            if my_req is None:
                return False
            required = self._live_members - {self.node_id}
            if required:
                return False
            for other in self._pending_requests:
                if other.node_id == self.node_id:
                    continue
                if other.state != LockRequestState.PENDING:
                    continue
                if (other.lamport_timestamp, other.node_id) < (
                    my_req.lamport_timestamp,
                    my_req.node_id,
                ):
                    return False
            my_req.state = LockRequestState.GRANTED
            my_req.granted_at = time.time()
            self._in_critical_section = True
            self._owner = self.node_id
            self._owner_resource = resource_key
            return True

    def release_lock(self, resource_key: str) -> None:
        with self._lock:
            self._in_critical_section = False
            self._owner = None
            self._owner_resource = None
            for r in self._pending_requests:
                if r.node_id == self.node_id and r.resource_key == resource_key:
                    r.state = LockRequestState.RELEASED
            deferred = list(self._deferred_replies)
            self._deferred_replies.clear()
        if self._send_reply:
            for node in deferred:
                self._send_reply(node, "deferred", self._lamport())

    def list_requests(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "request_id": r.request_id,
                    "resource_key": r.resource_key,
                    "node_id": r.node_id,
                    "lamport_timestamp": r.lamport_timestamp,
                    "state": r.state.value,
                    "created_at": r.created_at,
                    "granted_at": r.granted_at,
                }
                for r in self._history[-100:]
            ]

    def get_owner(self) -> Tuple[Optional[str], Optional[str]]:
        with self._lock:
            return self._owner, self._owner_resource


class DistributedLockCoordinator:
    """Scheduler-side aggregate view of lock state across workers (prototype ledger)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ledger: Dict[str, str] = {}
        self._requests: List[Dict[str, Any]] = []

    def record_request(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self._requests.append(data)
            if len(self._requests) > 500:
                self._requests = self._requests[-500:]

    def grant_ledger(self, resource_key: str, node_id: str) -> bool:
        with self._lock:
            if resource_key in self._ledger and self._ledger[resource_key] != node_id:
                return False
            self._ledger[resource_key] = node_id
            return True

    def release_ledger(self, resource_key: str, node_id: str) -> None:
        with self._lock:
            if self._ledger.get(resource_key) == node_id:
                del self._ledger[resource_key]

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "ledger": dict(self._ledger),
                "requests": list(self._requests[-50:]),
            }

    def clear(self) -> None:
        with self._lock:
            self._ledger.clear()
            self._requests.clear()


distributed_lock_coordinator = DistributedLockCoordinator()
