import grpc
from concurrent import futures
import time
import logging

# Note: We will generate protobuf code dynamically or assume it is available in backend/protobufs
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "protobufs"))

import gpuflow_pb2
import gpuflow_pb2_grpc

from backend.app.scheduler.cluster_state import cluster_state
from backend.app.scheduler.resource_manager import resource_manager
from backend.app.models.resources import ResourceRequirements
from backend.app.models.worker import WorkerNode
from backend.app.config import settings

logger = logging.getLogger(__name__)

class SchedulerServicer(gpuflow_pb2_grpc.SchedulerServicer):
    def RegisterNode(self, request, context):
        node = WorkerNode(
            node_id=request.node_id,
            hostname=request.hostname,
            cpu_total=request.cpu_total,
            cpu_available=request.cpu_total,
            ram_total=request.ram_total,
            ram_available=request.ram_total,
            gpu_total=request.gpu_total,
            gpu_available=request.gpu_total,
            gpu_memory_total=request.gpu_memory_total,
            gpu_memory_available=request.gpu_memory_total,
            status="ONLINE",
            last_heartbeat=time.time()
        )
        cluster_state.register_node(node)
        return gpuflow_pb2.RegisterNodeResponse(success=True, message="Node registered successfully")

    def SendHeartbeat(self, request, context):
        cluster_state.update_heartbeat(
            node_id=request.node_id,
            status=request.status,
            timestamp=request.timestamp / 1000.0, # convert to seconds
            cpu_avail=request.cpu_available,
            ram_avail=request.ram_available,
            gpu_avail=request.gpu_available,
            gpu_mem_avail=request.gpu_memory_available
        )
        return gpuflow_pb2.HeartbeatResponse(acknowledged=True)

    def SubmitTask(self, request, context):
        online_nodes = cluster_state.get_online_nodes()
        if not online_nodes:
            return gpuflow_pb2.TaskResponse(
                accepted=False,
                message="No online worker nodes available for scheduling",
            )

        requirements = ResourceRequirements(
            cpu=request.cpu_req,
            gpu=request.gpu_req,
            ram=request.ram_req,
        )

        for node in online_nodes:
            if resource_manager.can_allocate(node.node_id, requirements):
                job_id = request.task_id
                if resource_manager.allocate_resources(
                    node.node_id, requirements, job_id
                ):
                    cluster_state.sync_node_resources(node.node_id)
                    return gpuflow_pb2.TaskResponse(
                        accepted=True,
                        message=f"Task allocated on node {node.node_id}",
                    )

        return gpuflow_pb2.TaskResponse(
            accepted=False,
            message="Insufficient cluster resources for task",
        )

def serve_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    gpuflow_pb2_grpc.add_SchedulerServicer_to_server(SchedulerServicer(), server)
    server.add_insecure_port(f'[::]:{settings.grpc_port}')
    server.start()
    logger.info(f"gRPC Scheduler Server started on port {settings.grpc_port}")
    server.wait_for_termination()
