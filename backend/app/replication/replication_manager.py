from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.app.events.event_manager import EventType
from backend.app.synchronization.event_sync import log_synchronized_event

logger = logging.getLogger(__name__)


class ReplicationManager:
    """Primary-writer versioned metadata log. Scheduler writes; workers are followers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sequence = 0
        self._replicas: Dict[str, Dict[str, Any]] = {
            "primary": {
                "status": "ACTIVE",
                "lag": 0,
                "role": "writer",
                "hostname": "scheduler",
                "last_sequence": 0,
            }
        }
        self._log: List[Dict[str, Any]] = []
        self._mongo = None
        self._init_mongo()
        self._hydrate()

    def register_replica(
        self, replica_id: str, hostname: str = "", role: str = "follower"
    ) -> None:
        with self._lock:
            existing = self._replicas.get(replica_id, {})
            self._replicas[replica_id] = {
                "status": existing.get("status", "ACTIVE"),
                "lag": existing.get("lag", 0),
                "role": role,
                "hostname": hostname or existing.get("hostname") or replica_id,
                "last_sequence": existing.get("last_sequence", 0),
            }

    def mark_replica_status(self, replica_id: str, status: str) -> None:
        with self._lock:
            if replica_id in self._replicas:
                self._replicas[replica_id]["status"] = status
                primary_seq = self._sequence
                last = int(self._replicas[replica_id].get("last_sequence") or 0)
                self._replicas[replica_id]["lag"] = max(0, primary_seq - last)

    def _init_mongo(self) -> None:
        try:
            from backend.app.config import settings

            if not settings.mongo_uri:
                return
            from pymongo import MongoClient

            client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=2000)
            db = client[settings.mongo_database]
            self._mongo = db["fa2_replication_log"]
            self._mongo.create_index("sequence", unique=True)
        except Exception as exc:
            logger.debug("Replication mongo unavailable: %s", exc)
            self._mongo = None

    def _hydrate(self) -> None:
        if self._mongo is None:
            return
        try:
            docs = list(self._mongo.find({}, {"_id": 0}).sort("sequence", 1))
            if not docs:
                return
            with self._lock:
                self._log = docs[-500:]
                self._sequence = int(docs[-1]["sequence"])
                for replica in self._replicas.values():
                    replica["last_sequence"] = self._sequence
                    replica["lag"] = 0
        except Exception as exc:
            logger.debug("Replication hydrate failed: %s", exc)

    def _follower_online(self, replica_id: str) -> bool:
        if replica_id == "primary":
            return True
        try:
            from backend.app.scheduler.cluster_state import cluster_state

            node = cluster_state.get_node(replica_id)
            return node is not None and node.status == "ONLINE"
        except Exception:
            return False

    def _online_ids(self) -> set[str]:
        ids = {"primary"}
        with self._lock:
            replica_ids = [k for k in self._replicas if k != "primary"]
        for replica_id in replica_ids:
            if self._follower_online(replica_id):
                ids.add(replica_id)
        return ids

    def replicate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        online = self._online_ids()
        with self._lock:
            self._sequence += 1
            record = {
                "sequence": self._sequence,
                "record_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "payload": payload,
            }
            self._log.append(record)
            if len(self._log) > 500:
                self._log = self._log[-500:]
            for replica_id, replica in self._replicas.items():
                if replica_id in online:
                    replica["last_sequence"] = self._sequence
                    replica["lag"] = 0
                    replica["status"] = "ACTIVE"
                else:
                    last = int(replica.get("last_sequence") or 0)
                    replica["lag"] = max(0, self._sequence - last)
                    replica["status"] = "STALE"
        if self._mongo is not None:
            try:
                self._mongo.insert_one({**record})
            except Exception as exc:
                logger.warning("Replication persist failed: %s", exc)
        log_synchronized_event(
            EventType.STATE_REPLICATED,
            message=f"Replicated sequence {record['sequence']}",
            metadata={"record_id": record["record_id"]},
        )
        return record

    def apply_if_newer(self, sequence: int, payload: Dict[str, Any]) -> bool:
        with self._lock:
            if sequence <= self._sequence:
                return False
            self._sequence = sequence
        self.replicate(payload)
        log_synchronized_event(EventType.REPLICA_SYNCED, message=f"Replica synced at {sequence}")
        return True

    def status(self) -> Dict[str, Any]:
        rows = self.list_replicas()
        return {
            "model": "primary-writer",
            "sequence": self._sequence,
            "replicas": rows,
            "persisted": self._mongo is not None,
        }

    def list_replicas(self) -> List[Dict[str, Any]]:
        online = self._online_ids()
        with self._lock:
            items = [(name, dict(v)) for name, v in self._replicas.items()]
            seq = self._sequence
        out = []
        for name, v in items:
            last = int(v.get("last_sequence") or 0)
            if name in online:
                last_shown = seq
                lag = 0
                status = "ACTIVE"
            else:
                last_shown = last
                lag = max(0, seq - last)
                status = "STALE"
            out.append(
                {
                    "name": v.get("hostname") or name,
                    "replica_id": name,
                    "role": v.get("role"),
                    "status": status,
                    "lag": lag,
                    "last_sequence": last_shown,
                }
            )
        return out

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = list(self._log[-limit:])
        if rows or self._mongo is None:
            return rows
        try:
            docs = list(self._mongo.find({}, {"_id": 0}).sort("sequence", -1).limit(limit))
            docs.reverse()
            return docs
        except Exception:
            return rows

    def clear(self) -> None:
        with self._lock:
            self._sequence = 0
            self._log.clear()
            for replica in self._replicas.values():
                replica["last_sequence"] = 0
                replica["lag"] = 0
                replica["status"] = "ACTIVE"


replication_manager = ReplicationManager()
