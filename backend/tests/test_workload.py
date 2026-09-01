import pytest
from pydantic import ValidationError

from backend.app.models.workload import (
    Priority,
    WorkloadCreate,
    WorkloadStatus,
    WorkloadType,
)
from backend.app.repositories.workload_repository import InMemoryWorkloadRepository
from backend.app.services.workload_service import WorkloadService


@pytest.fixture
def service():
    return WorkloadService(InMemoryWorkloadRepository())


def _payload(**overrides):
    base = {
        "name": "train-resnet",
        "type": WorkloadType.TRAINING,
        "gpu_required": 1,
        "gpu_memory_required": 8,
        "cpu_required": 4,
        "ram_required": 16,
        "priority": Priority.HIGH,
        "estimated_duration": 3600,
    }
    base.update(overrides)
    return WorkloadCreate(**base)


def test_valid_submission(service):
    workload = service.create_workload(_payload())
    assert workload.job_id
    assert workload.status == WorkloadStatus.QUEUED
    assert workload.assigned_node is None
    assert workload.type == WorkloadType.TRAINING


def test_invalid_resource_requirements_all_zero():
    with pytest.raises(ValidationError):
        WorkloadCreate(
            name="bad-job",
            type=WorkloadType.INFERENCE,
            estimated_duration=60,
        )


def test_invalid_resource_requirements_negative():
    with pytest.raises(ValidationError):
        WorkloadCreate(
            name="bad-job",
            type=WorkloadType.INFERENCE,
            cpu_required=-1,
            estimated_duration=60,
        )


def test_priority_ordering(service):
    service.create_workload(_payload(name="low-job", priority=Priority.LOW))
    service.create_workload(_payload(name="critical-job", priority=Priority.CRITICAL))
    service.create_workload(_payload(name="high-job", priority=Priority.HIGH))
    service.create_workload(_payload(name="medium-job", priority=Priority.MEDIUM))

    ordered = service.queue.get_ordered_queue()
    assert [w.name for w in ordered] == [
        "critical-job",
        "high-job",
        "medium-job",
        "low-job",
    ]


def test_fcfs_tie_breaking(service):
    first = service.create_workload(_payload(name="first", priority=Priority.MEDIUM))
    second = service.create_workload(_payload(name="second", priority=Priority.MEDIUM))

    first.created_at = 100.0
    second.created_at = 200.0
    service._repository.update(first)
    service._repository.update(second)

    ordered = service.queue.get_ordered_queue()
    assert [w.name for w in ordered] == ["first", "second"]


def test_status_update(service):
    workload = service.create_workload(_payload())
    updated = service.update_status(workload.job_id, WorkloadStatus.SCHEDULED)
    assert updated.status == WorkloadStatus.SCHEDULED
    assert updated.updated_at >= workload.updated_at


def test_status_update_with_assigned_node(service):
    workload = service.create_workload(_payload())
    service.update_status(workload.job_id, WorkloadStatus.SCHEDULED)
    running = service.update_status(
        workload.job_id,
        WorkloadStatus.RUNNING,
        assigned_node="node-1",
    )
    assert running.status == WorkloadStatus.RUNNING
    assert running.assigned_node == "node-1"


def test_invalid_status_transition(service):
    workload = service.create_workload(_payload())
    service.update_status(workload.job_id, WorkloadStatus.SCHEDULED)
    service.update_status(workload.job_id, WorkloadStatus.RUNNING)
    service.update_status(workload.job_id, WorkloadStatus.COMPLETED)
    with pytest.raises(ValueError, match="Invalid status transition"):
        service.update_status(workload.job_id, WorkloadStatus.QUEUED)


def test_get_workload(service):
    created = service.create_workload(_payload())
    fetched = service.get_workload(created.job_id)
    assert fetched is not None
    assert fetched.job_id == created.job_id


def test_list_workloads_by_status(service):
    queued = service.create_workload(_payload(name="queued-job"))
    done = service.create_workload(_payload(name="done-job"))
    service.update_status(done.job_id, WorkloadStatus.SCHEDULED)

    queued_only = service.list_workloads(status=WorkloadStatus.QUEUED)
    assert len(queued_only) == 1
    assert queued_only[0].job_id == queued.job_id


def test_peek_next_returns_highest_priority(service):
    service.create_workload(_payload(name="low", priority=Priority.LOW))
    service.create_workload(_payload(name="critical", priority=Priority.CRITICAL))

    nxt = service.queue.peek_next()
    assert nxt is not None
    assert nxt.name == "critical"
