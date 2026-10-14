from __future__ import annotations

from backend.app.recovery.retry_policy import RetryPolicy
from backend.app.recovery.recovery_manager import RecoveryManager
from backend.app.replication.replication_manager import ReplicationManager


def test_retry_policy_exponential():
    p = RetryPolicy(max_attempts=3, base_delay_s=1.0, max_delay_s=8.0)
    d1 = p.evaluate(0, "fail")
    assert d1.should_retry and d1.delay_s == 1.0
    d2 = p.evaluate(1, "fail")
    assert d2.delay_s == 2.0


def test_retry_exhaustion():
    p = RetryPolicy(max_attempts=2)
    assert not p.evaluate(1, "fail").should_retry


def test_replication_sequence_monotonic():
    rep = ReplicationManager()
    rep._mongo = None
    r1 = rep.replicate({"a": 1})
    r2 = rep.replicate({"b": 2})
    assert r2["sequence"] > r1["sequence"]
    assert not rep.apply_if_newer(1, {"stale": True})


def test_recovery_attempt_tracking():
    rm = RecoveryManager()
    att = rm.begin_attempt("job1", "node-a")
    assert att.attempt_number == 1
    assert rm.validate_status_update("job1", att.attempt_id, "RUNNING")
