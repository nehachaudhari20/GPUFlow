from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from backend.app.config import settings
from backend.app.coordination.coordinator import coordination_service
from backend.app.coordination.distributed_lock import distributed_lock_coordinator

router = APIRouter(prefix="/fa2/coordination", tags=["FA2 Coordination"])


def _dev_only() -> None:
    if not settings.fa2_dev_controls_enabled:
        raise HTTPException(
            status_code=403,
            detail="Coordination control endpoints disabled in production",
        )


@router.get("/leader")
def get_leader() -> Dict[str, Any]:
    return coordination_service.get_leader()


@router.get("/elections")
def list_elections() -> Dict[str, Any]:
    elections = coordination_service.list_elections()
    return {"count": len(elections), "elections": elections}


@router.get("/members")
def list_members() -> Dict[str, Any]:
    members = coordination_service.list_members()
    return {"count": len(members), "members": members, "epoch": coordination_service.membership_epoch()}


@router.get("/locks")
def list_locks() -> Dict[str, Any]:
    return distributed_lock_coordinator.snapshot()


@router.get("/beacons")
def list_beacons() -> Dict[str, Any]:
    return {
        "beacons": coordination_service._beacons.list_beacons(),
        "events": coordination_service._beacons.list_events(),
    }


@router.get("/deadlocks")
def detect_deadlocks() -> Dict[str, Any]:
    report = coordination_service._deadlock.detect()
    return {
        "deadlock_detected": report.deadlock_detected,
        "cycle_participants": report.cycle_participants,
        "resources_involved": report.resources_involved,
        "detection_timestamp": report.detection_timestamp,
        "edges": report.edges,
        "history": coordination_service._deadlock.history(),
    }


@router.post("/elections/trigger")
def trigger_election_dev() -> Dict[str, Any]:
    _dev_only()
    return {"message": "Election trigger is worker-initiated; report ingested on next heartbeat."}
