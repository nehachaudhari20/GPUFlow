import pytest

from backend.app.models.resources import ResourceRequirements
from backend.app.models.worker import WorkerNode
from backend.app.models.workload import (
    Priority,
    WorkloadCreate,
    WorkloadStatus,
    WorkloadType,
)
from backend.app.repositories.workload_repository import InMemoryWorkloadRepository
from backend.app.scheduler.cluster_state import ClusterState
from backend.app.scheduler.resource_manager import ResourceManager
from backend.app.scheduler.scheduler import Scheduler
from backend.app.scheduler.scheduling_policy import SchedulingPolicy
from backend.app.services.workload_service import WorkloadService


@pytest.fixture
def cluster():
    return ClusterState()


@pytest.fixture
def resources():
    return ResourceManager()


@pytest.fixture
def scheduler(cluster, resources):
    return Scheduler(resources, cluster)


@pytest.fixture
def workload_service():
    return WorkloadService(InMemoryWorkloadRepository())


def _register(
    cluster: ClusterState,
    resources: ResourceManager,
    node_id: str,
    cpu_total=8,
    cpu_avail=8,
    ram_total=32,
    ram_avail=32,
    gpu_total=2,
    gpu_avail=2,
    gpu_mem_total=32,
    gpu_mem_avail=32,
    status="ONLINE",
):
    node = WorkerNode(
        node_id=node_id,
        hostname=f"host-{node_id}",
        cpu_total=cpu_total,
        cpu_available=cpu_avail,
        ram_total=ram_total,
        ram_available=ram_avail,
        gpu_total=gpu_total,
        gpu_available=gpu_avail,
        gpu_memory_total=gpu_mem_total,
        gpu_memory_available=gpu_mem_avail,
        status=status,
    )
    resources.register_node(node)
    with cluster.lock:
        cluster.nodes[node_id] = node


def _workload(**overrides):
    base = {
        "name": "test-job",
        "type": WorkloadType.TRAINING,
        "gpu_required": 1,
        "gpu_memory_required": 8,
        "cpu_required": 4,
        "ram_required": 16,
        "priority": Priority.MEDIUM,
        "estimated_duration": 3600,
    }
    base.update(overrides)
    return WorkloadCreate(**base)


def test_no_eligible_nodes(scheduler, cluster, resources, workload_service):
    _register(cluster, resources, "NODE-01", gpu_avail=0, gpu_total=2)
    workload = workload_service.create_workload(
        _workload(name="JOB-101", gpu_required=1), job_id="JOB-101"
    )

    decision = scheduler.schedule_and_update(workload_service, workload)

    assert decision.kept_queued is True
    assert decision.selected_node is None
    assert len(decision.rejected_nodes) == 1
    assert "Insufficient GPU" in decision.rejected_nodes[0].reasons[0]
    assert workload_service.get_workload("JOB-101").status == WorkloadStatus.QUEUED


def test_one_eligible_node(scheduler, cluster, resources, workload_service):
    _register(cluster, resources, "NODE-01")
    workload = workload_service.create_workload(_workload(name="JOB-102"), job_id="JOB-102")

    decision = scheduler.schedule_and_update(workload_service, workload)

    assert decision.allocation_success is True
    assert decision.selected_node == "NODE-01"
    assert len(decision.candidate_nodes) == 1
    assert workload_service.get_workload("JOB-102").status == WorkloadStatus.RUNNING


def test_multiple_eligible_nodes_picks_highest_score(
    scheduler, cluster, resources, workload_service
):
    _register(
        cluster,
        resources,
        "NODE-01",
        gpu_avail=1,
        gpu_total=4,
        cpu_avail=4,
        cpu_total=8,
    )
    _register(
        cluster,
        resources,
        "NODE-02",
        gpu_avail=3,
        gpu_total=4,
        cpu_avail=6,
        cpu_total=8,
    )
    _register(
        cluster,
        resources,
        "NODE-03",
        gpu_avail=4,
        gpu_total=4,
        cpu_avail=8,
        cpu_total=8,
        ram_avail=32,
    )

    workload = workload_service.create_workload(_workload(name="JOB-101"), job_id="JOB-101")
    decision = scheduler.schedule_workload(workload)

    assert decision.selected_node == "NODE-03"
    assert decision.candidate_nodes[0].node_id == "NODE-03"
    assert decision.candidate_nodes[0].scores.total > decision.candidate_nodes[1].scores.total
    assert len(decision.candidate_nodes) == 3


def test_gpu_heavy_workload(scheduler, cluster, resources, workload_service):
    _register(cluster, resources, "NODE-GPU-LIGHT", gpu_avail=1, gpu_total=4)
    _register(cluster, resources, "NODE-GPU-HEAVY", gpu_avail=4, gpu_total=4)

    workload = workload_service.create_workload(
        _workload(name="gpu-job", gpu_required=2, gpu_memory_required=16),
        job_id="gpu-job",
    )
    decision = scheduler.schedule_workload(workload)

    assert decision.selected_node == "NODE-GPU-HEAVY"


def test_cpu_heavy_workload(scheduler, cluster, resources, workload_service):
    _register(cluster, resources, "NODE-CPU-LIGHT", cpu_avail=2, cpu_total=16)
    _register(cluster, resources, "NODE-CPU-HEAVY", cpu_avail=14, cpu_total=16)

    workload = workload_service.create_workload(
        _workload(name="cpu-job", gpu_required=0, cpu_required=8, ram_required=8),
        job_id="cpu-job",
    )
    decision = scheduler.schedule_workload(workload)

    assert decision.selected_node == "NODE-CPU-HEAVY"


def test_memory_heavy_workload(scheduler, cluster, resources, workload_service):
    _register(cluster, resources, "NODE-RAM-LIGHT", ram_avail=8, ram_total=64)
    _register(cluster, resources, "NODE-RAM-HEAVY", ram_avail=56, ram_total=64)

    workload = workload_service.create_workload(
        _workload(name="mem-job", gpu_required=0, ram_required=32, cpu_required=2),
        job_id="mem-job",
    )
    decision = scheduler.schedule_workload(workload)

    assert decision.selected_node == "NODE-RAM-HEAVY"


def test_priority_interaction(scheduler, cluster, resources, workload_service):
    _register(cluster, resources, "NODE-01")
    workload_service.create_workload(
        _workload(name="low-priority", priority=Priority.LOW), job_id="low"
    )
    workload_service.create_workload(
        _workload(name="critical-priority", priority=Priority.CRITICAL), job_id="critical"
    )

    decision = scheduler.schedule_next(workload_service)

    assert decision is not None
    assert decision.job_id == "critical"
    assert decision.allocation_success is True


def test_resource_fragmentation(scheduler, cluster, resources, workload_service):
    _register(
        cluster,
        resources,
        "NODE-GPU-ONLY",
        gpu_avail=2,
        gpu_total=2,
        cpu_avail=1,
        cpu_total=8,
    )
    _register(
        cluster,
        resources,
        "NODE-BALANCED",
        gpu_avail=1,
        gpu_total=2,
        cpu_avail=8,
        cpu_total=8,
    )

    workload = workload_service.create_workload(
        _workload(name="frag-job", gpu_required=1, cpu_required=4),
        job_id="frag-job",
    )
    decision = scheduler.schedule_workload(workload)

    rejected_gpu_only = next(
        r for r in decision.rejected_nodes if r.node_id == "NODE-GPU-ONLY"
    )
    assert any("Insufficient CPU" in reason for reason in rejected_gpu_only.reasons)
    assert decision.selected_node == "NODE-BALANCED"


def test_offline_node(scheduler, cluster, resources, workload_service):
    _register(cluster, resources, "NODE-OFFLINE", status="OFFLINE")
    _register(cluster, resources, "NODE-ONLINE")

    workload = workload_service.create_workload(_workload(name="offline-test"), job_id="off")
    decision = scheduler.schedule_workload(workload)

    offline_rejection = next(
        r for r in decision.rejected_nodes if r.node_id == "NODE-OFFLINE"
    )
    assert any("OFFLINE" in reason for reason in offline_rejection.reasons)
    assert decision.selected_node == "NODE-ONLINE"


def test_allocation_failure(scheduler, cluster, resources, workload_service, monkeypatch):
    _register(cluster, resources, "NODE-01")

    workload = workload_service.create_workload(_workload(name="fail-alloc"), job_id="fail-alloc")

    def fail_allocate(node_id, requirements, job_id):
        return False

    monkeypatch.setattr(resources, "allocate_resources", fail_allocate)

    decision = scheduler.schedule_workload(workload)

    assert decision.selected_node == "NODE-01"
    assert decision.allocation_success is False
    assert decision.kept_queued is True
    assert "allocation failed" in decision.reason.lower()


def test_scheduling_decision_summary(scheduler, cluster, resources, workload_service):
    _register(cluster, resources, "NODE-01", gpu_avail=0, gpu_total=2)
    _register(cluster, resources, "NODE-02", gpu_avail=2, gpu_total=2)
    _register(cluster, resources, "NODE-03", gpu_avail=2, gpu_total=2, cpu_avail=8)

    workload = workload_service.create_workload(
        _workload(name="JOB-101", gpu_required=1), job_id="JOB-101"
    )
    decision = scheduler.schedule_workload(workload)
    summary = decision.summary()

    assert "JOB-101" in summary
    assert "NODE-01" in summary
    assert "Rejected" in summary
    assert "NODE-03" in summary
    assert "Selected" in summary


def test_does_not_pick_first_available_node(scheduler, cluster, resources, workload_service):
    _register(cluster, resources, "NODE-FIRST", gpu_avail=1, gpu_total=4)
    _register(cluster, resources, "NODE-BEST", gpu_avail=4, gpu_total=4)

    workload = workload_service.create_workload(_workload(name="score-test"), job_id="score-test")
    decision = scheduler.schedule_workload(workload)

    assert decision.selected_node == "NODE-BEST"
    assert decision.selected_node != "NODE-FIRST"


def test_schedule_all_stops_on_blocked_job(scheduler, cluster, resources, workload_service):
    _register(cluster, resources, "NODE-01", gpu_avail=0, gpu_total=1)
    workload_service.create_workload(
        _workload(name="blocked", gpu_required=1), job_id="blocked"
    )
    workload_service.create_workload(
        _workload(name="waiting", gpu_required=0, cpu_required=1), job_id="waiting"
    )

    decisions = scheduler.schedule_all_queued(workload_service)

    assert len(decisions) == 1
    assert decisions[0].kept_queued is True


def test_configurable_scoring_weights():
    policy = SchedulingPolicy(
        gpu_weight=0.60,
        cpu_weight=0.20,
        ram_weight=0.10,
        health_weight=0.05,
        load_balance_weight=0.05,
    )
    assert policy.gpu_weight == 0.60

    with pytest.raises(ValueError):
        SchedulingPolicy(
            gpu_weight=0.5,
            cpu_weight=0.5,
            ram_weight=0.5,
            health_weight=0.0,
            load_balance_weight=0.0,
        )
