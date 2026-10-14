from __future__ import annotations

import logging
import re
import threading
import time
from typing import Dict, Optional

from backend.app.coordination.bully_election import BullyElectionManager
from backend.app.coordination.distributed_lock import RicartAgrawalaLockManager
from backend.app.synchronization.process_sync import get_worker_sync

logger = logging.getLogger(__name__)


def parse_election_id(worker_name: str, hostname: str) -> int:
    import os

    env = os.environ.get("WORKER_ELECTION_ID")
    if env and env.isdigit():
        return int(env)
    for label in (worker_name, hostname):
        match = re.search(r"(\d+)\s*$", label or "")
        if match:
            return int(match.group(1))
    return 1


class WorkerCoordinationRuntime:
    def __init__(self, node_id: str, worker_name: str, hostname: str) -> None:
        self.node_id = node_id
        self.election_id = parse_election_id(worker_name, hostname)
        sync = get_worker_sync(node_id)
        self._beacon_seq = 0
        self._membership_epoch = 1
        self._lock = threading.Lock()

        def send(host: str, port: int, msg_type: str, payload: str) -> bool:
            if not host or port <= 0:
                return False
            try:
                import grpc
                import gpuflow_pb2
                import gpuflow_pb2_grpc

                target = f"{host}:{port}"
                with grpc.insecure_channel(target) as ch:
                    stub = gpuflow_pb2_grpc.WorkerStub(ch)
                    lp, vc = sync.on_send()
                    req = gpuflow_pb2.PeerMessageRequest(
                        sender_node_id=node_id,
                        target_node_id=target,
                        message_type=msg_type,
                        payload=payload,
                        timestamp=int(time.time() * 1000),
                        lamport_time=lp,
                    )
                    for k, v in vc.items():
                        req.vector_clock[k] = v
                    stub.SendPeerMessage(req, timeout=2.0)
                return True
            except Exception as exc:
                logger.debug("Peer send failed: %s", exc)
                return False

        self.election = BullyElectionManager(node_id, self.election_id, send_message=send)

        def send_reply(target_node: str, request_id: str, timestamp: int) -> None:
            host, port = self.election._peer_targets().get(target_node, ("", 0))
            send(host, port, "LOCK_REPLY", f"LOCK_REPLY|{request_id}|{timestamp}")

        self.lock_manager = RicartAgrawalaLockManager(
            node_id,
            lamport_provider=sync.lamport.get_time,
            lamport_tick=lambda: sync.on_local_event()[0],
            send_reply=send_reply,
        )

    def update_peers_from_proto(self, peers) -> None:
        peer_ids: Dict[str, int] = {}
        targets: Dict[str, tuple[str, int]] = {}
        for p in peers:
            if p.node_id == self.node_id:
                continue
            peer_ids[p.node_id] = int(p.election_id)
            targets[p.node_id] = (p.hostname, int(p.grpc_port))
        self.election.set_peers(peer_ids)
        self.election.set_peer_targets(targets)
        self.lock_manager.set_membership(
            self._membership_epoch, set(peer_ids.keys()) | {self.node_id}
        )

    def on_register(self, peers, membership_epoch: int) -> None:
        self._membership_epoch = membership_epoch
        self.update_peers_from_proto(peers)
        if not self.election.get_coordinator()[0]:
            self.election.start_election(reason="initial_join")

    def next_beacon_sequence(self) -> int:
        with self._lock:
            self._beacon_seq += 1
            return self._beacon_seq

    def coordinator_report(self) -> tuple[str, int]:
        cid, ceid = self.election.get_coordinator()
        return cid or self.node_id, ceid if ceid >= 0 else self.election_id

    def handle_peer_message(self, message_type: str, payload: str, sender: str) -> None:
        sync = get_worker_sync(self.node_id)
        self.election.handle_message(message_type, payload, sender)
        if message_type == "LOCK_REQUEST":
            parts = payload.split("|")
            if len(parts) >= 4:
                self.lock_manager.handle_remote_request(
                    parts[1], parts[2], sender, int(parts[3])
                )
        elif message_type == "LOCK_REPLY":
            self.lock_manager.on_reply(sender)
