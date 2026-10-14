from __future__ import annotations

import time

from backend.app.coordination.bully_election import BullyElectionManager, ElectionState
from backend.app.coordination.deadlock_detector import DeadlockDetector
from backend.app.coordination.distributed_lock import RicartAgrawalaLockManager
from backend.app.coordination.coordinator import CoordinationService


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
    svc.report_coordinator("w2", 2)
    leader = svc.get_leader()
    assert leader["coordinator_node_id"] == "w2"
