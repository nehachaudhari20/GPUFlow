from fastapi import FastAPI
from backend.app.core.logging import setup_logging
from backend.app.config import settings

setup_logging()

app = FastAPI(title="GPUFlow", description="Distributed GPU-Aware Workload Scheduling")

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "GPUFlow Backend", "version": "1.0.0"}
