from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from backend.app.events.event_manager import EventType, event_manager
from backend.app.main import app
from backend.app.synchronization.clock_sync import CristianSyncSample, clock_sync_registry
from backend.app.synchronization.global_snapshot import global_snapshot_service
from backend.app.synchronization.lamport_clock import LamportClock
from backend.app.synchronization.process_sync import ProcessSynchronization, reset_sync_registry
from backend.app.synchronization.vector_clock import VectorClock
from backend.app.synchronization.event_sync import log_synchronized_event


class TestLamportClock:
    def test_tick_increments(self):
        clock = LamportClock()
        assert clock.tick() == 1
        assert clock.tick() == 2
        assert clock.get_time() == 2

    def test_receive_rule(self):
        clock = LamportClock(5)
        assert clock.receive_event(10) == 11
        assert clock.get_time() == 11
        assert clock.receive_event(8) == 12

    def test_concurrent_updates_thread_safe(self):
        clock = LamportClock()
        errors: list[str] = []

        def worker():
            try:
                for _ in range(100):
                    clock.tick()
            except Exception as exc:  # pragma: no cover
                errors.append(str(exc))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert clock.get_time() == 800


class TestVectorClock:
    def test_merge_and_happens_before(self):
        a = VectorClock("a")
        b = VectorClock("b")
        va = a.increment()
        vb = b.increment()
        vb2 = b.receive(va, "b")
        assert VectorClock.happens_before(va, vb2)

    def test_concurrent_events(self):
        a = VectorClock("a")
        b = VectorClock("b")
        va = a.increment()
        vb = b.increment()
        assert VectorClock.is_concurrent(va, vb)

    def test_dynamic_membership(self):
        clock = VectorClock("coordinator")
        remote = {"worker-1": 2, "worker-2": 1}
        merged = clock.receive(remote, "coordinator")
        assert merged["worker-1"] == 2
        assert merged["worker-2"] == 1
        assert merged["coordinator"] == 1


class TestClockSync:
    def test_cristian_offset(self):
        sample = CristianSyncSample(
            node_id="n1",
            client_request_ms=1000.0,
            client_response_ms=1100.0,
            server_receive_ms=1040.0,
            server_reply_ms=1060.0,
        )
        assert sample.round_trip_time_ms == 100.0
        assert sample.estimated_offset_ms == 0.0

    def test_registry_records_sample(self):
        clock_sync_registry.clear()
        record = clock_sync_registry.record_cristian_sample(
            CristianSyncSample(
                node_id="w1",
                client_request_ms=0,
                client_response_ms=50,
                server_receive_ms=20,
                server_reply_ms=30,
            )
        )
        assert record.node_id == "w1"
        assert clock_sync_registry.get_offset("w1") is not None


class TestGlobalSnapshot:
    def test_snapshot_serialization(self):
        global_snapshot_service.clear()
        reset_sync_registry()
        event_manager.clear_all()
        snap = global_snapshot_service.capture()
        assert snap["snapshot_type"] == "monitoring_assembled"
        assert snap["consistent_distributed_snapshot"] is False
        assert "snapshot_id" in snap
        assert "coordinator_logical_timestamp" in snap


class TestProcessIntegration:
    def test_two_nodes_message_exchange(self):
        coordinator = ProcessSynchronization("coordinator")
        worker = ProcessSynchronization("worker-1")

        send_lp, send_vc = worker.on_send()
        recv_lp, recv_vc = coordinator.on_receive(send_lp, send_vc)
        assert recv_lp > send_lp
        assert VectorClock.happens_before(send_vc, recv_vc)

        reply_lp, reply_vc = coordinator.on_send()
        w_lp, w_vc = worker.on_receive(reply_lp, reply_vc)
        assert w_lp > reply_lp
        assert VectorClock.happens_before(reply_vc, w_vc)


class TestFa2Api:
    @pytest.fixture(autouse=True)
    def _clean(self):
        reset_sync_registry()
        clock_sync_registry.clear()
        global_snapshot_service.clear()
        event_manager.clear_all()
        yield

    def test_clocks_endpoint(self):
        client = TestClient(app)
        log_synchronized_event(EventType.JOB_SUBMITTED, job_id="j1", message="test")
        resp = client.get("/fa2/synchronization/clocks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["coordinator"]["lamport_time"] >= 1

    def test_events_endpoint_includes_lamport(self):
        client = TestClient(app)
        log_synchronized_event(EventType.JOB_QUEUED, job_id="j2")
        resp = client.get("/fa2/synchronization/events?limit=5")
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert events[-1]["lamport_timestamp"] is not None


class TestSchedulingCompatibility:
    def test_workload_events_still_emitted(self):
        reset_sync_registry()
        event_manager.clear_all()
        log_synchronized_event(
            EventType.JOB_SUBMITTED,
            source="USER",
            job_id="compat-job",
            message="submit",
        )
        events = event_manager.get_events(job_id="compat-job")
        assert len(events) == 1
        assert events[0].event_type == EventType.JOB_SUBMITTED
