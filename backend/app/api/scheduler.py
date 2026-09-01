from fastapi import APIRouter, HTTPException

from backend.app.models.workload import WorkloadStatus
from backend.app.scheduler.scheduler import scheduler
from backend.app.services.workload_service import workload_service

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.post("/run-next")
def run_next_scheduler():
    decision = scheduler.schedule_next(workload_service)
    if decision is None:
        return {"message": "No queued workloads", "decision": None}
    return {"decision": decision}


@router.post("/run")
def run_scheduler():
    decisions = scheduler.schedule_all_queued(workload_service)
    return {"decisions": decisions, "count": len(decisions)}


@router.post("/workloads/{job_id}/schedule")
def schedule_workload(job_id: str):
    workload = workload_service.get_workload(job_id)
    if workload is None:
        raise HTTPException(status_code=404, detail=f"Workload {job_id} not found")
    if workload.status != WorkloadStatus.QUEUED:
        raise HTTPException(
            status_code=400,
            detail=f"Workload {job_id} is not QUEUED (status={workload.status.value})",
        )
    decision = scheduler.schedule_and_update(workload_service, workload)
    return {"decision": decision}
