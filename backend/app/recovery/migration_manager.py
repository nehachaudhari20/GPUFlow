from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MigrationRecord:
    migration_id: str
    job_id: str
    old_node_id: str
    new_node_id: Optional[str]
    migration_reason: str
    attempt_number: int
    migration_status: str
    migration_timestamp: float = field(default_factory=time.time)


class MigrationManager:
    """Restart-based migration (not live process migration)."""

    def __init__(self) -> None:
        self._history: List[MigrationRecord] = []

    def record(
        self,
        job_id: str,
        old_node_id: str,
        new_node_id: Optional[str],
        reason: str,
        attempt_number: int,
        status: str = "SCHEDULED",
    ) -> MigrationRecord:
        rec = MigrationRecord(
            migration_id=str(uuid.uuid4()),
            job_id=job_id,
            old_node_id=old_node_id,
            new_node_id=new_node_id,
            migration_reason=reason,
            attempt_number=attempt_number,
            migration_status=status,
        )
        self._history.append(rec)
        return rec

    def list_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [
            {
                "migration_id": m.migration_id,
                "job_id": m.job_id,
                "old_node_id": m.old_node_id,
                "new_node_id": m.new_node_id,
                "migration_reason": m.migration_reason,
                "attempt_number": m.attempt_number,
                "migration_status": m.migration_status,
                "migration_timestamp": m.migration_timestamp,
            }
            for m in self._history[-limit:]
        ]

    def clear(self) -> None:
        self._history.clear()
