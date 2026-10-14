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
    """Primary-writer versioned metadata replication (Mongo when configured)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sequence = 0
        self._replicas: Dict[str, Dict[str, Any]] = {"primary": {"status": "ACTIVE", "lag": 0}}
        self._log: List[Dict[str, Any]] = []
        self._mongo = None
        self._init_mongo()

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

    def replicate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
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
        if self._mongo is not None:
            try:
                self._mongo.insert_one(record)
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
        with self._lock:
            return {
                "model": "primary-writer",
                "sequence": self._sequence,
                "replicas": list(self._replicas.values()),
                "persisted": self._mongo is not None,
            }

    def list_replicas(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [{"name": k, **v} for k, v in self._replicas.items()]

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._log[-limit:])

    def clear(self) -> None:
        with self._lock:
            self._sequence = 0
            self._log.clear()


replication_manager = ReplicationManager()
