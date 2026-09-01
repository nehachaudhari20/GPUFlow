import threading
import time
from typing import Dict, List, Optional

from backend.app.models.worker import NodeFailureEvent, WorkerNode
from backend.app.config import settings
import logging

logger = logging.getLogger(__name__)


class ClusterState:
    def __init__(self):
        self.nodes: Dict[str, WorkerNode] = {}
        self.failure_events: List[NodeFailureEvent] = []
        self.lock = threading.Lock()

    def register_node(self, node: WorkerNode):
        with self.lock:
            self.nodes[node.node_id] = node
            logger.info(f"Registered node {node.node_id} ({node.hostname})")

    def update_heartbeat(
        self,
        node_id: str,
        status: str,
        timestamp: float,
        cpu_avail: float,
        ram_avail: float,
        gpu_avail: float,
        gpu_mem_avail: float,
    ):
        with self.lock:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                node.status = status
                node.last_heartbeat = timestamp
                node.cpu_available = cpu_avail
                node.ram_available = ram_avail
                node.gpu_available = gpu_avail
                node.gpu_memory_available = gpu_mem_avail
            else:
                logger.warning(f"Heartbeat received from unknown node {node_id}")

    def check_timeouts(self):
        with self.lock:
            current_time = time.time()
            for node_id, node in self.nodes.items():
                if node.status != "OFFLINE":
                    if current_time - node.last_heartbeat > settings.heartbeat_timeout:
                        node.status = "OFFLINE"
                        event = NodeFailureEvent(
                            node_id=node_id,
                            hostname=node.hostname,
                            timestamp=current_time,
                            reason="heartbeat_timeout",
                        )
                        self.failure_events.append(event)
                        logger.warning(
                            f"Node {node_id} missed heartbeat and marked OFFLINE"
                        )

    def get_node(self, node_id: str) -> Optional[WorkerNode]:
        with self.lock:
            return self.nodes.get(node_id)

    def get_all_nodes(self) -> List[WorkerNode]:
        with self.lock:
            return list(self.nodes.values())

    def get_online_nodes(self) -> List[WorkerNode]:
        with self.lock:
            return [node for node in self.nodes.values() if node.status == "ONLINE"]

    def is_schedulable(self, node_id: str) -> bool:
        with self.lock:
            node = self.nodes.get(node_id)
            return node is not None and node.status == "ONLINE"

    def get_failure_events(self) -> List[NodeFailureEvent]:
        with self.lock:
            return list(self.failure_events)


cluster_state = ClusterState()
