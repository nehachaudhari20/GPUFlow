import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.repositories.workload_repository import InMemoryWorkloadRepository
from backend.app.services import workload_service as workload_service_module
from backend.app.services.workload_service import WorkloadService


@pytest.fixture
def client(monkeypatch):
    repo = InMemoryWorkloadRepository()
    service = WorkloadService(repo)
    monkeypatch.setattr(workload_service_module, "workload_service", service)
    import backend.app.api.workloads as workloads_api

    monkeypatch.setattr(workloads_api, "workload_service", service)
    return TestClient(app)


def test_post_workloads(client):
    response = client.post(
        "/workloads",
        json={
            "name": "inference-job",
            "type": "INFERENCE",
            "gpu_required": 1,
            "gpu_memory_required": 4,
            "cpu_required": 2,
            "ram_required": 8,
            "priority": "HIGH",
            "estimated_duration": 120,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "QUEUED"
    assert data["name"] == "inference-job"


def test_get_workloads(client):
    client.post(
        "/workloads",
        json={
            "name": "batch-job",
            "type": "BATCH",
            "cpu_required": 2,
            "estimated_duration": 30,
        },
    )
    response = client.get("/workloads")
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_get_workload_by_id(client):
    created = client.post(
        "/workloads",
        json={
            "name": "preprocess-job",
            "type": "PREPROCESSING",
            "ram_required": 4,
            "estimated_duration": 15,
        },
    ).json()

    response = client.get(f"/workloads/{created['job_id']}")
    assert response.status_code == 200
    assert response.json()["job_id"] == created["job_id"]


def test_get_workload_not_found(client):
    response = client.get("/workloads/missing-id")
    assert response.status_code == 404
