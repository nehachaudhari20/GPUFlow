import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.app.models.resources import (
    ClusterResources,
    NodeResources,
    ResourceRequirements,
)
from backend.app.models.worker import WorkerNode
from backend.app.events.event_manager import event_manager, EventType
import logging

logger = logging.getLogger(__name__)


@dataclass
class _NodeResourceState:
    node_id: str
    hostname: str
    status: str = "ONLINE"

    cpu_total: float = 0.0
    ram_total: float = 0.0
    gpu_total: float = 0.0
    gpu_memory_total: float = 0.0

    reported_cpu_available: float = 0.0
    reported_ram_available: float = 0.0
    reported_gpu_available: float = 0.0
    reported_gpu_memory_available: float = 0.0

    allocated_cpu: float = 0.0
    allocated_ram: float = 0.0
    allocated_gpu: float = 0.0
    allocated_gpu_memory: float = 0.0

    allocations: Dict[str, ResourceRequirements] = field(default_factory=dict)

    def _utilization(self, total: float, available: float) -> float:
        if total <= 0:
            return 0.0
        used = max(0.0, total - available)
        return min(1.0, used / total)

    def _schedulable_available(
        self, total: float, reported: float, allocated: float
    ) -> float:
        logical = max(0.0, total - allocated)
        return max(0.0, min(reported, logical))

    @property
    def cpu_available(self) -> float:
        return self._schedulable_available(
            self.cpu_total, self.reported_cpu_available, self.allocated_cpu
        )

    @property
    def ram_available(self) -> float:
        return self._schedulable_available(
            self.ram_total, self.reported_ram_available, self.allocated_ram
        )

    @property
    def gpu_available(self) -> float:
        return self._schedulable_available(
            self.gpu_total, self.reported_gpu_available, self.allocated_gpu
        )

    @property
    def gpu_memory_available(self) -> float:
        return self._schedulable_available(
            self.gpu_memory_total,
            self.reported_gpu_memory_available,
            self.allocated_gpu_memory,
        )

    def to_view(self) -> NodeResources:
        return NodeResources(
            node_id=self.node_id,
            hostname=self.hostname,
            status=self.status,
            cpu_total=self.cpu_total,
            cpu_available=self.cpu_available,
            cpu_utilization=self._utilization(self.cpu_total, self.cpu_available),
            ram_total=self.ram_total,
            ram_available=self.ram_available,
            ram_utilization=self._utilization(self.ram_total, self.ram_available),
            gpu_total=self.gpu_total,
            gpu_available=self.gpu_available,
            gpu_utilization=self._utilization(self.gpu_total, self.gpu_available),
            gpu_memory_total=self.gpu_memory_total,
            gpu_memory_available=self.gpu_memory_available,
            gpu_memory_utilization=self._utilization(
                self.gpu_memory_total, self.gpu_memory_available
            ),
            running_workloads=list(self.allocations.keys()),
        )


