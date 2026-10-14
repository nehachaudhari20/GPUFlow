from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.app.events.event_manager import event_manager
from backend.app.synchronization.clock_sync import clock_sync_registry
from backend.app.synchronization.global_snapshot import global_snapshot_service
from backend.app.synchronization.process_sync import get_coordinator_sync
from backend.app.synchronization.vector_clock import VectorClock

router = APIRouter(prefix="/fa2", tags=["FA2 Synchronization"])


@router.get("/synchronization/clocks")
def get_clocks() -> Dict[str, Any]:
    coordinator = get_coordinator_sync()
    from backend.app.coordination.coordinator import coordination_service
    from backend.app.synchronization.clock_sync import clock_sync_registry

    offsets = {o.node_id: o for o in clock_sync_registry.list_offsets()}
    beacons = {b["node_id"]: b for b in coordination_service._beacons.list_beacons()}
    workers = []
    for m in coordination_service.list_members():
        nid = m["node_id"]
        off = offsets.get(nid)
        beacon = beacons.get(nid, {})
        workers.append(
            {
                "node_id": nid,
                "hostname": m.get("hostname"),
                "election_id": m.get("election_id"),
                "lamport_time": beacon.get("lamport_timestamp"),
                "vector_clock": beacon.get("vector_clock") or {},
                "offset_ms": getattr(off, "measured_offset_ms", None) if off else None,
                "rtt_ms": getattr(off, "round_trip_time_ms", None) if off else None,
                "sync_status": getattr(off, "synchronization_status", None) if off else None,
            }
        )
    return {
        "coordinator": {
            "node_id": coordinator.node_id,
            "lamport_time": coordinator.lamport.get_time(),
            "vector_clock": coordinator.vector.snapshot(),
        },
        "workers": workers,
        "note": "Lamport/vector clocks order events; Cristian offsets estimate skew vs scheduler (do not change OS time).",
    }


@router.get("/synchronization/events")
def get_synchronized_events(limit: int = Query(100, ge=1, le=500)) -> Dict[str, Any]:
    events = event_manager.get_events(limit=limit)
    return {
        "count": len(events),
        "events": [e.model_dump() for e in events],
    }


@router.get("/synchronization/causality")
def compare_event_causality(
    event_a_id: str = Query(..., description="First event_id"),
    event_b_id: str = Query(..., description="Second event_id"),
) -> Dict[str, Any]:
    events = {e.event_id: e for e in event_manager.get_events(limit=500)}
    event_a = events.get(event_a_id)
    event_b = events.get(event_b_id)
    if event_a is None or event_b is None:
        raise HTTPException(status_code=404, detail="One or both events not found")
    if not event_a.vector_clock or not event_b.vector_clock:
        raise HTTPException(
            status_code=400,
            detail="Both events must include vector clocks for causality analysis",
        )
    relation = VectorClock.compare(event_a.vector_clock, event_b.vector_clock)
    return {
        "event_a_id": event_a_id,
        "event_b_id": event_b_id,
        "relation": relation,
        "happens_before": relation == "before",
        "concurrent": relation == "concurrent",
        "vector_a": event_a.vector_clock,
        "vector_b": event_b.vector_clock,
    }


@router.get("/synchronization/offsets")
def get_clock_offsets() -> Dict[str, Any]:
    offsets = clock_sync_registry.list_offsets()
    return {"count": len(offsets), "offsets": [o.__dict__ for o in offsets]}


@router.get("/global-state/snapshots")
def list_snapshots(limit: int = Query(20, ge=1, le=50)) -> Dict[str, Any]:
    snapshots = global_snapshot_service.list_snapshots(limit=limit)
    return {"count": len(snapshots), "snapshots": snapshots}


@router.get("/global-state/latest")
def latest_snapshot() -> Dict[str, Any]:
    snapshot = global_snapshot_service.latest()
    if snapshot is None:
        snapshot = global_snapshot_service.capture()
    return snapshot
