from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from backend.app.config import settings
from backend.app.events.event_manager import EventType
from backend.app.models.workload import WorkloadStatus
from backend.app.synchronization.event_sync import log_synchronized_event
from backend.app.recovery.retry_policy import RetryPolicy
from backend.app.recovery.migration_manager import MigrationManager

logger = logging.getLogger(__name__)


@dataclass
class ExecutionAttempt:
    attempt_id: str
    job_id: str
    attempt_number: int
    node_id: Optional[str]
    status: str
    failure_reason: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    coordinator_epoch: int = 1


class RecoveryManager:
    """
    At-least-once restart-based recovery integrated with heartbeat timeouts.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._attempts: Dict[str, ExecutionAttempt] = {}
        self._job_attempts: Dict[str, List[str]] = {}
        self._retry_meta: Dict[str, Dict[str, Any]] = {}
        self._policy = RetryPolicy()
        self._migrations = MigrationManager()
        self._history: List[Dict[str, Any]] = []
        self._epoch = 1
        self._processed_status: Dict[str, str] = {}

    def current_epoch(self) -> int:
        return self._epoch

    def begin_attempt(self, job_id: str, node_id: str) -> ExecutionAttempt:
        with self._lock:
            retry_count = len(self._job_attempts.get(job_id, []))
            attempt = ExecutionAttempt(
                attempt_id=str(uuid.uuid4()),
                job_id=job_id,
                attempt_number=retry_count + 1,
                node_id=node_id,
                status="RUNNING",
                coordinator_epoch=self._epoch,
            )
            self._attempts[attempt.attempt_id] = attempt
            self._job_attempts.setdefault(job_id, []).append(attempt.attempt_id)
            self._processed_status[job_id] = attempt.attempt_id
        return attempt

    def validate_status_update(self, job_id: str, attempt_id: str | None, status: str) -> bool:
        with self._lock:
            current = self._processed_status.get(job_id)
            if attempt_id and current and attempt_id != current:
                if status in ("COMPLETED", "FAILED"):
                    return False
            if attempt_id:
                self._processed_status[job_id] = attempt_id
            return True

    def on_worker_failure(
        self,
        node_id: str,
        workload_service,
        scheduler,
        cluster_state,
        resource_manager,
    ) -> List[str]:
        recovered: List[str] = []
        log_synchronized_event(
            EventType.WORKER_FAILURE_DETECTED,
            node_id=node_id,
            message=f"Worker failure detected for {node_id}",
        )
        running = workload_service.list_workloads(status=WorkloadStatus.RUNNING)
        for wl in running:
            if wl.assigned_node != node_id:
                continue
            recovered.append(wl.job_id)
            self._handle_interrupted(wl.job_id, node_id, workload_service, scheduler, resource_manager)
        return recovered

    def _handle_interrupted(
        self, job_id: str, node_id: str, workload_service, scheduler, resource_manager
    ) -> None:
        meta = self._retry_meta.setdefault(job_id, {"retry_count": 0})
        log_synchronized_event(
            EventType.TASK_INTERRUPTED,
            job_id=job_id,
            node_id=node_id,
            message=f"Task {job_id} interrupted on failed worker {node_id}",
        )
        decision = self._policy.evaluate(meta["retry_count"], "worker_failure")
        if not decision.should_retry:
            workload_service.update_status(job_id, WorkloadStatus.FAILED)
            log_synchronized_event(
                EventType.RETRY_EXHAUSTED,
                job_id=job_id,
                node_id=node_id,
                message=decision.reason,
            )
            self._record_history(job_id, "RETRY_EXHAUSTED", node_id, None, decision.reason)
            return

        meta["retry_count"] = decision.attempt_number
        meta["last_retry_timestamp"] = time.time()
        meta["retry_delay"] = decision.delay_s
        meta["previous_node_id"] = node_id
        meta["failure_reason"] = decision.reason

        wl = workload_service.get_workload(job_id)
        if wl:
            from backend.app.models.resources import ResourceRequirements

            reqs = ResourceRequirements(
                cpu=wl.cpu_required,
                ram=wl.ram_required,
                gpu=wl.gpu_required,
                gpu_memory=wl.gpu_memory_required,
            )
            resource_manager.release_resources(node_id, reqs, job_id)
            workload_service.update_status(job_id, WorkloadStatus.QUEUED)

        mig = self._migrations.record(
            job_id, node_id, None, "worker_failure_restart", decision.attempt_number
        )
        log_synchronized_event(
            EventType.TASK_RETRY_SCHEDULED,
            job_id=job_id,
            message=f"Retry #{decision.attempt_number} in {decision.delay_s:.1f}s",
            metadata={"migration_id": mig.migration_id},
        )
        self._record_history(job_id, "TASK_RETRY_SCHEDULED", node_id, None, decision.reason)

    def process_retry_queue(self, workload_service, scheduler) -> None:
        for job_id, meta in list(self._retry_meta.items()):
            if not RetryPolicy.ready(meta.get("last_retry_timestamp"), meta.get("retry_delay", 0)):
                continue
            wl = workload_service.get_workload(job_id)
            if wl is None or wl.status != WorkloadStatus.QUEUED:
                if wl is not None and wl.status != WorkloadStatus.QUEUED:
                    self._retry_meta.pop(job_id, None)
                continue
            decision = scheduler.schedule_and_update(workload_service, wl)
            if decision.allocation_success and decision.selected_node:
                self.begin_attempt(job_id, decision.selected_node)
                self._record_history(
                    job_id,
                    "TASK_REASSIGNED",
                    meta.get("previous_node_id", ""),
                    decision.selected_node,
                    "retry_dispatch",
                )
                self._retry_meta.pop(job_id, None)
                mig = self._migrations.record(
                    job_id,
                    meta.get("previous_node_id", ""),
                    decision.selected_node,
                    "retry_dispatch",
                    meta.get("retry_count", 1),
                    status="IN_PROGRESS",
                )
                log_synchronized_event(
                    EventType.TASK_REASSIGNED,
                    job_id=job_id,
                    node_id=decision.selected_node,
                    message=f"Job reassigned to {decision.selected_node}",
                    metadata={"migration_id": mig.migration_id},
                )
                log_synchronized_event(
                    EventType.TASK_RECOVERED,
                    job_id=job_id,
                    node_id=decision.selected_node,
                    message="Recovery attempt dispatched",
                )

    def _record_history(
        self, job_id: str, event: str, old_node: str, new_node: Optional[str], reason: str
    ) -> None:
        with self._lock:
            self._history.append(
                {
                    "timestamp": time.time(),
                    "job_id": job_id,
                    "event": event,
                    "old_node_id": old_node,
                    "new_node_id": new_node,
                    "reason": reason,
                }
            )

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "epoch": self._epoch,
                "tracked_jobs": len(self._job_attempts),
                "pending_retries": len(self._retry_meta),
                "max_attempts": settings.recovery_max_attempts,
            }

    def job_detail(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            attempt_ids = self._job_attempts.get(job_id, [])
            attempts = [self._attempts[aid].__dict__ for aid in attempt_ids if aid in self._attempts]
            return {
                "job_id": job_id,
                "retry_meta": self._retry_meta.get(job_id),
                "attempts": attempts,
                "migrations": [
                    m for m in self._migrations.list_history(200) if m["job_id"] == job_id
                ],
            }

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history[-limit:])

    def clear(self) -> None:
        with self._lock:
            self._attempts.clear()
            self._job_attempts.clear()
            self._retry_meta.clear()
            self._history.clear()
        self._migrations.clear()


recovery_manager = RecoveryManager()
