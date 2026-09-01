from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.models.workload import (
    Workload,
    WorkloadCreate,
    WorkloadStatus,
)
from backend.app.services.workload_service import workload_service

router = APIRouter(prefix="/workloads", tags=["workloads"])


class WorkloadStatusUpdate(BaseModel):
    status: WorkloadStatus
    assigned_node: Optional[str] = None


@router.post("", response_model=Workload, status_code=201)
def create_workload(payload: WorkloadCreate):
    return workload_service.create_workload(payload)


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
