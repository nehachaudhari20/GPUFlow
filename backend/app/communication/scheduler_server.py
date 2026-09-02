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
from backend.app.models.worker import WorkerNode
from backend.app.models.workload import WorkloadCreate, WorkloadType, Priority, WorkloadStatus
from backend.app.models.resources import ResourceRequirements
from backend.app.scheduler.resource_manager import resource_manager
from backend.app.services.workload_service import workload_service
from backend.app.scheduler.scheduler import scheduler
from backend.app.config import settings

logger = logging.getLogger(__name__)

class SchedulerServicer(gpuflow_pb2_grpc.SchedulerServicer):
    def RegisterNode(self, request, context):
        node = WorkerNode(
            node_id=request.node_id,
            hostname=request.hostname,
            grpc_port=request.grpc_port,
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
            gpu_mem_avail=request.gpu_memory_available,
            grpc_port=request.grpc_port
        )
        return gpuflow_pb2.HeartbeatResponse(acknowledged=True)

    def SubmitTask(self, request, context):
        try:
            payload = WorkloadCreate(
                name=request.task_id or "grpc-task",
                type=WorkloadType.BATCH,
                cpu_required=request.cpu_req,
                gpu_required=request.gpu_req,
                ram_required=request.ram_req,
                priority=Priority.MEDIUM,
                estimated_duration=60,
            )
            workload = workload_service.create_workload(
                payload, job_id=request.task_id or None
            )
            decision = scheduler.schedule_and_update(workload_service, workload)
            if decision.allocation_success:
                return gpuflow_pb2.TaskResponse(
                    accepted=True,
                    message=f"Workload {workload.job_id} scheduled on {decision.selected_node}",
                )
            return gpuflow_pb2.TaskResponse(
                accepted=True,
                message=f"Workload {workload.job_id} queued: {decision.reason}",
            )
        except ValueError as exc:
            return gpuflow_pb2.TaskResponse(accepted=False, message=str(exc))

    def ReportTaskStatus(self, request, context):
        try:
            status_enum = WorkloadStatus(request.status)
            workload = workload_service.get_workload(request.task_id)
            if workload:
                if workload.status != status_enum:
                    workload_service.update_status(
                        request.task_id, status_enum, assigned_node=request.node_id
                    )
                if status_enum in (WorkloadStatus.COMPLETED, WorkloadStatus.FAILED):
                    reqs = ResourceRequirements(
                        cpu=workload.cpu_required,
                        ram=workload.ram_required,
                        gpu=workload.gpu_required,
                        gpu_memory=workload.gpu_memory_required,
                    )
                    resource_manager.release_resources(
                        request.node_id, reqs, request.task_id
                    )
                    cluster_state.sync_node_resources(request.node_id)
                    if status_enum == WorkloadStatus.COMPLETED:
                        scheduler.schedule_next(workload_service)
            return gpuflow_pb2.TaskStatusReportResponse(acknowledged=True)
        except Exception as e:
            logger.error(f"Error handling ReportTaskStatus for {request.task_id}: {e}")
            return gpuflow_pb2.TaskStatusReportResponse(acknowledged=False)

def serve_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    gpuflow_pb2_grpc.add_SchedulerServicer_to_server(SchedulerServicer(), server)
    server.add_insecure_port(f'[::]:{settings.grpc_port}')
    server.start()
    logger.info(f"gRPC Scheduler Server started on port {settings.grpc_port}")
    server.wait_for_termination()
