from fastapi import APIRouter
from typing import List, Optional
from backend.app.events.event_manager import event_manager, SystemEvent

router = APIRouter(prefix="/events", tags=["events"])

@router.get("", response_model=List[SystemEvent])
def get_events(job_id: Optional[str] = None, node_id: Optional[str] = None):
    return event_manager.get_events(job_id=job_id, node_id=node_id)

@router.get("/{job_id}", response_model=List[SystemEvent])
def get_events_for_job(job_id: str):
    return event_manager.get_events(job_id=job_id)
