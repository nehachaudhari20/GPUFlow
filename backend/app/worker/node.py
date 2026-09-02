import grpc
import time
import uuid
import socket
import threading
import logging
import psutil

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "protobufs"))

import gpuflow_pb2
import gpuflow_pb2_grpc
from backend.app.config import settings
from backend.app.core.logging import setup_logging
from backend.app.worker.worker_server import start_worker_server

logger = logging.getLogger(__name__)

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

class WorkerDaemon:
    def __init__(self):
        self.node_id = str(uuid.uuid4())
        self.hostname = os.environ.get("WORKER_HOSTNAME") or socket.gethostname()
        self.channel = None
        self.stub = None
        self.running = False
        self.grpc_port = find_free_port()
        self.server = None

        self.cpu_total = float(psutil.cpu_count(logical=True))
        self.ram_total = psutil.virtual_memory().total / (1024**3)

        if settings.simulate_gpus:
            self.gpu_total = settings.simulated_gpu_count
            self.gpu_memory_total = settings.simulated_gpu_memory_gb
        else:
            self.gpu_total = 0.0
            self.gpu_memory_total = 0.0

    def start(self, scheduler_address: str | None = None):
        address = scheduler_address or settings.scheduler_address
        self.scheduler_address = address
        self.server = start_worker_server(
            self.node_id, self.grpc_port, scheduler_address=address, daemon=self
        )

        self.channel = grpc.insecure_channel(address)
        self.stub = gpuflow_pb2_grpc.SchedulerStub(self.channel)

        while not self._register_with_scheduler():
            logger.warning(
                f"Scheduler not ready at {address}, retrying registration in 3s..."
            )
            self._ensure_scheduler_channel()
            time.sleep(3)

        threading.Thread(target=self._heartbeat_loop, daemon=True).start()

    def _ensure_scheduler_channel(self):
        if self.channel is not None:
            try:
                self.channel.close()
            except Exception:
                pass
        self.channel = grpc.insecure_channel(self.scheduler_address)
        self.stub = gpuflow_pb2_grpc.SchedulerStub(self.channel)

    def _register_with_scheduler(self) -> bool:
        try:
            req = gpuflow_pb2.RegisterNodeRequest(
                node_id=self.node_id,
                hostname=self.hostname,
                cpu_total=self.cpu_total,
                ram_total=self.ram_total,
                gpu_total=self.gpu_total,
                gpu_memory_total=self.gpu_memory_total,
                grpc_port=self.grpc_port,
            )
            res = self.stub.RegisterNode(req)
            if res.success:
                logger.info(f"Worker {self.node_id} successfully registered with scheduler.")
                self.running = True
                return True
            logger.error("Registration failed.")
        except Exception as e:
            logger.error(f"Could not connect to scheduler: {e}")
        return False

    def _heartbeat_loop(self):
        while self.running:
            try:
                cpu_util = psutil.cpu_percent(interval=None) / 100.0
                ram = psutil.virtual_memory()
                ram_util = ram.percent / 100.0
                cpu_avail = self.cpu_total * (1 - cpu_util)
                ram_avail = ram.available / (1024**3)

                gpu_util = 0.0
                if self.gpu_total > 0:
                    gpu_avail = self.gpu_total * (1 - gpu_util)
                    gpu_mem_avail = self.gpu_memory_total * (1 - gpu_util)
                else:
                    gpu_avail = 0.0
                    gpu_mem_avail = 0.0

                req = gpuflow_pb2.HeartbeatRequest(
                    node_id=self.node_id,
                    status="ONLINE",
                    timestamp=int(time.time() * 1000),
                    cpu_available=cpu_avail,
                    ram_available=ram_avail,
                    gpu_available=gpu_avail,
                    gpu_memory_available=gpu_mem_avail,
                    grpc_port=self.grpc_port,
                )
                self.stub.SendHeartbeat(req)
            except Exception as e:
                logger.error(f"Failed to send heartbeat: {e}")
                self._ensure_scheduler_channel()
                if self._register_with_scheduler():
                    logger.info(f"Worker {self.node_id} re-registered with scheduler.")

            time.sleep(settings.heartbeat_interval)

    def send_peer_message(self, target_host: str, target_port: int, msg_type: str, payload: str) -> str:
        """P2P direct worker-to-worker communication (Unit 2)."""
        target = f"{target_host}:{target_port}"
        try:
            with grpc.insecure_channel(target) as ch:
                stub = gpuflow_pb2_grpc.WorkerStub(ch)
                req = gpuflow_pb2.PeerMessageRequest(
                    sender_node_id=self.node_id,
                    target_node_id=target,
                    message_type=msg_type,
                    payload=payload,
                    timestamp=int(time.time() * 1000)
                )
                resp = stub.SendPeerMessage(req, timeout=3.0)
                return resp.reply_payload
        except Exception as e:
            logger.error(f"Failed to send peer message to {target}: {e}")
            return ""

    def stop(self):
        self.running = False
        if self.channel:
            self.channel.close()
        if self.server:
            self.server.stop(0)


def main():
    setup_logging()
    daemon = WorkerDaemon()
    daemon.start()
    logger.info(
        f"Worker node {daemon.node_id} running on port {daemon.grpc_port}. Press Ctrl+C to stop."
    )
    try:
        while daemon.running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping worker...")
        daemon.stop()


if __name__ == "__main__":
    main()
