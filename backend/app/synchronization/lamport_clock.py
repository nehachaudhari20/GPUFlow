from __future__ import annotations

import threading


class LamportClock:
    """Thread-safe Lamport logical clock."""

    def __init__(self, initial: int = 0) -> None:
        self._time = initial
        self._lock = threading.Lock()

    def tick(self) -> int:
        with self._lock:
            self._time += 1
            return self._time

    def send_event(self) -> int:
        with self._lock:
            self._time += 1
            return self._time

    def receive_event(self, remote_timestamp: int) -> int:
        with self._lock:
            self._time = max(self._time, remote_timestamp) + 1
            return self._time

    def get_time(self) -> int:
        with self._lock:
            return self._time
