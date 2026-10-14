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
from backend.app.events.event_manager import EventType
from backend.app.synchronization.process_sync import get_coordinator_sync
from backend.app.synchronization.grpc_metadata import vector_from_proto, apply_vector_to_proto
from backend.app.synchronization.event_sync import log_event_with_clocks
from backend.app.synchronization.clock_sync import clock_sync_registry, CristianSyncSample
from backend.app.coordination.coordinator import coordination_service
from backend.app.synchronization.event_sync import log_synchronized_event

logger = logging.getLogger(__name__)


class SchedulerServicer(gpuflow_pb2_grpc.SchedulerServicer):
    def RegisterNode(self, request, context):
        coord = get_coordinator_sync()
        remote_vector = vector_from_proto(request.vector_clock)
        if request.lamport_time:
            lamport, vector = coord.on_receive(int(request.lamport_time), remote_vector)
        else:
            lamport, vector = coord.on_local_event()

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
        cluster_state.register_node(node, lamport=lamport, vector=vector)
        election_id = int(request.election_id) if request.election_id else 0
        coordination_service.register_member(
            request.node_id, election_id, request.hostname, request.grpc_port
        )
        peers = coordination_service.list_members()
        if election_id > coordination_service.get_leader().get("coordinator_election_id", -1):
            coordination_service.report_coordinator(request.node_id, election_id)

        resp = gpuflow_pb2.RegisterNodeResponse(
            success=True,
            message="Node registered successfully",
            membership_epoch=coordination_service.membership_epoch(),
        )
        for p in peers:
            resp.peers.add(
                node_id=p["node_id"],
                election_id=int(p.get("election_id", 0)),
                hostname=p["hostname"],
                grpc_port=int(p["grpc_port"]),
            )
        return resp

    def SendHeartbeat(self, request, context):
        server_receive_ms = time.time() * 1000.0
        coord = get_coordinator_sync()
        remote_vector = vector_from_proto(request.vector_clock)

        if request.lamport_time:
            log_event_with_clocks(
                EventType.HEARTBEAT_SENT,
                int(request.lamport_time),
                remote_vector,
                source="WORKER",
                destination="SCHEDULER",
                node_id=request.node_id,
                message=f"Heartbeat sent from {request.node_id}",
            )
            lamport, vector = coord.on_receive(int(request.lamport_time), remote_vector)
        else:
            lamport, vector = coord.on_local_event()

        cluster_state.update_heartbeat(
            node_id=request.node_id,
            status=request.status,
            timestamp=request.timestamp / 1000.0,
            cpu_avail=request.cpu_available,
            ram_avail=request.ram_available,
            gpu_avail=request.gpu_available,
            gpu_mem_avail=request.gpu_memory_available,
            grpc_port=request.grpc_port,
            lamport=lamport,
            vector=vector,
        )

        server_reply_ms = time.time() * 1000.0
        if request.cristian_client_request_ms and request.cristian_client_response_ms:
            clock_sync_registry.record_cristian_sample(
                CristianSyncSample(
                    node_id=request.node_id,
                    client_request_ms=float(request.cristian_client_request_ms),
                    client_response_ms=float(request.cristian_client_response_ms),
                    server_receive_ms=server_receive_ms,
                    server_reply_ms=server_reply_ms,
                )
            )
        elif request.client_wall_time_ms:
            clock_sync_registry.record_simple_sync(
                node_id=request.node_id,
                worker_wall_ms=float(request.client_wall_time_ms),
                server_receive_ms=server_receive_ms,
                server_reply_ms=server_reply_ms,
            )

        if request.beacon_sequence:
            coordination_service.ingest_beacon(
                node_id=request.node_id,
                sequence=int(request.beacon_sequence),
                coordinator_node_id=request.worker_coordinator_id or None,
                membership_epoch=int(request.membership_epoch or coordination_service.membership_epoch()),
                lamport_timestamp=int(request.lamport_time or lamport),
                vector_clock=remote_vector,
                cpu_available=request.cpu_available,
                ram_available=request.ram_available,
                status=request.status,
            )
            if request.worker_coordinator_id and request.worker_election_id:
                coordination_service.report_coordinator(
                    request.worker_coordinator_id, int(request.worker_election_id)
                )

        resp_lamport, resp_vector = coord.on_send()
        response = gpuflow_pb2.HeartbeatResponse(
            acknowledged=True,
            server_time_ms=int(server_reply_ms),
            lamport_time=resp_lamport,
        )
        apply_vector_to_proto(response.vector_clock, resp_vector)
        return response

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
            coord = get_coordinator_sync()
            remote_vector = vector_from_proto(request.vector_clock)
            if request.lamport_time:
                coord.on_receive(int(request.lamport_time), remote_vector)

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
