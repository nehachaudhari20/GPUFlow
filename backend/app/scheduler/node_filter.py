from typing import List, Tuple

from backend.app.models.resources import NodeResources, ResourceRequirements


class NodeFilter:
    HEALTHY_STATUSES = {"ONLINE"}

    def evaluate(
        self, node: NodeResources, requirements: ResourceRequirements
    ) -> Tuple[bool, List[str]]:
        reasons: List[str] = []

        if node.status not in self.HEALTHY_STATUSES:
            reasons.append(f"Node is {node.status}, not ONLINE/HEALTHY")

        if requirements.gpu > node.gpu_available:
            reasons.append(
                f"Insufficient GPU (required {requirements.gpu}, available {node.gpu_available})"
            )

        if requirements.gpu_memory > node.gpu_memory_available:
            reasons.append(
                "Insufficient GPU memory "
                f"(required {requirements.gpu_memory}, available {node.gpu_memory_available})"
            )

        if requirements.cpu > node.cpu_available:
            reasons.append(
                f"Insufficient CPU (required {requirements.cpu}, available {node.cpu_available})"
            )

        if requirements.ram > node.ram_available:
            reasons.append(
                f"Insufficient RAM (required {requirements.ram}, available {node.ram_available})"
            )

        return len(reasons) == 0, reasons
