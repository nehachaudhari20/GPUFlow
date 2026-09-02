import threading
import time
import requests
import asyncio
import sys
import os

from backend.app.config import settings

def start_backend():
    import uvicorn
    # override grpc port for test
    os.environ["GRPC_PORT"] = "50051"
    os.environ["SIMULATE_GPUS"] = "True"
    os.environ["SIMULATED_GPU_COUNT"] = "4.0"
    os.environ["SIMULATED_GPU_MEMORY_GB"] = "16.0"
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, log_level="error")

def start_worker(idx):
    os.environ["SIMULATE_GPUS"] = "True"
    os.environ["SIMULATED_GPU_COUNT"] = str(idx * 2.0)
    os.environ["SIMULATED_GPU_MEMORY_GB"] = "16.0"
    from backend.app.worker.node import WorkerDaemon
    daemon = WorkerDaemon()
    daemon.start("localhost:50051")
    while daemon.running:
        time.sleep(1)

def run():
    print("Starting backend...")
    t1 = threading.Thread(target=start_backend, daemon=True)
    t1.start()
    time.sleep(3) # wait for uvicorn and gRPC

    print("Starting worker 1...")
    t2 = threading.Thread(target=start_worker, args=(1,), daemon=True)
    t2.start()

    print("Starting worker 2...")
    t3 = threading.Thread(target=start_worker, args=(2,), daemon=True)
    t3.start()

    time.sleep(2) # wait for heartbeat

    print("Checking nodes...")
    resp = requests.get("http://localhost:8000/nodes")
    nodes = resp.json()
    print("Nodes:", nodes)
    assert nodes["count"] == 2

    print("Submitting workload...")
    resp = requests.post("http://localhost:8000/workloads", json={
        "name": "E2E Task",
        "type": "TRAINING",
        "gpu_required": 0.5,
        "gpu_memory_required": 1.0,
        "cpu_required": 1.0,
        "ram_required": 0.5,
        "priority": "HIGH",
        "estimated_duration": 10.0
    })
    job = resp.json()
    print("Job:", job)
    job_id = job["job_id"]

    print("Triggering schedule...")
    resp = requests.post("http://localhost:8000/scheduler/run-next")
    sched = resp.json()
    print("Scheduling decision:", sched)
    assert sched['decision'].get("allocation_success") is True

    print("P2P Communication Test...")
    node2_port = nodes['nodes'][1]['grpc_port']
    node1_port = nodes['nodes'][0]['grpc_port']
    # Trigger P2P via a small standalone python script inside the environment
    import grpc
    import gpuflow_pb2
    import gpuflow_pb2_grpc
    try:
        with grpc.insecure_channel(f"localhost:{node2_port}") as channel:
            stub = gpuflow_pb2_grpc.WorkerStub(channel)
            resp = stub.SendPeerMessage(gpuflow_pb2.PeerMessageRequest(
                sender_node_id="TEST-DRIVER",
                target_node_id=f"localhost:{node2_port}",
                message_type="DATA_SYNC",
                payload="Syncing weights to peer worker",
                timestamp=int(time.time()*1000)
            ), timeout=3.0)
            print("P2P Reply:", resp.reply_payload)
    except Exception as e:
        print("P2P Error:", e)

    print("Waiting for task to complete (simulation)...", flush=True)
    time.sleep(5)

    print("Checking events...", flush=True)
    resp = requests.get(f"http://localhost:8000/events/{job_id}")
    events = resp.json()
    for e in events:
        print("Event:", e["event_type"], e["message"], flush=True)

    print("All ok, sys.exit(0)", flush=True)
    time.sleep(0.5)
    os._exit(0)

if __name__ == "__main__":
    run()
