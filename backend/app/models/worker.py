from pydantic import BaseModel, Field
from typing import List
import time


class WorkerNode(BaseModel):
    node_id: str
    hostname: str

    cpu_total: float
    cpu_available: float
    ram_total: float
    ram_available: float
    gpu_total: float
    gpu_available: float
    gpu_memory_total: float
    gpu_memory_available: float

    status: str = "ONLINE"
    last_heartbeat: float = Field(default_factory=time.time)
    current_workloads: List[str] = []


class NodeFailureEvent(BaseModel):
    node_id: str
    hostname: str
    timestamp: float = Field(default_factory=time.time)
    reason: str = "heartbeat_timeout"
