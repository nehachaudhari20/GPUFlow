from enum import Enum
import time
import uuid

from pydantic import BaseModel, Field, model_validator


class WorkloadType(str, Enum):
    TRAINING = "TRAINING"
    INFERENCE = "INFERENCE"
    BATCH = "BATCH"
    PREPROCESSING = "PREPROCESSING"


class Priority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


PRIORITY_ORDER = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
}


class WorkloadStatus(str, Enum):
    QUEUED = "QUEUED"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkloadCreate(BaseModel):
    name: str = Field(min_length=1)
    type: WorkloadType
    gpu_required: float = Field(default=0, ge=0)
    gpu_memory_required: float = Field(default=0, ge=0)
    cpu_required: float = Field(default=0, ge=0)
    ram_required: float = Field(default=0, ge=0)
    priority: Priority = Priority.MEDIUM
    estimated_duration: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_at_least_one_resource(self):
        if (
            self.gpu_required == 0
            and self.gpu_memory_required == 0
            and self.cpu_required == 0
            and self.ram_required == 0
        ):
            raise ValueError("At least one resource requirement must be greater than zero")
        return self


class Workload(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: WorkloadType
    gpu_required: float = Field(ge=0)
    gpu_memory_required: float = Field(ge=0)
    cpu_required: float = Field(ge=0)
    ram_required: float = Field(ge=0)
    priority: Priority
    estimated_duration: float = Field(gt=0)
    status: WorkloadStatus = WorkloadStatus.QUEUED
    assigned_node: str | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    @classmethod
    def from_create(cls, payload: WorkloadCreate, job_id: str | None = None) -> "Workload":
        return cls(
            job_id=job_id or str(uuid.uuid4()),
            name=payload.name,
            type=payload.type,
            gpu_required=payload.gpu_required,
            gpu_memory_required=payload.gpu_memory_required,
            cpu_required=payload.cpu_required,
            ram_required=payload.ram_required,
            priority=payload.priority,
            estimated_duration=payload.estimated_duration,
        )

    def touch(self) -> None:
        self.updated_at = time.time()
