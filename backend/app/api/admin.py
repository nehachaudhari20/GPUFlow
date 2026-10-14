import logging

from fastapi import APIRouter

from backend.app.events.event_manager import event_manager
from backend.app.scheduler.cluster_state import cluster_state
from backend.app.scheduler.resource_manager import resource_manager
from backend.app.services.workload_service import workload_service
from backend.app.synchronization.clock_sync import clock_sync_registry
from backend.app.synchronization.global_snapshot import global_snapshot_service
from backend.app.synchronization.process_sync import reset_sync_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reset")
def reset_platform():
    """Clear all workloads, events, and cluster scheduling state for a fresh demo."""
    workloads_deleted = workload_service.clear_all_workloads()
    event_manager.clear_all()
    cluster_state.reset()
    resource_manager.reset()
    clock_sync_registry.clear()
    global_snapshot_service.clear()
    reset_sync_registry()

    logger.info(f"Platform reset: removed {workloads_deleted} workload(s)")

    return {
        "message": "Platform reset complete. Workers will re-register automatically.",
        "workloads_deleted": workloads_deleted,
        "nodes_cleared": True,
        "events_cleared": True,
    }
