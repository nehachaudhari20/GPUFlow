from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import grpc

from backend.app.config import settings
from backend.app.scheduler.cluster_state import cluster_state
from backend.app.storage.storage_metadata import FileMetadata

logger = logging.getLogger(__name__)

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class DistributedStorageService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._files: Dict[str, FileMetadata] = {}
        self._base_dir = Path(os.environ.get("GPUFLOW_STORAGE_DIR", "/tmp/gpuflow-storage"))

    def _safe_filename(self, name: str) -> str:
        base = os.path.basename(name)
        if not SAFE_NAME.match(base):
            raise ValueError("Unsafe filename")
        return base

    def _checksum(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _store_remote(self, node_id: str, hostname: str, port: int, file_id: str, name: str, data: bytes, checksum: str) -> bool:
        import sys

        sys.path.append(str(Path(__file__).resolve().parents[2] / "protobufs"))
        import gpuflow_pb2
        import gpuflow_pb2_grpc

        target = f"{hostname}:{port}"
        try:
            with grpc.insecure_channel(target) as ch:
                stub = gpuflow_pb2_grpc.WorkerStub(ch)
                resp = stub.StoreFile(
                    gpuflow_pb2.StoreFileRequest(
                        file_id=file_id,
                        original_filename=name,
                        content=data,
                        checksum=checksum,
                    ),
                    timeout=10.0,
                )
                return resp.success
        except Exception as exc:
            logger.warning("Store on %s failed: %s", node_id, exc)
            return False

    def _retrieve_remote(self, hostname: str, port: int, file_id: str) -> Tuple[bytes, str]:
        import sys

        sys.path.append(str(Path(__file__).resolve().parents[2] / "protobufs"))
        import gpuflow_pb2
        import gpuflow_pb2_grpc

        with grpc.insecure_channel(f"{hostname}:{port}") as ch:
            stub = gpuflow_pb2_grpc.WorkerStub(ch)
            resp = stub.RetrieveFile(gpuflow_pb2.RetrieveFileRequest(file_id=file_id), timeout=10.0)
            if not resp.success:
                raise FileNotFoundError(resp.message)
            return resp.content, resp.checksum

    def upload(self, filename: str, data: bytes) -> FileMetadata:
        if len(data) > settings.storage_max_upload_bytes:
            raise ValueError("File exceeds size limit")
        safe = self._safe_filename(filename)
        checksum = self._checksum(data)
        file_id = str(uuid.uuid4())
        online = [n for n in cluster_state.get_online_nodes() if n.grpc_port > 0]
        if len(online) < 1:
            raise RuntimeError("No storage workers available")
        targets = online[: max(1, settings.storage_replication_factor)]
        replicas: List[str] = []
        for node in targets:
            if self._store_remote(node.node_id, node.hostname, node.grpc_port, file_id, safe, data, checksum):
                replicas.append(node.node_id)
        if not replicas:
            raise RuntimeError("Replication failed on all nodes")
        meta = FileMetadata(
            file_id=file_id,
            original_filename=safe,
            size_bytes=len(data),
            checksum=checksum,
            replica_nodes=replicas,
            replication_status="REPLICATED" if len(replicas) >= 2 else "PARTIAL",
        )
        with self._lock:
            self._files[file_id] = meta
        return meta

    def get_metadata(self, file_id: str) -> Optional[FileMetadata]:
        with self._lock:
            return self._files.get(file_id)

    def download(self, file_id: str) -> Tuple[bytes, FileMetadata]:
        meta = self.get_metadata(file_id)
        if meta is None:
            raise FileNotFoundError(file_id)
        last_err: Exception | None = None
        for node_id in meta.replica_nodes:
            node = cluster_state.get_node(node_id)
            if node is None or node.status != "ONLINE":
                continue
            try:
                content, checksum = self._retrieve_remote(node.hostname, node.grpc_port, file_id)
                if checksum != meta.checksum:
                    raise ValueError("Checksum mismatch")
                return content, meta
            except Exception as exc:
                last_err = exc
        raise RuntimeError(f"All replicas unavailable: {last_err}")

    def list_files(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "file_id": m.file_id,
                    "original_filename": m.original_filename,
                    "size_bytes": m.size_bytes,
                    "checksum": m.checksum,
                    "replica_nodes": m.replica_nodes,
                    "created_at": m.created_at,
                    "replication_status": m.replication_status,
                }
                for m in self._files.values()
            ]

    def delete(self, file_id: str) -> bool:
        with self._lock:
            return self._files.pop(file_id, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._files.clear()


distributed_storage = DistributedStorageService()
