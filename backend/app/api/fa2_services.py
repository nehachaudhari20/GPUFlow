from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.app.services.autoscaling import autoscaling_engine
from backend.app.services.function_registry import function_invocation_service
from backend.app.services.workload_service import workload_service
from backend.app.scheduler.scheduler import scheduler
from backend.app.storage.distributed_storage import distributed_storage
from backend.app.storage.replica_manager import replica_health

router = APIRouter(prefix="/fa2", tags=["FA2 Services"])


class FunctionInvokeRequest(BaseModel):
    function_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    cpu_required: float = 0.5
    ram_required: float = 0.5
    timeout: float = 30.0


@router.get("/storage/files")
def list_files() -> Dict[str, Any]:
    files = distributed_storage.list_files()
    return {"count": len(files), "files": files}


@router.post("/storage/files")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    data = await file.read()
    try:
        meta = distributed_storage.upload(file.filename or "upload.bin", data)
        return {"metadata": meta.__dict__}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/storage/files/{file_id}")
def download_file(file_id: str) -> Dict[str, Any]:
    try:
        content, meta = distributed_storage.download(file_id)
        import base64

        return {
            "file_id": file_id,
            "metadata": meta.__dict__,
            "content_base64": base64.b64encode(content).decode("ascii"),
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/storage/replicas/{file_id}")
def file_replicas(file_id: str) -> Dict[str, Any]:
    return replica_health(file_id)


@router.get("/functions")
def list_functions() -> Dict[str, List[str]]:
    return {"functions": function_invocation_service.list_functions()}


@router.post("/functions/invoke")
def invoke_function(body: FunctionInvokeRequest) -> Dict[str, Any]:
    try:
        return function_invocation_service.invoke(
            body.function_name,
            body.parameters,
            body.cpu_required,
            body.ram_required,
            body.timeout,
            scheduler,
            workload_service,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/functions/invocations/{invocation_id}")
def get_invocation(invocation_id: str) -> Dict[str, Any]:
    rec = function_invocation_service.get(invocation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Invocation not found")
    return rec


@router.get("/autoscaling/status")
def autoscaling_status() -> Dict[str, Any]:
    queued = len(workload_service.list_workloads())
    decision = autoscaling_engine.evaluate(queued_count=queued)
    return {"decision": decision.__dict__, "note": "Decision-only; does not launch EC2 instances."}


@router.get("/autoscaling/decisions")
def autoscaling_decisions() -> Dict[str, Any]:
    return {"decisions": autoscaling_engine.history()}
