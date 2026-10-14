import threading
import time
from fastapi import FastAPI, HTTPException

from backend.app.core.logging import setup_logging
from backend.app.config import settings
from backend.app.scheduler.cluster_state import cluster_state
from backend.app.scheduler.resource_manager import resource_manager
from backend.app.communication.scheduler_server import serve_grpc
from backend.app.api.workloads import router as workloads_router
from backend.app.api.scheduler import router as scheduler_router
from backend.app.api.events import router as events_router
from backend.app.api.admin import router as admin_router
from backend.app.api.websocket import router as ws_router, setup_event_broadcaster
import asyncio

setup_logging()

app = FastAPI(title="GPUFlow", description="Distributed GPU-Aware Workload Scheduling")
app.include_router(workloads_router)
app.include_router(scheduler_router)
app.include_router(events_router)
app.include_router(admin_router)
app.include_router(ws_router)


def timeout_checker():
    while True:
        cluster_state.check_timeouts()
        time.sleep(1)


@app.on_event("startup")
def startup_event():
    loop = asyncio.get_event_loop()
    setup_event_broadcaster(loop)

    grpc_thread = threading.Thread(target=serve_grpc, daemon=True)
    grpc_thread.start()

    checker_thread = threading.Thread(target=timeout_checker, daemon=True)
    checker_thread.start()


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "GPUFlow Backend", "version": "1.0.0"}


@app.get("/nodes")
def get_nodes():
    nodes = cluster_state.get_all_nodes()
    return {"nodes": nodes, "count": len(nodes)}


@app.get("/nodes/{node_id}")
def get_node(node_id: str):
    node = cluster_state.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return node


@app.get("/failure-events")
def get_failure_events():
    events = cluster_state.get_failure_events()
    return {"events": events, "count": len(events)}


@app.get("/cluster")
@app.get("/resources/cluster")
def get_cluster_resources():
    cluster = resource_manager.get_cluster_resources()
    payload = cluster.model_dump()
    payload["cpu_only_mode"] = settings.cpu_only_mode
    payload["simulate_gpus"] = settings.simulate_gpus
    return payload


@app.get("/resources/nodes/{node_id}")
def get_node_resources(node_id: str):
    resources = resource_manager.get_node_resources(node_id)
    if resources is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return resources
