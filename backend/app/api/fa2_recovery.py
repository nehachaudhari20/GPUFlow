from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from backend.app.config import settings
from backend.app.recovery.recovery_manager import recovery_manager
from backend.app.replication.replication_manager import replication_manager

router = APIRouter(prefix="/fa2", tags=["FA2 Recovery"])


@router.get("/recovery/summary")
def recovery_summary() -> Dict[str, Any]:
    return recovery_manager.summary()


@router.get("/recovery/history")
def recovery_history() -> Dict[str, Any]:
    history = recovery_manager.history()
    return {"count": len(history), "history": history}


@router.get("/recovery/jobs/{job_id}")
def recovery_job(job_id: str) -> Dict[str, Any]:
    detail = recovery_manager.job_detail(job_id)
    if not detail["attempts"] and not detail["retry_meta"]:
        wl_exists = detail.get("job_id")
        if wl_exists:
            pass
    return detail


@router.get("/replication/status")
def replication_status() -> Dict[str, Any]:
    return replication_manager.status()


@router.get("/replication/replicas")
def replication_replicas() -> Dict[str, Any]:
    return {"replicas": replication_manager.list_replicas(), "recent": replication_manager.recent()}


@router.post("/recovery/simulate-failure/{node_id}")
def simulate_failure_dev(node_id: str) -> Dict[str, Any]:
    if not settings.fa2_dev_controls_enabled:
        raise HTTPException(status_code=403, detail="Disabled in production")
    from backend.app.scheduler.cluster_state import cluster_state
    from backend.app.scheduler.resource_manager import resource_manager
    from backend.app.scheduler.scheduler import scheduler
    from backend.app.services.workload_service import workload_service

    cluster_state.quarantine(node_id, duration_s=45.0)
    resource_manager.mark_offline(node_id)
    from backend.app.coordination.coordinator import coordination_service

    leader = coordination_service.drop_member(node_id, reason="simulated_failure")
    jobs = recovery_manager.on_worker_failure(
        node_id, workload_service, scheduler, cluster_state, resource_manager
    )
    recovery_manager.process_retry_queue(workload_service, scheduler)
    scheduler.schedule_all_queued(workload_service)
    from backend.app.replication.replication_manager import replication_manager

    replication_manager.replicate(
        {
            "type": "worker_failure",
            "node_id": node_id,
            "interrupted_jobs": jobs,
        }
    )
    return {
        "node_id": node_id,
        "interrupted_jobs": jobs,
        "node_quarantined_s": 45,
        "new_coordinator": (leader or {}).get("coordinator_node_id"),
        "new_coordinator_election_id": (leader or {}).get("coordinator_election_id"),
    }
