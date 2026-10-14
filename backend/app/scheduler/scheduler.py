import threading
import time
from typing import List, Optional

from backend.app.models.resources import ResourceRequirements
from backend.app.models.workload import Workload, WorkloadStatus
from backend.app.scheduler.cluster_state import ClusterState, cluster_state
from backend.app.scheduler.node_filter import NodeFilter
from backend.app.scheduler.node_scorer import NodeScorer
from backend.app.scheduler.resource_manager import ResourceManager, resource_manager
from backend.app.scheduler.scheduling_decision import (
    CandidateNode,
    RejectedNode,
    SchedulingDecision,
)
from backend.app.scheduler.scheduling_policy import SchedulingPolicy
from backend.app.services.workload_service import WorkloadService
from backend.app.communication.worker_client import WorkerClient
from backend.app.events.event_manager import event_manager, EventType
import logging

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(
        self,
        resource_mgr: ResourceManager,
        cluster: ClusterState,
        policy: SchedulingPolicy | None = None,
        node_filter: NodeFilter | None = None,
        node_scorer: NodeScorer | None = None,
    ):
        self._resource_manager = resource_mgr
        self._cluster_state = cluster
        self._policy = policy or SchedulingPolicy.from_settings()
        self._node_filter = node_filter or NodeFilter()
        self._node_scorer = node_scorer or NodeScorer(self._policy)
        self._lock = threading.Lock()

    def schedule_workload(self, workload: Workload) -> SchedulingDecision:
        requirements = ResourceRequirements(
            cpu=workload.cpu_required,
            ram=workload.ram_required,
            gpu=workload.gpu_required,
            gpu_memory=workload.gpu_memory_required,
        )

        cluster = self._resource_manager.get_cluster_resources()
        rejected_nodes: List[RejectedNode] = []
        candidate_nodes: List[CandidateNode] = []

        for node in cluster.nodes:
            if node.running_workloads:
                rejected_nodes.append(
                    RejectedNode(
                        node_id=node.node_id,
                        hostname=node.hostname,
                        reasons=[
                            f"Node busy running {len(node.running_workloads)} workload(s)"
                        ],
                    )
                )
                continue

            eligible, reasons = self._node_filter.evaluate(node, requirements)
            if eligible:
                scores = self._node_scorer.score(node, cluster.nodes)
                candidate_nodes.append(
                    CandidateNode(
                        node_id=node.node_id,
                        hostname=node.hostname,
                        scores=scores,
                    )
                )
            else:
                rejected_nodes.append(
                    RejectedNode(
                        node_id=node.node_id,
                        hostname=node.hostname,
                        reasons=reasons,
                    )
                )

        if not candidate_nodes:
            reason = self._build_no_candidate_reason(rejected_nodes, requirements)
            logger.info(f"Job {workload.job_id} kept QUEUED: {reason}")
            return SchedulingDecision(
                job_id=workload.job_id,
                workload_name=workload.name,
                candidate_nodes=[],
                rejected_nodes=rejected_nodes,
                selected_node=None,
                allocation_success=False,
                kept_queued=True,
                reason=reason,
                scheduling_timestamp=time.time(),
            )

        candidate_nodes.sort(key=lambda c: c.scores.total, reverse=True)
        best = candidate_nodes[0]

        with self._lock:
            allocated = self._resource_manager.allocate_resources(
                best.node_id, requirements, workload.job_id
            )

        if not allocated:
            reason = (
                f"Resource allocation failed on selected node {best.node_id} "
                "(resources may have changed)"
            )
            logger.warning(f"Job {workload.job_id}: {reason}")
            return SchedulingDecision(
                job_id=workload.job_id,
                workload_name=workload.name,
                candidate_nodes=candidate_nodes,
                rejected_nodes=rejected_nodes,
                selected_node=best.node_id,
                allocation_success=False,
                kept_queued=True,
                reason=reason,
                scheduling_timestamp=time.time(),
            )

        self._cluster_state.sync_node_resources(best.node_id)
        logger.info(
            f"Job {workload.job_id} scheduled on {best.node_id} "
            f"(score={best.scores.total})"
        )

        event_manager.log_event(
            event_type=EventType.NODE_SELECTED,
            source="SCHEDULER",
            job_id=workload.job_id,
            node_id=best.node_id,
            message=f"Node {best.node_id} selected with score {best.scores.total}",
        )
        event_manager.log_event(
            event_type=EventType.RESOURCE_ALLOCATED,
            source="SCHEDULER",
            job_id=workload.job_id,
            node_id=best.node_id,
            message=f"Resources allocated on {best.node_id}",
        )

        return SchedulingDecision(
            job_id=workload.job_id,
            workload_name=workload.name,
            candidate_nodes=candidate_nodes,
            rejected_nodes=rejected_nodes,
            selected_node=best.node_id,
            allocation_success=True,
            kept_queued=False,
            scheduling_timestamp=time.time(),
        )

    def schedule_next(self, workload_service: WorkloadService) -> Optional[SchedulingDecision]:
        workload = workload_service.queue.peek_next()
        if workload is None:
            return None
        return self.schedule_and_update(workload_service, workload)

    def schedule_and_update(
        self, workload_service: WorkloadService, workload: Workload
    ) -> SchedulingDecision:
        if workload.status != WorkloadStatus.QUEUED:
            return SchedulingDecision(
                job_id=workload.job_id,
                workload_name=workload.name,
                kept_queued=False,
                allocation_success=False,
                reason=f"Workload is not QUEUED (status={workload.status.value})",
                scheduling_timestamp=time.time(),
            )

        decision = self.schedule_workload(workload)

        if decision.allocation_success and decision.selected_node:
            node = self._cluster_state.get_node(decision.selected_node)
            assigned_ok = False
            if node and node.grpc_port > 0:
                client = WorkerClient(node.hostname, node.grpc_port)
                assigned_ok = client.assign_task(workload)
            else:
                # If node has no valid gRPC port (e.g. mock/test environment without server), assume OK for backward compatibility
                assigned_ok = True

            if assigned_ok:
                workload_service.update_status(
                    workload.job_id,
                    WorkloadStatus.SCHEDULED,
                    assigned_node=decision.selected_node,
                )
                workload_service.update_status(
                    workload.job_id,
                    WorkloadStatus.RUNNING,
                    assigned_node=decision.selected_node,
                )
            else:
                requirements = ResourceRequirements(
                    cpu=workload.cpu_required,
                    ram=workload.ram_required,
                    gpu=workload.gpu_required,
                    gpu_memory=workload.gpu_memory_required,
                )
                self._resource_manager.release_resources(
                    decision.selected_node, requirements, workload.job_id
                )
                self._cluster_state.sync_node_resources(decision.selected_node)
                decision.allocation_success = False
                decision.kept_queued = True
                target = f"{node.hostname}:{node.grpc_port}" if node else decision.selected_node
                decision.reason = (
                    f"Cannot reach worker at {target} to assign task — "
                    f"run scripts/start-laptop-control.ps1 (SSH tunnels) or open AWS "
                    f"security group inbound port 50052 from your laptop IP"
                )
        return decision

    @staticmethod
    def _build_no_candidate_reason(
        rejected_nodes: List[RejectedNode],
        requirements: ResourceRequirements,
    ) -> str:
        if not rejected_nodes:
            return (
                "No worker nodes registered — start AWS workers or run "
                "docker compose workers and wait ~15s"
            )
        if requirements.gpu > 0 or requirements.gpu_memory > 0:
            all_no_gpu = all(
                any("Insufficient GPU" in r for r in node.reasons)
                for node in rejected_nodes
            )
            if all_no_gpu:
                return (
                    "Cluster is CPU-only (0 GPUs on workers). Submit with GPU=0 and "
                    "VRAM=0, using CPU and RAM only."
                )
        busy = [n for n in rejected_nodes if any("busy" in r.lower() for r in n.reasons)]
        if busy and len(busy) == len(rejected_nodes):
            return "All workers are busy running other jobs — job kept in queue"
        return "No eligible nodes satisfy workload resource requirements"

    def schedule_all_queued(
        self, workload_service: WorkloadService
    ) -> List[SchedulingDecision]:
        decisions: List[SchedulingDecision] = []
        while True:
            workload = workload_service.queue.peek_next()
            if workload is None:
                break
            decision = self.schedule_and_update(workload_service, workload)
            decisions.append(decision)
            if decision.kept_queued:
                break
        return decisions


scheduler = Scheduler(resource_manager, cluster_state)
