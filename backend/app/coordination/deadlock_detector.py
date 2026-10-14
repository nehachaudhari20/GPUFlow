from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class DeadlockReport:
    deadlock_detected: bool
    cycle_participants: List[str]
    resources_involved: List[str]
    detection_timestamp: float
    edges: List[Dict[str, str]]


class DeadlockDetector:
    """
    Wait-for graph prototype from distributed lock waiters and resource owners.

    Only reflects dependencies explicitly reported to the coordinator view.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._wait_for: Dict[str, str] = {}
        self._resource_map: Dict[str, str] = {}
        self._history: List[DeadlockReport] = []

    def update_edge(self, waiter: str, holder: str, resource: str) -> None:
        with self._lock:
            self._wait_for[waiter] = holder
            self._resource_map[waiter] = resource

    def clear_waiter(self, waiter: str) -> None:
        with self._lock:
            self._wait_for.pop(waiter, None)
            self._resource_map.pop(waiter, None)

    def detect(self) -> DeadlockReport:
        with self._lock:
            wait_for = dict(self._wait_for)
            resources = dict(self._resource_map)

        cycle: List[str] = []
        resources_involved: List[str] = []
        edges = [{"waiter": w, "waits_for": h} for w, h in wait_for.items()]

        visited: Set[str] = set()
        for start in wait_for:
            path: List[str] = []
            current: Optional[str] = start
            local_visited: Set[str] = set()
            while current and current not in local_visited:
                local_visited.add(current)
                path.append(current)
                current = wait_for.get(current)
            if current and current in local_visited:
                idx = path.index(current)
                cycle = path[idx:] + [current]
                resources_involved = [resources.get(n, "") for n in cycle if n in resources]
                break
            visited.add(start)

        report = DeadlockReport(
            deadlock_detected=bool(cycle),
            cycle_participants=cycle,
            resources_involved=[r for r in resources_involved if r],
            detection_timestamp=time.time(),
            edges=edges,
        )
        with self._lock:
            self._history.append(report)
            if len(self._history) > 100:
                self._history = self._history[-100:]
        return report

    def latest(self) -> Optional[DeadlockReport]:
        with self._lock:
            return self._history[-1] if self._history else None

    def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "deadlock_detected": r.deadlock_detected,
                    "cycle_participants": r.cycle_participants,
                    "resources_involved": r.resources_involved,
                    "detection_timestamp": r.detection_timestamp,
                    "edges": r.edges,
                }
                for r in self._history[-limit:]
            ]

    def clear(self) -> None:
        with self._lock:
            self._wait_for.clear()
            self._resource_map.clear()
            self._history.clear()
