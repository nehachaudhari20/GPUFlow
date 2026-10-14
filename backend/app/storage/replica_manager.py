from __future__ import annotations

from typing import Any, Dict, List

from backend.app.storage.distributed_storage import distributed_storage


def replica_health(file_id: str) -> Dict[str, Any]:
    meta = distributed_storage.get_metadata(file_id)
    if meta is None:
        return {"file_id": file_id, "replicas": []}
    from backend.app.scheduler.cluster_state import cluster_state

    replicas = []
    for node_id in meta.replica_nodes:
        node = cluster_state.get_node(node_id)
        replicas.append(
            {
                "node_id": node_id,
                "online": node is not None and node.status == "ONLINE",
            }
        )
    return {"file_id": file_id, "replicas": replicas, "metadata": meta.__dict__}
