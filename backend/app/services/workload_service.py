import threading
import time
from typing import Callable, List, Optional

from backend.app.models.workload import (
    Priority,
    PRIORITY_ORDER,
    Workload,
    WorkloadCreate,
    WorkloadStatus,
)
from backend.app.repositories.workload_repository import (
    InMemoryWorkloadRepository,
    WorkloadRepository,
)
from backend.app.events.event_manager import EventType
from backend.app.synchronization.event_sync import log_synchronized_event
from backend.app.config import settings
import logging

logger = logging.getLogger(__name__)

QueueSortKey = Callable[[Workload], tuple]


def default_queue_sort_key(workload: Workload) -> tuple:
    """Higher priority first, then FCFS by creation time."""
    return (PRIORITY_ORDER[workload.priority], workload.created_at)


class WorkloadQueue:
    def __init__(
        self,
        repository: WorkloadRepository,
        sort_key: QueueSortKey = default_queue_sort_key,
    ):
        self._repository = repository
        self._sort_key = sort_key
        self._lock = threading.Lock()

    def enqueue(self, payload: WorkloadCreate, job_id: str | None = None) -> Workload:
        workload = Workload.from_create(payload, job_id=job_id)
        workload.status = WorkloadStatus.QUEUED
        with self._lock:
            self._repository.insert(workload)
        logger.info(f"Enqueued workload {workload.job_id} with priority {workload.priority.name}")
        log_synchronized_event(
            EventType.JOB_SUBMITTED,
            source="USER",
            destination="SCHEDULER",
            job_id=workload.job_id,
            message=f"Job {workload.name} submitted",
            metadata={"priority": workload.priority.name, "type": workload.type.name},
        )
        log_synchronized_event(
            EventType.JOB_QUEUED,
            source="SCHEDULER",
            job_id=workload.job_id,
            message=f"Job {workload.job_id} placed in queue",
        )
        return workload

    def get_ordered_queue(self) -> List[Workload]:
        with self._lock:
            queued = self._repository.list_all(status=WorkloadStatus.QUEUED)
        return sorted(queued, key=self._sort_key)

    def peek_next(self) -> Optional[Workload]:
        ordered = self.get_ordered_queue()
        return ordered[0] if ordered else None


class WorkloadService:
    def __init__(self, repository: WorkloadRepository):
        self._repository = repository
        self.queue = WorkloadQueue(repository)
        self._lock = threading.Lock()

    def create_workload(self, payload: WorkloadCreate, job_id: str | None = None) -> Workload:
        return self.queue.enqueue(payload, job_id=job_id)

    def get_workload(self, job_id: str) -> Optional[Workload]:
        return self._repository.get_by_id(job_id)

    def list_workloads(self, status: WorkloadStatus | None = None) -> List[Workload]:
        return self._repository.list_all(status=status)

    def clear_all_workloads(self) -> int:
        with self._lock:
            return self._repository.delete_all()

    def update_status(
        self,
        job_id: str,
        status: WorkloadStatus,
        assigned_node: str | None = None,
    ) -> Workload:
        with self._lock:
            workload = self._repository.get_by_id(job_id)
            if workload is None:
                raise KeyError(f"Workload {job_id} not found")

            if not self._is_valid_transition(workload.status, status):
                raise ValueError(
                    f"Invalid status transition from {workload.status.value} to {status.value}"
                )

            workload.status = status
            if assigned_node is not None:
                workload.assigned_node = assigned_node
            if status == WorkloadStatus.RUNNING and workload.started_at is None:
                workload.started_at = time.time()
            workload.touch()
            updated = self._repository.update(workload)

            # Emit event for status updates
            event_map = {
                WorkloadStatus.SCHEDULED: EventType.TASK_ASSIGNED,
                WorkloadStatus.RUNNING: EventType.TASK_STARTED,
                WorkloadStatus.COMPLETED: EventType.TASK_COMPLETED,
                WorkloadStatus.FAILED: EventType.TASK_FAILED,
            }
            if status in event_map:
                log_synchronized_event(
                    event_map[status],
                    source="SCHEDULER",
                    job_id=job_id,
                    node_id=assigned_node or workload.assigned_node,
                    message=f"Job {job_id} state changed to {status.value}",
                )

            return updated

    @staticmethod
    def _is_valid_transition(current: WorkloadStatus, new: WorkloadStatus) -> bool:
        transitions = {
            WorkloadStatus.QUEUED: {
                WorkloadStatus.SCHEDULED,
                WorkloadStatus.CANCELLED,
                WorkloadStatus.FAILED,
            },
            WorkloadStatus.SCHEDULED: {
                WorkloadStatus.RUNNING,
                WorkloadStatus.CANCELLED,
                WorkloadStatus.FAILED,
            },
            WorkloadStatus.RUNNING: {
                WorkloadStatus.COMPLETED,
                WorkloadStatus.FAILED,
                WorkloadStatus.CANCELLED,
            },
            WorkloadStatus.COMPLETED: set(),
            WorkloadStatus.FAILED: set(),
            WorkloadStatus.CANCELLED: set(),
        }
        return new in transitions.get(current, set())


def create_workload_repository() -> WorkloadRepository:
    if settings.mongo_uri:
        from backend.app.repositories.mongo_workload_repository import (
            MongoWorkloadRepository,
        )

        logger.info("Using MongoDB workload repository")
        return MongoWorkloadRepository(settings.mongo_uri, database=settings.mongo_database)
    logger.info("MongoDB not configured; using in-memory workload repository")
    return InMemoryWorkloadRepository()


workload_service = WorkloadService(create_workload_repository())
