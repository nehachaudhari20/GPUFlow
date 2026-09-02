from typing import List, Optional

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from backend.app.models.workload import Priority, Workload, WorkloadStatus, WorkloadType
from backend.app.repositories.workload_repository import WorkloadRepository


class MongoWorkloadRepository(WorkloadRepository):
    def __init__(self, mongo_uri: str, database: str = "gpuflow"):
        self._client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        self._client.admin.command("ping")
        self._collection: Collection = self._client[database]["workloads"]
        self._collection.create_index("job_id", unique=True)
        self._collection.create_index([("status", ASCENDING), ("priority", ASCENDING)])

    def insert(self, workload: Workload) -> Workload:
        doc = self._to_document(workload)
        try:
            self._collection.insert_one(doc)
        except DuplicateKeyError as exc:
            raise ValueError(f"Workload {workload.job_id} already exists") from exc
        return workload

    def get_by_id(self, job_id: str) -> Optional[Workload]:
        doc = self._collection.find_one({"job_id": job_id})
        return self._from_document(doc) if doc else None

    def list_all(self, status: WorkloadStatus | None = None) -> List[Workload]:
        query = {"status": status.value} if status else {}
        docs = self._collection.find(query)
        return [self._from_document(doc) for doc in docs]

    def update(self, workload: Workload) -> Workload:
        doc = self._to_document(workload)
        result = self._collection.replace_one({"job_id": workload.job_id}, doc)
        if result.matched_count == 0:
            raise KeyError(f"Workload {workload.job_id} not found")
        return workload

    def delete_all(self) -> int:
        result = self._collection.delete_many({})
        return result.deleted_count

    @staticmethod
    def _to_document(workload: Workload) -> dict:
        data = workload.model_dump()
        data["type"] = workload.type.value
        data["priority"] = workload.priority.value
        data["status"] = workload.status.value
        return data

    @staticmethod
    def _from_document(doc: dict) -> Workload:
        return Workload(
            job_id=doc["job_id"],
            name=doc["name"],
            type=WorkloadType(doc["type"]),
            gpu_required=doc["gpu_required"],
            gpu_memory_required=doc["gpu_memory_required"],
            cpu_required=doc["cpu_required"],
            ram_required=doc["ram_required"],
            priority=Priority(doc["priority"]),
            estimated_duration=doc["estimated_duration"],
            status=WorkloadStatus(doc["status"]),
            assigned_node=doc.get("assigned_node"),
            started_at=doc.get("started_at"),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )
