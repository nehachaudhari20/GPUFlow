import threading
import time

import pytest

from backend.app.models.resources import ResourceRequirements
from backend.app.models.worker import WorkerNode
from backend.app.scheduler.resource_manager import ResourceManager


def _make_node(node_id="node-1", cpu=8, ram=16, gpu=1, gpu_mem=16):
    return WorkerNode(
        node_id=node_id,
        hostname="host-1",
        cpu_total=cpu,
        cpu_available=cpu,
        ram_total=ram,
        ram_available=ram,
        gpu_total=gpu,
        gpu_available=gpu,
        gpu_memory_total=gpu_mem,
        gpu_memory_available=gpu_mem,
    )


def _req(cpu=0, ram=0, gpu=0, gpu_memory=0):
    return ResourceRequirements(
        cpu=cpu, ram=ram, gpu=gpu, gpu_memory=gpu_memory
    )


@pytest.fixture
def rm():
    return ResourceManager()


def test_sufficient_resources(rm):
    rm.register_node(_make_node())
    req = _req(cpu=4, ram=8, gpu=1, gpu_memory=8)
    assert rm.can_allocate("node-1", req) is True


def test_insufficient_resources(rm):
    rm.register_node(_make_node())
    req = _req(cpu=16, ram=8)
    assert rm.can_allocate("node-1", req) is False


def test_allocation(rm):
    rm.register_node(_make_node())
    req = _req(cpu=2, ram=4, gpu=1, gpu_memory=4)

    assert rm.allocate_resources("node-1", req, "job-1") is True

    view = rm.get_node_resources("node-1")
    assert view.cpu_available == 6
    assert view.ram_available == 12
    assert view.gpu_available == 0
    assert view.gpu_memory_available == 12
    assert view.running_workloads == ["job-1"]


def test_release(rm):
    rm.register_node(_make_node())
    req = _req(cpu=2, ram=4)

    rm.allocate_resources("node-1", req, "job-1")
    assert rm.release_resources("node-1", req, "job-1") is True

    view = rm.get_node_resources("node-1")
    assert view.cpu_available == 8
    assert view.ram_available == 16
    assert view.running_workloads == []


def test_multiple_jobs(rm):
    rm.register_node(_make_node())
    assert rm.allocate_resources("node-1", _req(cpu=2, ram=4), "job-1") is True
    assert rm.allocate_resources("node-1", _req(cpu=2, ram=4), "job-2") is True
    assert rm.allocate_resources("node-1", _req(cpu=2, ram=4), "job-3") is True
    assert rm.allocate_resources("node-1", _req(cpu=2, ram=4), "job-4") is True
    assert rm.can_allocate("node-1", _req(cpu=1)) is False

    view = rm.get_node_resources("node-1")
    assert len(view.running_workloads) == 4
    assert view.cpu_available == 0


def test_invalid_allocation_unknown_node(rm):
    assert rm.allocate_resources("missing", _req(cpu=1), "job-1") is False


def test_invalid_allocation_duplicate_job(rm):
    rm.register_node(_make_node())
    req = _req(cpu=2)
    assert rm.allocate_resources("node-1", req, "job-1") is True
    assert rm.allocate_resources("node-1", req, "job-1") is False


def test_invalid_allocation_negative_requirements(rm):
    rm.register_node(_make_node())
    with pytest.raises(Exception):
        ResourceRequirements(cpu=-1)


def test_offline_node(rm):
    rm.register_node(_make_node())
    rm.mark_offline("node-1")
    assert rm.can_allocate("node-1", _req(cpu=1)) is False
    assert rm.allocate_resources("node-1", _req(cpu=1), "job-1") is False


def test_release_unknown_job(rm):
    rm.register_node(_make_node())
    assert rm.release_resources("node-1", _req(cpu=1), "missing-job") is False


def test_no_negative_available_after_over_release(rm):
    rm.register_node(_make_node())
    req = _req(cpu=2, ram=4)
    rm.allocate_resources("node-1", req, "job-1")
    rm.release_resources("node-1", req, "job-1")
    rm.release_resources("node-1", req, "job-1")

    view = rm.get_node_resources("node-1")
    assert view.cpu_available >= 0
    assert view.ram_available >= 0


def test_heartbeat_updates_reported_available(rm):
    rm.register_node(_make_node())
    rm.allocate_resources("node-1", _req(cpu=2, ram=4), "job-1")

    rm.update_from_heartbeat("node-1", "ONLINE", 4, 8, 0, 8)

    view = rm.get_node_resources("node-1")
    assert view.cpu_available == 4
    assert view.ram_available == 8


def test_get_cluster_resources(rm):
    rm.register_node(_make_node("node-1", cpu=8, ram=16))
    rm.register_node(_make_node("node-2", cpu=4, ram=8, gpu=0, gpu_mem=0))

    cluster = rm.get_cluster_resources()
    assert cluster.cpu_total == 12
    assert cluster.ram_total == 24
    assert cluster.online_nodes == 2
    assert len(cluster.nodes) == 2


def test_concurrent_allocations(rm):
    rm.register_node(_make_node(cpu=4))
    req = _req(cpu=2)
    results = []

    def allocate(job_id):
        results.append(rm.allocate_resources("node-1", req, job_id))

    threads = [
        threading.Thread(target=allocate, args=(f"job-{i}",))
        for i in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(results) == 2
    view = rm.get_node_resources("node-1")
    assert view.cpu_available == 0
    assert len(view.running_workloads) == 2
