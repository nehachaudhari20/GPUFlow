from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from backend.app.coordination.distributed_lock import (
    RicartAgrawalaLockManager,
    distributed_lock_coordinator,
)
from backend.app.events.event_manager import EventType
from backend.app.synchronization.event_sync import log_synchronized_event


class SharedLamport:
    def __init__(self) -> None:
        self._t = 0
        self._lock = threading.Lock()

    def get(self) -> int:
        with self._lock:
            return self._t

    def tick(self) -> int:
        with self._lock:
            self._t += 1
            return self._t


class RicartAgrawalaDemo:
    """
    Live RA mutual-exclusion demo among currently registered workers.

    Each member gets a real RicartAgrawalaLockManager. REQUEST/REPLY are
    routed in-process so the dashboard can show (T, id) ordering, deferred
    replies, and a single critical-section owner.
    """

    RESOURCE = "cluster-cs"

    def __init__(self) -> None:
        self._clock = SharedLamport()
        self._managers: Dict[str, RicartAgrawalaLockManager] = {}
        self._labels: Dict[str, str] = {}
        self._trace: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def sync_members(self, members: List[Dict[str, Any]]) -> None:
        ids = {m["node_id"] for m in members}
        with self._lock:
            for m in members:
                nid = m["node_id"]
                self._labels[nid] = m.get("hostname") or nid
                if nid not in self._managers:
                    self._managers[nid] = RicartAgrawalaLockManager(
                        nid,
                        lamport_provider=self._clock.get,
                        lamport_tick=self._clock.tick,
                        send_reply=self._make_send_reply(nid),
                    )
            for stale in list(self._managers.keys()):
                if stale not in ids:
                    self._managers.pop(stale, None)
            live = set(self._managers.keys())
            for mgr in self._managers.values():
                mgr.set_membership(1, live)

    def _make_send_reply(self, sender_id: str):
        def send_reply(target: str, request_id: str, timestamp: int) -> None:
            self._append_trace(
                "REPLY",
                sender_id,
                target=target,
                request_id=request_id,
                timestamp=timestamp,
            )
            target_mgr = self._managers.get(target)
            if target_mgr is not None:
                target_mgr.on_reply(sender_id)

        return send_reply

    def _append_trace(self, kind: str, node_id: str, **extra: Any) -> None:
        rec = {
            "time": time.time(),
            "type": kind,
            "node_id": node_id,
            "hostname": self._labels.get(node_id, node_id),
            **extra,
        }
        self._trace.append(rec)
        if len(self._trace) > 80:
            self._trace = self._trace[-80:]

    def request(self, node_id: str) -> Dict[str, Any]:
        mgr = self._managers.get(node_id)
        if mgr is None:
            raise KeyError(f"Unknown member {node_id}")
        req = mgr.request_lock(self.RESOURCE)
        distributed_lock_coordinator.record_request(
            {
                "request_id": req.request_id,
                "resource_key": self.RESOURCE,
                "node_id": node_id,
                "lamport_timestamp": req.lamport_timestamp,
                "state": "PENDING",
            }
        )
        self._append_trace(
            "REQUEST",
            node_id,
            request_id=req.request_id,
            timestamp=req.lamport_timestamp,
        )
        log_synchronized_event(
            EventType.DISTRIBUTED_LOCK_REQUESTED,
            source=self._labels.get(node_id, node_id),
            node_id=node_id,
            message=(
                f"{self._labels.get(node_id, node_id)} REQUEST CS "
                f"(T={req.lamport_timestamp})"
            ),
            metadata={"lamport": req.lamport_timestamp},
        )
        for other_id, other in self._managers.items():
            if other_id == node_id:
                continue
            other.handle_remote_request(
                req.request_id, self.RESOURCE, node_id, req.lamport_timestamp
            )
        entered = self._try_all()
        return {
            "entered": entered,
            "lamport_timestamp": req.lamport_timestamp,
            **self.snapshot(),
        }

    def pulse(self, node_id: str, job_id: str) -> None:
        """Brief CS acquire/release when a real job is placed on this worker."""
        if node_id not in self._managers:
            return
        owner = None
        for nid, mgr in self._managers.items():
            if mgr.snapshot().get("in_critical_section"):
                owner = nid
                break
        if owner and owner != node_id:
            self._append_trace("REQUEST", node_id, job_id=job_id, note="deferred_cs_busy")
            return
        try:
            self.request(node_id)
            self._append_trace("JOB", node_id, job_id=job_id)
            self.release(node_id)
        except Exception:
            logger.debug("RA pulse skipped for %s", node_id, exc_info=True)

    def release(self, node_id: str) -> Dict[str, Any]:
        mgr = self._managers.get(node_id)
        if mgr is None:
            raise KeyError(f"Unknown member {node_id}")
        mgr.release_lock(self.RESOURCE)
        distributed_lock_coordinator.release_ledger(self.RESOURCE, node_id)
        self._append_trace("RELEASE", node_id)
        entered = self._try_all()
        return {"released": node_id, "entered": entered, **self.snapshot()}

    def _try_all(self) -> Optional[str]:
        for nid, mgr in self._managers.items():
            if mgr.try_enter_critical_section(self.RESOURCE):
                distributed_lock_coordinator.grant_ledger(self.RESOURCE, nid)
                self._append_trace("ENTER_CS", nid)
                log_synchronized_event(
                    EventType.DISTRIBUTED_LOCK_GRANTED,
                    source=self._labels.get(nid, nid),
                    node_id=nid,
                    message=f"{self._labels.get(nid, nid)} entered critical section",
                )
                return nid
        return None

    def snapshot(self) -> Dict[str, Any]:
        owner = None
        nodes = []
        for nid, mgr in self._managers.items():
            snap = mgr.snapshot()
            snap["hostname"] = self._labels.get(nid, nid)
            nodes.append(snap)
            if snap.get("in_critical_section"):
                owner = nid
        return {
            "algorithm": "Ricart-Agrawala",
            "resource": self.RESOURCE,
            "ordering": "(lamport_timestamp, node_id) smaller = higher priority",
            "owner": owner,
            "owner_hostname": self._labels.get(owner, owner) if owner else None,
            "clock": self._clock.get(),
            "nodes": nodes,
            "trace": list(self._trace[-40:]),
        }

    def clear(self) -> None:
        with self._lock:
            self._managers.clear()
            self._labels.clear()
            self._trace.clear()
            self._clock = SharedLamport()


ra_demo = RicartAgrawalaDemo()
