from enum import Enum
import time
import uuid
import threading
from typing import Dict, List, Optional, Any, Callable
from pydantic import BaseModel, Field

class EventType(str, Enum):
    NODE_REGISTERED = "NODE_REGISTERED"
    HEARTBEAT_RECEIVED = "HEARTBEAT_RECEIVED"
    NODE_OFFLINE = "NODE_OFFLINE"
    JOB_SUBMITTED = "JOB_SUBMITTED"
    JOB_QUEUED = "JOB_QUEUED"
    NODE_EVALUATED = "NODE_EVALUATED"
    NODE_REJECTED = "NODE_REJECTED"
    NODE_SELECTED = "NODE_SELECTED"
    RESOURCE_ALLOCATED = "RESOURCE_ALLOCATED"
    TASK_ASSIGNED = "TASK_ASSIGNED"
    TASK_STARTED = "TASK_STARTED"
    RESOURCE_UPDATED = "RESOURCE_UPDATED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    RESOURCE_RELEASED = "RESOURCE_RELEASED"
    PEER_MESSAGE_SENT = "PEER_MESSAGE_SENT"
    HEARTBEAT_SENT = "HEARTBEAT_SENT"

class SystemEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    event_type: EventType
    source: str = "SCHEDULER"
    destination: Optional[str] = None
    job_id: Optional[str] = None
    node_id: Optional[str] = None
    message: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    lamport_timestamp: Optional[int] = None
    vector_clock: Optional[Dict[str, int]] = None

class EventManager:
    def __init__(self):
        self._events: List[SystemEvent] = []
        self._listeners: List[Callable[[SystemEvent], None]] = []
        self._lock = threading.Lock()

    def emit(self, event: SystemEvent):
        with self._lock:
            self._events.append(event)
            listeners_copy = list(self._listeners)

        for listener in listeners_copy:
            try:
                listener(event)
            except Exception:
                pass

    def log_event(
        self,
        event_type: EventType,
        source: str = "SCHEDULER",
        destination: Optional[str] = None,
        job_id: Optional[str] = None,
        node_id: Optional[str] = None,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SystemEvent:
        event = SystemEvent(
            event_type=event_type,
            source=source,
            destination=destination,
            job_id=job_id,
            node_id=node_id,
            message=message,
            metadata=metadata or {},
        )
        self.emit(event)
        return event

    def add_listener(self, listener: Callable[[SystemEvent], None]):
        with self._lock:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[SystemEvent], None]):
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def get_events(
        self,
        job_id: Optional[str] = None,
        node_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        limit: int = 100,
    ) -> List[SystemEvent]:
        with self._lock:
            res = list(self._events)

        if job_id:
            res = [e for e in res if e.job_id == job_id]
        if node_id:
            res = [e for e in res if e.node_id == node_id]
        if event_type:
            res = [e for e in res if e.event_type == event_type]
        return res[-limit:]

    def clear_all(self):
        with self._lock:
            self._events.clear()

event_manager = EventManager()
