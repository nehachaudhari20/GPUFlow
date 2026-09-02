from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from backend.app.models.workload import Workload, WorkloadStatus


class WorkloadRepository(ABC):
    @abstractmethod
    def insert(self, workload: Workload) -> Workload:
        pass

    @abstractmethod
    def get_by_id(self, job_id: str) -> Optional[Workload]:
        pass

    @abstractmethod
    def list_all(self, status: WorkloadStatus | None = None) -> List[Workload]:
        pass

    @abstractmethod
    def update(self, workload: Workload) -> Workload:
        pass

    @abstractmethod
    def delete_all(self) -> int:
        pass


class InMemoryWorkloadRepository(WorkloadRepository):
    def __init__(self):
        self._workloads: Dict[str, Workload] = {}

    def insert(self, workload: Workload) -> Workload:
        self._workloads[workload.job_id] = workload.model_copy(deep=True)
        return workload

    def get_by_id(self, job_id: str) -> Optional[Workload]:
        stored = self._workloads.get(job_id)
        return stored.model_copy(deep=True) if stored else None

    def list_all(self, status: WorkloadStatus | None = None) -> List[Workload]:
        workloads = [w.model_copy(deep=True) for w in self._workloads.values()]
        if status is not None:
            workloads = [w for w in workloads if w.status == status]
        return workloads

    def update(self, workload: Workload) -> Workload:
        if workload.job_id not in self._workloads:
            raise KeyError(f"Workload {workload.job_id} not found")
        self._workloads[workload.job_id] = workload.model_copy(deep=True)
        return workload

    def clear(self):
        self._workloads.clear()

    def delete_all(self) -> int:
        count = len(self._workloads)
        self._workloads.clear()
        return count
