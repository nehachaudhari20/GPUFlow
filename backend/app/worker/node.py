from __future__ import annotations

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
from backend.app.worker.hardware_probe import probe_host_resources
from backend.app.synchronization.process_sync import get_worker_sync
from backend.app.synchronization.grpc_metadata import apply_vector_to_proto
from backend.app.worker.coordination_worker import WorkerCoordinationRuntime

logger = logging.getLogger(__name__)

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

class WorkerDaemon:
    def __init__(self):
        self.node_id = str(uuid.uuid4())
        self.worker_name = os.environ.get("WORKER_NAME", "")
        self.hostname = os.environ.get("WORKER_HOSTNAME") or socket.gethostname()
        self.channel = None
        self.stub = None
        self.running = False

        configured_port = int(
            os.environ.get("WORKER_GRPC_PORT", settings.worker_grpc_port or 0)
        )
        self.listen_port = configured_port if configured_port > 0 else find_free_port()
        # Port scheduler uses to call back (may differ via SSH tunnel on laptop setup)
        self.advertise_port = int(
            os.environ.get("WORKER_ADVERTISE_GRPC_PORT", self.listen_port)
        )
        self.grpc_port = self.listen_port
        self.server = None

        resources = probe_host_resources(
            simulate_gpus=settings.simulate_gpus,
            simulated_gpu_count=settings.simulated_gpu_count,
            simulated_gpu_memory_gb=settings.simulated_gpu_memory_gb,
        )
        self.cpu_total = resources.cpu_total
        self.ram_total = resources.ram_total_gb
        self.gpu_total = resources.gpu_total
        self.gpu_memory_total = resources.gpu_memory_total_gb
        self.resource_source = resources.source
        self._cristian_prev_request_ms: float | None = None
        self._cristian_prev_response_ms: float | None = None
        self.coordination = WorkerCoordinationRuntime(
            self.node_id, self.worker_name, self.hostname
        )

    def start(self, scheduler_address: str | None = None):
        address = scheduler_address or settings.scheduler_address
        self.scheduler_address = address
        self.server = start_worker_server(
            self.node_id, self.listen_port, scheduler_address=address, daemon=self
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
            sync = get_worker_sync(self.node_id)
            lamport, vector = sync.on_send()
            req = gpuflow_pb2.RegisterNodeRequest(
                node_id=self.node_id,
                hostname=self.hostname,
                cpu_total=self.cpu_total,
                ram_total=self.ram_total,
                gpu_total=self.gpu_total,
                gpu_memory_total=self.gpu_memory_total,
                grpc_port=self.advertise_port,
                lamport_time=lamport,
                election_id=self.coordination.election_id,
            )
            apply_vector_to_proto(req.vector_clock, vector)
            res = self.stub.RegisterNode(req)
            if res.success:
                self.coordination.on_register(res.peers, res.membership_epoch or 1)
                label = self.worker_name or self.hostname
                logger.info(
                    f"Worker {self.node_id} ({label}) registered — "
                    f"cpu={self.cpu_total} ram={self.ram_total:.1f}GB "
                    f"gpu={self.gpu_total} source={self.resource_source} "
                    f"listen={self.listen_port} advertise={self.hostname}:{self.advertise_port}"
                )
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

                sync = get_worker_sync(self.node_id)
                client_wall_ms = int(time.time() * 1000)
                lamport, vector = sync.on_send()
                coord_id, coord_eid = self.coordination.coordinator_report()
                req = gpuflow_pb2.HeartbeatRequest(
                    node_id=self.node_id,
                    status="ONLINE",
                    timestamp=client_wall_ms,
                    cpu_available=cpu_avail,
                    ram_available=ram_avail,
                    gpu_available=gpu_avail,
                    gpu_memory_available=gpu_mem_avail,
                    grpc_port=self.advertise_port,
                    lamport_time=lamport,
                    client_wall_time_ms=client_wall_ms,
                    beacon_sequence=self.coordination.next_beacon_sequence(),
                    worker_coordinator_id=coord_id,
                    worker_election_id=coord_eid,
                    membership_epoch=self.coordination._membership_epoch,
                )
                apply_vector_to_proto(req.vector_clock, vector)
                if (
                    self._cristian_prev_request_ms is not None
                    and self._cristian_prev_response_ms is not None
                ):
                    req.cristian_client_request_ms = int(self._cristian_prev_request_ms)
                    req.cristian_client_response_ms = int(
                        self._cristian_prev_response_ms
                    )
                send_started = time.time() * 1000
                resp = self.stub.SendHeartbeat(req)
                send_finished = time.time() * 1000
                self._cristian_prev_request_ms = send_started
                self._cristian_prev_response_ms = send_finished
                if resp.lamport_time:
                    sync.on_receive(
                        int(resp.lamport_time),
                        {k: int(v) for k, v in resp.vector_clock.items()},
                    )
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
    label = daemon.worker_name or daemon.hostname
    logger.info(
        f"Worker {label} ({daemon.node_id}) listening on 0.0.0.0:{daemon.listen_port} "
        f"advertised as {daemon.hostname}:{daemon.advertise_port} "
        f"[{daemon.resource_source}]. Press Ctrl+C to stop."
    )
    try:
        while daemon.running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping worker...")
        daemon.stop()


if __name__ == "__main__":
    main()
