import grpc
import logging
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "protobufs"))

import gpuflow_pb2
import gpuflow_pb2_grpc
from typing import Any, Dict, Tuple

from backend.app.models.workload import Workload
from backend.app.synchronization.process_sync import get_coordinator_sync
from backend.app.synchronization.grpc_metadata import apply_vector_to_proto

logger = logging.getLogger(__name__)

class WorkerClient:
    def __init__(self, hostname: str, port: int, timeout: float = 5.0):
        self.target = f"{hostname}:{port}"
        self.timeout = timeout

    def assign_task(self, workload: Workload) -> bool:
        if not self.target or ":0" in self.target:
            logger.error(f"Invalid worker target: {self.target}")
            return False

        try:
            with grpc.insecure_channel(self.target) as channel:
                stub = gpuflow_pb2_grpc.WorkerStub(channel)
                coord = get_coordinator_sync()
                lamport, vector = coord.on_send()
                req = gpuflow_pb2.AssignTaskRequest(
                    task_id=workload.job_id,
                    workload_type=workload.type.value,
                    cpu_req=workload.cpu_required,
                    gpu_req=workload.gpu_required,
                    gpu_memory_req=workload.gpu_memory_required,
                    ram_req=workload.ram_required,
                    estimated_duration=workload.estimated_duration,
                    lamport_time=lamport,
                )
                apply_vector_to_proto(req.vector_clock, vector)
                response = stub.AssignTask(req, timeout=self.timeout)
                return response.success
        except Exception as e:
            logger.error(f"Error calling AssignTask on worker {self.target}: {e}")
            return False

    def invoke_function(
        self,
        invocation_id: str,
        function_name: str,
        parameters: Dict[str, Any],
        timeout_s: float,
    ) -> Tuple[bool, Any, str, str]:
        """Run an allowlisted function on the worker process. Returns success, result, error, node_id."""
        import json

        if not self.target or ":0" in self.target:
            return False, None, "invalid worker target", ""
        try:
            with grpc.insecure_channel(self.target) as channel:
                stub = gpuflow_pb2_grpc.WorkerStub(channel)
                resp = stub.InvokeFunction(
                    gpuflow_pb2.InvokeFunctionRequest(
                        invocation_id=invocation_id,
                        function_name=function_name,
                        parameters_json=json.dumps(parameters),
                        timeout_s=timeout_s,
                    ),
                    timeout=max(timeout_s, 5.0),
                )
                result = json.loads(resp.result_json) if resp.result_json else None
                return resp.success, result, resp.error, resp.worker_node_id
        except Exception as e:
            logger.error(f"Error calling InvokeFunction on {self.target}: {e}")
            return False, None, str(e), ""

    def release_resources(self, task_id: str) -> bool:
        if not self.target or ":0" in self.target:
            return False

        try:
            with grpc.insecure_channel(self.target) as channel:
                stub = gpuflow_pb2_grpc.WorkerStub(channel)
                req = gpuflow_pb2.ReleaseResourceRequest(task_id=task_id)
                response = stub.ReleaseResources(req, timeout=self.timeout)
                return response.success
        except Exception as e:
            logger.error(f"Error calling ReleaseResources on worker {self.target}: {e}")
            return False
