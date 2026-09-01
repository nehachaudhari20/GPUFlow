from pydantic import BaseModel, Field
from typing import List


class ResourceRequirements(BaseModel):
    cpu: float = Field(default=0, ge=0)
    ram: float = Field(default=0, ge=0)
    gpu: float = Field(default=0, ge=0)
    gpu_memory: float = Field(default=0, ge=0)


class NodeResources(BaseModel):
    node_id: str
    hostname: str
    status: str

    cpu_total: float
    cpu_available: float
    cpu_utilization: float

    ram_total: float
    ram_available: float
    ram_utilization: float

    gpu_total: float
    gpu_available: float
    gpu_utilization: float

    gpu_memory_total: float
    gpu_memory_available: float
    gpu_memory_utilization: float

    running_workloads: List[str]


class ClusterResources(BaseModel):
    cpu_total: float
    cpu_available: float
    cpu_utilization: float

    ram_total: float
    ram_available: float
    ram_utilization: float

    gpu_total: float
    gpu_available: float
    gpu_utilization: float

    gpu_memory_total: float
    gpu_memory_available: float
    gpu_memory_utilization: float

    online_nodes: int
    offline_nodes: int
    total_workloads: int
    nodes: List[NodeResources]