class ResourceManager:
    def __init__(self):
        self._nodes: Dict[str, _NodeResourceState] = {}
        self._lock = threading.Lock()

    def register_node(self, node: WorkerNode):
        with self._lock:
            state = _NodeResourceState(
                node_id=node.node_id,
                hostname=node.hostname,
                status=node.status,
                cpu_total=node.cpu_total,
                ram_total=node.ram_total,
                gpu_total=node.gpu_total,
                gpu_memory_total=node.gpu_memory_total,
                reported_cpu_available=node.cpu_available,
                reported_ram_available=node.ram_available,
                reported_gpu_available=node.gpu_available,
                reported_gpu_memory_available=node.gpu_memory_available,
            )
            self._nodes[node.node_id] = state
            logger.info(f"Resource state initialized for node {node.node_id}")

    def update_from_heartbeat(
        self,
        node_id: str,
        status: str,
        cpu_avail: float,
        ram_avail: float,
        gpu_avail: float,
        gpu_mem_avail: float,
    ):
        with self._lock:
            state = self._nodes.get(node_id)
            if state is None:
                logger.warning(f"Heartbeat for unknown node {node_id} in ResourceManager")
                return

            state.status = status
            state.reported_cpu_available = max(0.0, cpu_avail)
            state.reported_ram_available = max(0.0, ram_avail)
            state.reported_gpu_available = max(0.0, gpu_avail)
            state.reported_gpu_memory_available = max(0.0, gpu_mem_avail)

    def mark_offline(self, node_id: str):
        with self._lock:
            state = self._nodes.get(node_id)
            if state is not None:
                state.status = "OFFLINE"

    def get_node_resources(self, node_id: str) -> Optional[NodeResources]:
        with self._lock:
            state = self._nodes.get(node_id)
            if state is None:
                return None
            return state.to_view()

    def get_cluster_resources(self) -> ClusterResources:
        with self._lock:
            node_views = [state.to_view() for state in self._nodes.values()]

        cpu_total = sum(n.cpu_total for n in node_views)
        cpu_available = sum(n.cpu_available for n in node_views)
        ram_total = sum(n.ram_total for n in node_views)
        ram_available = sum(n.ram_available for n in node_views)
        gpu_total = sum(n.gpu_total for n in node_views)
        gpu_available = sum(n.gpu_available for n in node_views)
        gpu_mem_total = sum(n.gpu_memory_total for n in node_views)
        gpu_mem_available = sum(n.gpu_memory_available for n in node_views)

        def cluster_util(total: float, available: float) -> float:
            if total <= 0:
                return 0.0
            return min(1.0, max(0.0, total - available) / total)

        online = sum(1 for n in node_views if n.status == "ONLINE")
        offline = len(node_views) - online
        workloads = sum(len(n.running_workloads) for n in node_views)

        return ClusterResources(
            cpu_total=cpu_total,
            cpu_available=cpu_available,
            cpu_utilization=cluster_util(cpu_total, cpu_available),
            ram_total=ram_total,
            ram_available=ram_available,
            ram_utilization=cluster_util(ram_total, ram_available),
            gpu_total=gpu_total,
            gpu_available=gpu_available,
            gpu_utilization=cluster_util(gpu_total, gpu_available),
            gpu_memory_total=gpu_mem_total,
            gpu_memory_available=gpu_mem_available,
            gpu_memory_utilization=cluster_util(gpu_mem_total, gpu_mem_available),
            online_nodes=online,
            offline_nodes=offline,
            total_workloads=workloads,
            nodes=node_views,
        )

    def can_allocate(self, node_id: str, requirements: ResourceRequirements) -> bool:
        with self._lock:
            return self._can_allocate_locked(node_id, requirements)

    def allocate_resources(
        self, node_id: str, requirements: ResourceRequirements, job_id: str
    ) -> bool:
        with self._lock:
            if not self._can_allocate_locked(node_id, requirements, job_id):
                return False

            state = self._nodes[node_id]
            state.allocated_cpu += requirements.cpu
            state.allocated_ram += requirements.ram
            state.allocated_gpu += requirements.gpu
            state.allocated_gpu_memory += requirements.gpu_memory
            state.allocations[job_id] = requirements.model_copy()
            logger.info(f"Allocated resources on {node_id} for job {job_id}")
            return True

    def release_resources(
        self, node_id: str, requirements: ResourceRequirements, job_id: str
    ) -> bool:
        with self._lock:
            state = self._nodes.get(node_id)
            if state is None:
                logger.warning(f"Release requested for unknown node {node_id}")
                return False

            if job_id not in state.allocations:
                logger.warning(
                    f"Release requested for unknown job {job_id} on node {node_id}"
                )
                return False

            stored = state.allocations.pop(job_id)
            state.allocated_cpu = max(0.0, state.allocated_cpu - stored.cpu)
            state.allocated_ram = max(0.0, state.allocated_ram - stored.ram)
            state.allocated_gpu = max(0.0, state.allocated_gpu - stored.gpu)
            state.allocated_gpu_memory = max(
                0.0, state.allocated_gpu_memory - stored.gpu_memory
            )
            logger.info(f"Released resources on {node_id} for job {job_id}")

            event_manager.log_event(
                event_type=EventType.RESOURCE_RELEASED,
                source="SCHEDULER",
                job_id=job_id,
                node_id=node_id,
                message=f"Resources released for completed/failed job {job_id}",
            )

            return True

    def _can_allocate_locked(
        self,
        node_id: str,
        requirements: ResourceRequirements,
        job_id: str | None = None,
    ) -> bool:
        if requirements.cpu < 0 or requirements.ram < 0:
            return False
        if requirements.gpu < 0 or requirements.gpu_memory < 0:
            return False

        state = self._nodes.get(node_id)
        if state is None or state.status != "ONLINE":
            return False

        if job_id is not None and job_id in state.allocations:
            return False

        return (
            requirements.cpu <= state.cpu_available
            and requirements.ram <= state.ram_available
            and requirements.gpu <= state.gpu_available
            and requirements.gpu_memory <= state.gpu_memory_available
        )


resource_manager = ResourceManager()
