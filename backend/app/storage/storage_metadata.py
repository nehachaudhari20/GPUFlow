from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List


@dataclass
class FileMetadata:
    file_id: str
    original_filename: str
    size_bytes: int
    checksum: str
    replica_nodes: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    replication_status: str = "PENDING"
