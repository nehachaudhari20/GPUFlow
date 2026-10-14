from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import time

from backend.app.models.workload import (
    Workload,
    WorkloadCreate,
    WorkloadStatus,
)
from backend.app.scheduler.scheduler import scheduler
from backend.app.services.workload_service import workload_service

router = APIRouter(prefix="/workloads", tags=["workloads"])


class WorkloadStatusUpdate(BaseModel):
    status: WorkloadStatus
    assigned_node: Optional[str] = None


@router.post("", response_model=Workload, status_code=201)
def create_workload(
    payload: WorkloadCreate,
    auto_schedule: bool = Query(default=True, description="Immediately schedule if a worker is free"),
):
    workload = workload_service.create_workload(payload)
    if auto_schedule:
        # Always try to place onto a free worker. Priority only orders the
        # queue; a RUNNING job on one node must not block the other nodes.
        for attempt in range(10):
            scheduler.schedule_all_queued(workload_service)
            updated = workload_service.get_workload(workload.job_id)
            if updated and updated.status != WorkloadStatus.QUEUED:
                return updated
            still_running = any(
                w.status == WorkloadStatus.RUNNING
                for w in workload_service.list_workloads()
                if w.job_id != workload.job_id
            )
            if still_running:
                break
            if attempt < 9:
                time.sleep(1)
    updated = workload_service.get_workload(workload.job_id)
    return updated or workload


@router.get("", response_model=dict)
def list_workloads(status: WorkloadStatus | None = Query(default=None)):
    workloads = workload_service.list_workloads(status=status)
    return {"workloads": workloads, "count": len(workloads)}


@router.get("/{job_id}", response_model=Workload)
def get_workload(job_id: str):
    workload = workload_service.get_workload(job_id)
    if workload is None:
        raise HTTPException(status_code=404, detail=f"Workload {job_id} not found")
    return workload


@router.patch("/{job_id}/status", response_model=Workload)
def update_workload_status(job_id: str, payload: WorkloadStatusUpdate):
    try:
        return workload_service.update_status(
            job_id, payload.status, assigned_node=payload.assigned_node
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Workload {job_id} not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
