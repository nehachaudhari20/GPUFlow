from __future__ import annotations

import pytest

from backend.app.services.function_registry import (
    calculate_fibonacci,
    calculate_prime_count,
    FUNCTIONS,
    run_allowlisted_function,
)
from backend.app.services.autoscaling import AutoscalingEngine
from backend.app.storage.distributed_storage import DistributedStorageService


def test_function_registry_allowlist():
    assert "calculate_fibonacci" in FUNCTIONS
    assert calculate_fibonacci({"n": 5}) == 5
    assert calculate_prime_count({"n": 10}) >= 4
    assert run_allowlisted_function("calculate_fibonacci", {"n": 10}) == 55


def test_storage_safe_filename():
    svc = DistributedStorageService()
    with pytest.raises(ValueError):
        svc._safe_filename("bad name!.txt")


def test_autoscaling_cooldown():
    engine = AutoscalingEngine()
    d1 = engine.evaluate(queued_count=0)
    assert "current_worker_count" in d1.__dict__
