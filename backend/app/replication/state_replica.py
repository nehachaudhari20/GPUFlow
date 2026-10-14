from __future__ import annotations

from typing import Any, Dict

from backend.app.replication.replication_manager import replication_manager


def replicate_cluster_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return replication_manager.replicate({"type": "cluster_snapshot", "data": snapshot})
