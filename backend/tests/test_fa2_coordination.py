from __future__ import annotations

import time

from backend.app.coordination.bully_election import BullyElectionManager, ElectionState
from backend.app.coordination.deadlock_detector import DeadlockDetector
from backend.app.coordination.distributed_lock import RicartAgrawalaLockManager
from backend.app.coordination.coordinator import CoordinationService
from backend.app.coordination.ra_demo import RicartAgrawalaDemo


def test_highest_id_election_wins():
    sent = []

    def send(host, port, msg_type, payload):
        sent.append((msg_type, payload))
        return True

    bully = BullyElectionManager("n3", 3, send_message=send)
    bully.set_peers({"n1": 1, "n2": 2})
    bully.set_peer_targets({"n1": ("h1", 1), "n2": ("h2", 2)})
    record = bully.start_election(reason="test")
    assert record is not None
    coord, eid = bully.get_coordinator()
    assert coord == "n3"
    assert eid == 3


def test_coordinator_failure_re_election():
    bully = BullyElectionManager("n1", 1, send_message=None)
    bully.set_peers({"n2": 2})
    bully.handle_message("COORDINATOR", "COORDINATOR|n2|2", "n2")
    assert bully.get_state() in (ElectionState.FOLLOWER, ElectionState.ELECTION_IN_PROGRESS)
    bully.on_coordinator_timeout()
    assert bully.get_state() == ElectionState.ELECTION_IN_PROGRESS


def test_lock_lamport_ordering():
    lock = RicartAgrawalaLockManager("a", lambda: 1, lambda: 2)
    lock.set_membership(1, {"a", "b"})
    lock.handle_remote_request("r1", "ledger", "b", 5)
    req = lock.request_lock("ledger")
    assert req.lamport_timestamp == 2


def test_ra_defer_when_local_has_priority():
    replies: list[str] = []
    clock = {"t": 0}

    def tick() -> int:
        clock["t"] += 1
        return clock["t"]

    lock = RicartAgrawalaLockManager(
        "a", lambda: clock["t"], tick, send_reply=lambda n, *_: replies.append(n)
    )
    lock.set_membership(1, {"a", "b"})
    lock.request_lock("ledger")
    lock.handle_remote_request("r1", "ledger", "b", 9)
    assert replies == []


def test_ra_reply_when_incoming_has_priority():
    replies: list[str] = []
    clock = {"t": 4}

    def tick() -> int:
        clock["t"] += 1
        return clock["t"]

    lock = RicartAgrawalaLockManager(
        "a", lambda: clock["t"], tick, send_reply=lambda n, *_: replies.append(n)
    )
    lock.set_membership(1, {"a", "b"})
    lock.request_lock("ledger")
    lock.handle_remote_request("r1", "ledger", "b", 1)
    assert replies == ["b"]


def test_ra_enter_after_all_replies():
    lock = RicartAgrawalaLockManager("a", lambda: 1, lambda: 2)
    lock.set_membership(1, {"a", "b"})
    lock.request_lock("ledger")
    assert not lock.try_enter_critical_section("ledger")
    lock.on_reply("b")
    assert lock.try_enter_critical_section("ledger")
    lock.release_lock("ledger")


def test_deadlock_cycle():
    det = DeadlockDetector()
    det.update_edge("a", "b", "res1")
    det.update_edge("b", "a", "res2")
    report = det.detect()
    assert report.deadlock_detected
    assert "a" in report.cycle_participants


def test_no_deadlock():
    det = DeadlockDetector()
    det.update_edge("a", "b", "res1")
    report = det.detect()
    assert not report.deadlock_detected


def test_coordination_service_leader():
    svc = CoordinationService()
    svc.register_member("w1", 1, "h1", 50052)
    svc.register_member("w2", 2, "h2", 50052)
    svc.report_coordinator("w2", 2)
    leader = svc.get_leader()
    assert leader["coordinator_node_id"] == "w2"


def test_drop_coordinator_elects_next_highest():
    svc = CoordinationService()
    svc.register_member("w1", 1, "worker-1", 1)
    svc.register_member("w2", 2, "worker-2", 1)
    svc.register_member("w3", 3, "worker-3", 1)
    svc.report_coordinator("w3", 3)
    leader = svc.drop_member("w3", reason="simulated_failure")
    assert leader["coordinator_node_id"] == "w2"
    assert leader["coordinator_election_id"] == 2
    assert all(m["node_id"] != "w3" for m in svc.list_members())


def test_ra_demo_spreads_mutex_across_workers():
    demo = RicartAgrawalaDemo()
    demo.sync_members(
        [
            {"node_id": "n1", "hostname": "worker-1"},
            {"node_id": "n2", "hostname": "worker-2"},
            {"node_id": "n3", "hostname": "worker-3"},
        ]
    )
    first = demo.request("n1")
    assert first["owner"] == "n1"
    second = demo.request("n2")
    assert second["owner"] == "n1"
    n2 = next(n for n in second["nodes"] if n["node_id"] == "n2")
    assert "n1" in n2["outstanding_replies"]
    demo.release("n1")
    after = demo.snapshot()
    assert after["owner"] == "n2"
    demo.release("n2")
    assert demo.snapshot()["owner"] is None
