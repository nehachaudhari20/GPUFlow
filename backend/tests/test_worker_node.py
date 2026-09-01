import time
import pytest
from backend.app.models.worker import WorkerNode
from backend.app.scheduler.cluster_state import ClusterState


def test_node_registration():
    state = ClusterState()
    node = WorkerNode(
        node_id="test-node-1",
        hostname="test-host",
        cpu_total=8,
        cpu_available=8,
        ram_total=16,
        ram_available=16,
        gpu_total=1,
        gpu_available=1,
        gpu_memory_total=16,
        gpu_memory_available=16,
    )
    state.register_node(node)

    nodes = state.get_all_nodes()
    assert len(nodes) == 1
    assert nodes[0].node_id == "test-node-1"
    assert nodes[0].status == "ONLINE"


def test_heartbeat_update():
    state = ClusterState()
    node = WorkerNode(
        node_id="test-node-1",
        hostname="test-host",
        cpu_total=8,
        cpu_available=8,
        ram_total=16,
        ram_available=16,
        gpu_total=1,
        gpu_available=1,
        gpu_memory_total=16,
        gpu_memory_available=16,
    )
    state.register_node(node)

    new_timestamp = time.time() + 10
    state.update_heartbeat(
        node_id="test-node-1",
        status="ONLINE",
        timestamp=new_timestamp,
        cpu_avail=4,
        ram_avail=8,
        gpu_avail=0,
        gpu_mem_avail=0,
    )

    nodes = state.get_all_nodes()
    assert nodes[0].cpu_available == 4
    assert nodes[0].last_heartbeat == new_timestamp


def test_heartbeat_timeout(monkeypatch):
    state = ClusterState()
    node = WorkerNode(
        node_id="test-node-1",
        hostname="test-host",
        cpu_total=8,
        cpu_available=8,
        ram_total=16,
        ram_available=16,
        gpu_total=1,
        gpu_available=1,
        gpu_memory_total=16,
        gpu_memory_available=16,
    )
    state.register_node(node)

    import backend.app.config

    monkeypatch.setattr(backend.app.config.settings, "heartbeat_timeout", 1)

    time.sleep(1.5)
    state.check_timeouts()

    nodes = state.get_all_nodes()
    assert nodes[0].status == "OFFLINE"


def test_offline_status(monkeypatch):
    state = ClusterState()
    node = WorkerNode(
        node_id="offline-node",
        hostname="test-host",
        cpu_total=4,
        cpu_available=4,
        ram_total=8,
        ram_available=8,
        gpu_total=1,
        gpu_available=1,
        gpu_memory_total=8,
        gpu_memory_available=8,
    )
    state.register_node(node)

    import backend.app.config

    monkeypatch.setattr(backend.app.config.settings, "heartbeat_timeout", 1)

    assert state.is_schedulable("offline-node") is True
    assert len(state.get_online_nodes()) == 1

    time.sleep(1.5)
    state.check_timeouts()

    assert state.get_node("offline-node").status == "OFFLINE"
    assert state.is_schedulable("offline-node") is False
    assert len(state.get_online_nodes()) == 0


def test_failure_event_recorded(monkeypatch):
    state = ClusterState()
    node = WorkerNode(
        node_id="failing-node",
        hostname="fail-host",
        cpu_total=4,
        cpu_available=4,
        ram_total=8,
        ram_available=8,
        gpu_total=0,
        gpu_available=0,
        gpu_memory_total=0,
        gpu_memory_available=0,
    )
    state.register_node(node)

    import backend.app.config

    monkeypatch.setattr(backend.app.config.settings, "heartbeat_timeout", 1)

    time.sleep(1.5)
    state.check_timeouts()

    events = state.get_failure_events()
    assert len(events) == 1
    assert events[0].node_id == "failing-node"
    assert events[0].hostname == "fail-host"
    assert events[0].reason == "heartbeat_timeout"
