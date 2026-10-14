import threading
import time
from typing import Dict, List, Optional

from backend.app.models.worker import NodeFailureEvent, WorkerNode
from backend.app.config import settings
from backend.app.scheduler.resource_manager import resource_manager
from backend.app.events.event_manager import event_manager, EventType
from backend.app.synchronization.event_sync import (
    log_event_with_clocks,
    log_synchronized_event,
)
import logging

logger = logging.getLogger(__name__)


class ClusterState:
    def __init__(self):
        self.nodes: Dict[str, WorkerNode] = {}
        self.failure_events: List[NodeFailureEvent] = []
        self.lock = threading.Lock()

    def register_node(
        self,
        node: WorkerNode,
        lamport: Optional[int] = None,
        vector: Optional[Dict[str, int]] = None,
    ):
        with self.lock:
            self.nodes[node.node_id] = node
            logger.info(f"Registered node {node.node_id} ({node.hostname})")
        resource_manager.register_node(node)
        meta = {
            "cpu_total": node.cpu_total,
            "ram_total": node.ram_total,
            "gpu_total": node.gpu_total,
            "gpu_memory_total": node.gpu_memory_total,
            "grpc_port": node.grpc_port,
        }
        if lamport is not None and vector is not None:
            log_event_with_clocks(
                EventType.NODE_REGISTERED,
                lamport,
                vector,
                source="WORKER",
                destination="SCHEDULER",
                node_id=node.node_id,
                message=f"Node {node.node_id} ({node.hostname}) registered",
                metadata=meta,
            )
        else:
            log_synchronized_event(
                EventType.NODE_REGISTERED,
                source="WORKER",
                destination="SCHEDULER",
                node_id=node.node_id,
                message=f"Node {node.node_id} ({node.hostname}) registered",
                metadata=meta,
            )

    def update_heartbeat(
        self,
        node_id: str,
        status: str,
        timestamp: float,
        cpu_avail: float,
        ram_avail: float,
        gpu_avail: float,
        gpu_mem_avail: float,
        grpc_port: int = 0,
        lamport: Optional[int] = None,
        vector: Optional[Dict[str, int]] = None,
    ):
        with self.lock:
            if node_id not in self.nodes:
                logger.warning(f"Heartbeat received from unknown node {node_id}")
                return
            node = self.nodes[node_id]
            node.status = status
            node.last_heartbeat = timestamp
            if grpc_port > 0:
                node.grpc_port = grpc_port

        resource_manager.update_from_heartbeat(
            node_id, status, cpu_avail, ram_avail, gpu_avail, gpu_mem_avail
        )
        self.sync_node_resources(node_id)
        if lamport is not None and vector is not None:
            log_event_with_clocks(
                EventType.HEARTBEAT_RECEIVED,
                lamport,
                vector,
                source="WORKER",
                destination="SCHEDULER",
                node_id=node_id,
                message=f"Heartbeat received from {node_id}",
            )
        else:
            log_synchronized_event(
                EventType.HEARTBEAT_RECEIVED,
                source="WORKER",
                destination="SCHEDULER",
                node_id=node_id,
                message=f"Heartbeat received from {node_id}",
            )

    def check_timeouts(self):
        offline_ids: List[str] = []
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
                        offline_ids.append(node_id)
                        logger.warning(
                            f"Node {node_id} missed heartbeat and marked OFFLINE"
                        )
                        log_synchronized_event(
                            EventType.NODE_OFFLINE,
                            source="SCHEDULER",
                            node_id=node_id,
                            message=f"Node {node_id} missed heartbeat and marked OFFLINE",
                            metadata={"last_heartbeat": node.last_heartbeat},
                        )

        for node_id in offline_ids:
            resource_manager.mark_offline(node_id)
            try:
                from backend.app.recovery.recovery_manager import recovery_manager
                from backend.app.services.workload_service import workload_service
                from backend.app.scheduler.scheduler import scheduler

                recovery_manager.on_worker_failure(
                    node_id, workload_service, scheduler, self, resource_manager
                )
            except Exception as exc:
                logger.warning("Recovery hook failed for %s: %s", node_id, exc)

    def sync_node_resources(self, node_id: str):
        view = resource_manager.get_node_resources(node_id)
        if view is None:
            return
        with self.lock:
            if node_id not in self.nodes:
                return
            node = self.nodes[node_id]
            node.cpu_available = view.cpu_available
            node.ram_available = view.ram_available
            node.gpu_available = view.gpu_available
            node.gpu_memory_available = view.gpu_memory_available
            node.current_workloads = view.running_workloads

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

    def reset(self):
        with self.lock:
            self.nodes.clear()
            self.failure_events.clear()


cluster_state = ClusterState()
