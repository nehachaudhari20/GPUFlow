from __future__ import annotations

import json
import math
import subprocess
import sys
import time
import uuid
from typing import Any, Callable, Dict, List

from backend.app.models.workload import WorkloadCreate, WorkloadType, Priority


FUNCTIONS: Dict[str, Callable[[Dict[str, Any]], Any]] = {}


def _register(name: str, fn: Callable[[Dict[str, Any]], Any]) -> None:
    FUNCTIONS[name] = fn


def calculate_prime_count(params: Dict[str, Any]) -> int:
    n = int(params.get("n", 100))
    n = max(2, min(n, 500000))
    sieve = [True] * (n + 1)
    sieve[0] = sieve[1] = False
    for i in range(2, int(n**0.5) + 1):
        if sieve[i]:
            step = i
            start = i * i
            sieve[start : n + 1 : step] = [False] * len(sieve[start : n + 1 : step])
    return sum(1 for x in sieve if x)


def calculate_fibonacci(params: Dict[str, Any]) -> int:
    n = int(params.get("n", 10))
    n = max(0, min(n, 40))
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def summarize_numbers(params: Dict[str, Any]) -> Dict[str, float]:
    nums = params.get("values", [])
    if not isinstance(nums, list) or not nums:
        raise ValueError("values required")
    vals = [float(x) for x in nums[:1000]]
    return {"count": len(vals), "sum": sum(vals), "avg": sum(vals) / len(vals)}


def calculate_matrix_statistics(params: Dict[str, Any]) -> Dict[str, float]:
    rows = params.get("rows", 2)
    cols = params.get("cols", 2)
    rows = max(1, min(int(rows), 50))
    cols = max(1, min(int(cols), 50))
    data = [float((i + 1) * (j + 1)) for i in range(rows) for j in range(cols)]
    return {"mean": sum(data) / len(data), "max": max(data), "min": min(data)}


_register("calculate_prime_count", calculate_prime_count)
_register("calculate_fibonacci", calculate_fibonacci)
_register("summarize_numbers", summarize_numbers)
_register("calculate_matrix_statistics", calculate_matrix_statistics)


class FunctionInvocationService:
    def __init__(self) -> None:
        self._invocations: Dict[str, Dict[str, Any]] = {}

    def list_functions(self) -> List[str]:
        return sorted(FUNCTIONS.keys())

    def invoke(
        self,
        function_name: str,
        parameters: Dict[str, Any],
        cpu_required: float,
        ram_required: float,
        timeout_s: float,
        scheduler,
        workload_service,
    ) -> Dict[str, Any]:
        if function_name not in FUNCTIONS:
            raise ValueError("Unknown function")
        invocation_id = str(uuid.uuid4())
        started = time.time()
        payload = WorkloadCreate(
            name=f"fn-{function_name}",
            type=WorkloadType.BATCH,
            cpu_required=cpu_required,
            ram_required=ram_required,
            gpu_required=0,
            gpu_memory_required=0,
            priority=Priority.MEDIUM,
            estimated_duration=min(max(timeout_s, 1.0), 120.0),
        )
        wl = workload_service.create_workload(payload, job_id=invocation_id)
        decision = scheduler.schedule_and_update(workload_service, wl)
        result: Any = None
        error: str | None = None
        status = "SCHEDULED"
        worker = decision.selected_node
        if not decision.allocation_success:
            status = "QUEUED"
            error = decision.reason
        else:
            try:
                result = self._run_isolated(function_name, parameters, timeout_s)
                status = "COMPLETED"
                from backend.app.models.workload import WorkloadStatus

                try:
                    workload_service.update_status(invocation_id, WorkloadStatus.COMPLETED)
                except Exception:
                    pass
            except Exception as exc:
                error = str(exc)
                status = "FAILED"
                result = None
        record = {
            "invocation_id": invocation_id,
            "function_name": function_name,
            "parameters": parameters,
            "selected_worker": worker,
            "execution_status": status,
            "result": result,
            "execution_duration": time.time() - started,
            "errors": error,
        }
        self._invocations[invocation_id] = record
        return record

    def _run_isolated(self, function_name: str, parameters: Dict[str, Any], timeout_s: float) -> Any:
        code = (
            "import json, sys\n"
            "from backend.app.services.function_registry import FUNCTIONS\n"
            "params=json.loads(sys.argv[1])\n"
            "print(json.dumps(FUNCTIONS[sys.argv[2]](params)))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code, json.dumps(parameters), function_name],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2].parent),
            env={**dict(__import__("os").environ), "PYTHONPATH": str(__import__("pathlib").Path(__file__).resolve().parents[2].parent)},
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or "function failed")
        return json.loads(proc.stdout.strip())

    def get(self, invocation_id: str) -> Dict[str, Any] | None:
        return self._invocations.get(invocation_id)


function_invocation_service = FunctionInvocationService()
