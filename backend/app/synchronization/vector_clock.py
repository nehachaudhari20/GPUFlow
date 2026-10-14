from __future__ import annotations

import copy
import threading
from typing import Dict, Literal


VectorRelation = Literal["before", "after", "concurrent", "equal"]


class VectorClock:
    """Vector clock keyed by stable node IDs (dynamic membership)."""

    def __init__(self, node_id: str, initial: Dict[str, int] | None = None) -> None:
        self._node_id = node_id
        self._vector: Dict[str, int] = dict(initial or {})
        self._vector.setdefault(node_id, 0)
        self._lock = threading.Lock()

    @property
    def node_id(self) -> str:
        return self._node_id

    def increment(self, node_id: str | None = None) -> Dict[str, int]:
        key = node_id or self._node_id
        with self._lock:
            self._vector[key] = self._vector.get(key, 0) + 1
            return copy.deepcopy(self._vector)

    def merge(self, remote_vector: Dict[str, int]) -> Dict[str, int]:
        with self._lock:
            for nid, value in remote_vector.items():
                self._vector[nid] = max(self._vector.get(nid, 0), value)
            return copy.deepcopy(self._vector)

    def receive(self, remote_vector: Dict[str, int], local_node_id: str | None = None) -> Dict[str, int]:
        key = local_node_id or self._node_id
        with self._lock:
            for nid, value in remote_vector.items():
                self._vector[nid] = max(self._vector.get(nid, 0), value)
            self._vector[key] = self._vector.get(key, 0) + 1
            return copy.deepcopy(self._vector)

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return copy.deepcopy(self._vector)

    @staticmethod
    def compare(vector_a: Dict[str, int], vector_b: Dict[str, int]) -> VectorRelation:
        keys = set(vector_a) | set(vector_b)
        a_le_b = True
        b_le_a = True
        a_strict = False
        b_strict = False
        for key in keys:
            av = vector_a.get(key, 0)
            bv = vector_b.get(key, 0)
            if av > bv:
                a_le_b = False
            if bv > av:
                b_le_a = False
            if av < bv:
                a_strict = True
            if bv < av:
                b_strict = True
        if a_le_b and b_le_a:
            return "equal"
        if a_le_b and a_strict:
            return "before"
        if b_le_a and b_strict:
            return "after"
        return "concurrent"

    @staticmethod
    def happens_before(vector_a: Dict[str, int], vector_b: Dict[str, int]) -> bool:
        return VectorClock.compare(vector_a, vector_b) == "before"

    @staticmethod
    def is_concurrent(vector_a: Dict[str, int], vector_b: Dict[str, int]) -> bool:
        return VectorClock.compare(vector_a, vector_b) == "concurrent"
