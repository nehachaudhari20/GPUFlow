from typing import List

from backend.app.models.resources import NodeResources
from backend.app.scheduler.scheduling_decision import ResourceScoreBreakdown
from backend.app.scheduler.scheduling_policy import SchedulingPolicy


def _normalize_ratio(available: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, available / total))


class NodeScorer:
    def __init__(self, policy: SchedulingPolicy):
        self.policy = policy

    def score(
        self, node: NodeResources, cluster_nodes: List[NodeResources]
    ) -> ResourceScoreBreakdown:
        gpu_ratio = _normalize_ratio(node.gpu_available, node.gpu_total)
        gpu_mem_ratio = _normalize_ratio(
            node.gpu_memory_available, node.gpu_memory_total
        )
        cpu_ratio = _normalize_ratio(node.cpu_available, node.cpu_total)
        ram_ratio = _normalize_ratio(node.ram_available, node.ram_total)

        gpu_component = (gpu_ratio + gpu_mem_ratio) / 2.0
        health_component = 1.0 if node.status == "ONLINE" else 0.0
        load_component = self._load_balance_score(node, cluster_nodes)

        weighted_total = (
            self.policy.gpu_weight * gpu_component
            + self.policy.cpu_weight * cpu_ratio
            + self.policy.ram_weight * ram_ratio
            + self.policy.health_weight * health_component
            + self.policy.load_balance_weight * load_component
        )

        return ResourceScoreBreakdown(
            gpu_availability=round(gpu_component * 100, 2),
            cpu_availability=round(cpu_ratio * 100, 2),
            ram_availability=round(ram_ratio * 100, 2),
            gpu_memory_availability=round(gpu_mem_ratio * 100, 2),
            health=round(health_component * 100, 2),
            load_balance=round(load_component * 100, 2),
            total=round(weighted_total * 100, 2),
        )

    @staticmethod
    def _load_balance_score(
        node: NodeResources, cluster_nodes: List[NodeResources]
    ) -> float:
        workload_counts = [len(n.running_workloads) for n in cluster_nodes]
        max_workloads = max(workload_counts) if workload_counts else 0
        if max_workloads == 0:
            return 1.0
        return 1.0 - (len(node.running_workloads) / max_workloads)
