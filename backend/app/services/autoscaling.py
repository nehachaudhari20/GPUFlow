from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List

from backend.app.config import settings
from backend.app.scheduler.cluster_state import cluster_state
from backend.app.scheduler.resource_manager import resource_manager


@dataclass
class AutoscaleDecision:
    current_worker_count: int
    desired_worker_count: int
    scale_out_recommended: bool
    scale_in_recommended: bool
    reason: str
    timestamp: float


class AutoscalingEngine:
    """Decision-only autoscaling (does not provision EC2)."""

    def __init__(self) -> None:
        self._last_scale_time = 0.0
        self._history: List[Dict[str, Any]] = []

    def evaluate(self, queued_count: int) -> AutoscaleDecision:
        nodes = cluster_state.get_online_nodes()
        current = len(nodes)
        cluster = resource_manager.get_cluster_resources()
        cpu_util = cluster.cpu_utilization if hasattr(cluster, "cpu_utilization") else 0.0
        desired = current
        scale_out = False
        scale_in = False
        reason = "steady"

        if queued_count >= settings.autoscale_queue_depth_high or cpu_util >= settings.autoscale_cpu_high:
            desired = min(settings.autoscale_max_workers, current + 1)
            scale_out = desired > current
            reason = "high load or queue depth"
        elif queued_count == 0 and cpu_util < 0.3 and current > settings.autoscale_min_workers:
            busy = any(n.current_workloads for n in nodes if n.current_workloads)
            if not busy:
                desired = max(settings.autoscale_min_workers, current - 1)
                scale_in = desired < current
                reason = "low utilization"

        now = time.time()
        if (scale_out or scale_in) and now - self._last_scale_time < settings.autoscale_cooldown_s:
            scale_out = scale_in = False
            reason = "cooldown active"

        if scale_out or scale_in:
            self._last_scale_time = now

        decision = AutoscaleDecision(
            current_worker_count=current,
            desired_worker_count=desired,
            scale_out_recommended=scale_out,
            scale_in_recommended=scale_in,
            reason=reason,
            timestamp=now,
        )
        self._history.append(decision.__dict__)
        return decision

    def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._history[-limit:]


autoscaling_engine = AutoscalingEngine()
