from __future__ import annotations

import grpc
from concurrent import futures
import logging
import time
import threading

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "protobufs"))

import gpuflow_pb2
import gpuflow_pb2_grpc
from backend.app.config import settings
from backend.app.synchronization.process_sync import get_worker_sync
from backend.app.synchronization.grpc_metadata import vector_from_proto
from backend.app.synchronization.event_sync import log_synchronized_event
from backend.app.events.event_manager import EventType

logger = logging.getLogger(__name__)

class WorkerServicer(gpuflow_pb2_grpc.WorkerServicer):
    def __init__(self, node_id: str, scheduler_address: str | None = None, daemon = None):
        self.node_id = node_id
        self.scheduler_address = scheduler_address or settings.scheduler_address
        self.daemon = daemon
        self.tasks = {}
        self._active_task_id: str | None = None
        self._lock = threading.Lock()

    def is_busy(self) -> bool:
        with self._lock:
            return self._active_task_id is not None

    def _report_status_to_scheduler(self, task_id: str, status: str, message: str = ""):
        try:
            with grpc.insecure_channel(self.scheduler_address) as channel:
                stub = gpuflow_pb2_grpc.SchedulerStub(channel)
                sync = get_worker_sync(self.node_id)
                lamport, vector = sync.on_send()
                req = gpuflow_pb2.TaskStatusReportRequest(
                    task_id=task_id,
                    node_id=self.node_id,
                    status=status,
                    message=message,
                    timestamp=int(time.time() * 1000),
                    lamport_time=lamport,
                )
                for key, value in vector.items():
                    req.vector_clock[key] = value
                stub.ReportTaskStatus(req, timeout=3.0)
        except Exception as e:
            logger.error(f"Worker {self.node_id} failed to report task status {status} for {task_id}: {e}")

    def _execute_workload(self, task_id: str, duration: float):
        logger.info(
            f"Worker {self.node_id} starting execution of task {task_id} "
            f"(duration={duration}s)"
        )
        with self._lock:
            self.tasks[task_id] = "RUNNING"
        log_synchronized_event(
            EventType.TASK_STARTED,
            sync=get_worker_sync(self.node_id),
            source="WORKER",
            destination="SCHEDULER",
            job_id=task_id,
            node_id=self.node_id,
            message="Task execution started",
        )
        self._report_status_to_scheduler(task_id, "RUNNING", "Task execution started")

        run_time = max(duration, 0.5) if duration > 0 else 0.5
        time.sleep(run_time)

        with self._lock:
            self.tasks[task_id] = "COMPLETED"
            if self._active_task_id == task_id:
                self._active_task_id = None
        self._report_status_to_scheduler(task_id, "COMPLETED", "Task execution completed successfully")
        logger.info(f"Worker {self.node_id} completed execution of task {task_id}")

    def AssignTask(self, request, context):
        task_id = request.task_id
        logger.info(f"Worker {self.node_id} received AssignTask request for {task_id}")

        sync = get_worker_sync(self.node_id)
        if request.lamport_time:
            sync.on_receive(
                int(request.lamport_time),
                vector_from_proto(request.vector_clock),
            )
        log_synchronized_event(
            EventType.TASK_ASSIGNED,
            sync=sync,
            source="SCHEDULER",
            destination="WORKER",
            job_id=task_id,
            node_id=self.node_id,
            message=f"Task {task_id} assigned to worker {self.node_id}",
        )

        with self._lock:
            if self._active_task_id is not None:
                return gpuflow_pb2.AssignTaskResponse(
                    success=False,
                    message=f"Worker busy executing task {self._active_task_id}",
                )
            if task_id in self.tasks and self.tasks[task_id] == "RUNNING":
                return gpuflow_pb2.AssignTaskResponse(
                    success=False, message="Task already running"
                )
            self._active_task_id = task_id
            self.tasks[task_id] = "SCHEDULED"

        duration = request.estimated_duration if request.estimated_duration > 0 else 2.0
        exec_thread = threading.Thread(
            target=self._execute_workload, args=(task_id, duration), daemon=True
        )
        exec_thread.start()

        return gpuflow_pb2.AssignTaskResponse(
            success=True, message=f"Task {task_id} accepted for execution"
        )

    def GetTaskStatus(self, request, context):
        task_id = request.task_id
        with self._lock:
            status = self.tasks.get(task_id, "UNKNOWN")
        return gpuflow_pb2.TaskStatusResponse(status=status, message="", progress=1.0 if status == "COMPLETED" else 0.5)

    def GetResourceStatus(self, request, context):
        if self.daemon:
            return gpuflow_pb2.ResourceStatusResponse(
                node_id=self.node_id,
                status="ONLINE" if self.daemon.running else "OFFLINE",
                cpu_total=self.daemon.cpu_total,
                cpu_available=self.daemon.cpu_total,
                ram_total=self.daemon.ram_total,
                ram_available=self.daemon.ram_total,
                gpu_total=self.daemon.gpu_total,
                gpu_available=self.daemon.gpu_total,
                gpu_memory_total=self.daemon.gpu_memory_total,
                gpu_memory_available=self.daemon.gpu_memory_total,
            )
        return gpuflow_pb2.ResourceStatusResponse(
            node_id=self.node_id,
            status="ONLINE",
            cpu_total=8.0,
            cpu_available=8.0,
            ram_total=16.0,
            ram_available=16.0,
            gpu_total=1.0,
            gpu_available=1.0,
            gpu_memory_total=16.0,
            gpu_memory_available=16.0,
        )

    def ReleaseResources(self, request, context):
        task_id = request.task_id
        logger.info(f"Worker {self.node_id} releasing resources for {task_id}")
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id] = "COMPLETED"
                return gpuflow_pb2.ReleaseResourceResponse(success=True)
        return gpuflow_pb2.ReleaseResourceResponse(success=True)

    def StoreFile(self, request, context):
        import hashlib
        from pathlib import Path

        base = Path(os.environ.get("GPUFLOW_WORKER_STORAGE", "/tmp/gpuflow-worker-storage"))
        base.mkdir(parents=True, exist_ok=True)
        safe_id = request.file_id.replace("/", "").replace("..", "")
        path = base / safe_id
        path.write_bytes(request.content)
        digest = hashlib.sha256(request.content).hexdigest()
        if request.checksum and request.checksum != digest:
            path.unlink(missing_ok=True)
            return gpuflow_pb2.StoreFileResponse(success=False, message="checksum mismatch")
        return gpuflow_pb2.StoreFileResponse(success=True, message="stored")

    def RetrieveFile(self, request, context):
        import hashlib
        from pathlib import Path

        base = Path(os.environ.get("GPUFLOW_WORKER_STORAGE", "/tmp/gpuflow-worker-storage"))
        safe_id = request.file_id.replace("/", "").replace("..", "")
        path = base / safe_id
        if not path.exists():
            return gpuflow_pb2.RetrieveFileResponse(success=False, message="not found")
        data = path.read_bytes()
        return gpuflow_pb2.RetrieveFileResponse(
            success=True, content=data, checksum=hashlib.sha256(data).hexdigest(), message="ok"
        )

    def SendPeerMessage(self, request, context):
        """P2P messaging between workers (Unit 2 syllabus)."""
        logger.info(
            f"Worker {self.node_id} received P2P message '{request.message_type}' "
            f"from sender {request.sender_node_id}: {request.payload}"
        )
        if self.daemon and hasattr(self.daemon, "coordination"):
            self.daemon.coordination.handle_peer_message(
                request.message_type, request.payload, request.sender_node_id
            )
        reply = f"ACK from node {self.node_id} for peer message '{request.message_type}'"
        return gpuflow_pb2.PeerMessageResponse(success=True, reply_payload=reply)

    def InvokeFunction(self, request, context):
        import json

        from backend.app.services.function_registry import run_allowlisted_function

        try:
            params = json.loads(request.parameters_json or "{}")
            result = run_allowlisted_function(request.function_name, params)
            return gpuflow_pb2.InvokeFunctionResponse(
                success=True,
                result_json=json.dumps(result),
                error="",
                worker_node_id=self.node_id,
            )
        except Exception as exc:
            logger.error("InvokeFunction failed on %s: %s", self.node_id, exc)
            return gpuflow_pb2.InvokeFunctionResponse(
                success=False,
                result_json="",
                error=str(exc),
                worker_node_id=self.node_id,
            )

def start_worker_server(node_id: str, port: int, scheduler_address: str | None = None, daemon = None) -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = WorkerServicer(node_id=node_id, scheduler_address=scheduler_address, daemon=daemon)
    gpuflow_pb2_grpc.add_WorkerServicer_to_server(servicer, server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f"Worker {node_id} gRPC server started on port {port}")
    return server
