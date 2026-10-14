from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "GPUFlow"
    debug: bool = False

    heartbeat_interval: int = 5
    heartbeat_timeout: int = 15

    # Local Docker demo: simulate GPUs. AWS workers: SIMULATE_GPUS=False
    simulate_gpus: bool = True
    simulated_gpu_count: float = 1.0
    simulated_gpu_memory_gb: float = 16.0

    # AWS: fixed worker gRPC port (e.g. 50052). 0 = dynamic port (local Docker)
    worker_grpc_port: int = 0

    grpc_port: int = 50051
    scheduler_address: str = "localhost:50051"

    # AWS CPU-only cluster: rebalance scoring weights automatically
    cpu_only_mode: bool = False

    mongo_uri: Optional[str] = None
    mongo_database: str = "gpuflow"

    schedule_gpu_weight: float = 0.40
    schedule_cpu_weight: float = 0.25
    schedule_ram_weight: float = 0.15
    schedule_health_weight: float = 0.10
    schedule_load_balance_weight: float = 0.10

    fa2_dev_controls_enabled: bool = True

    recovery_max_attempts: int = 3
    recovery_retry_base_delay_s: float = 2.0
    recovery_retry_max_delay_s: float = 30.0

    storage_max_upload_bytes: int = 5 * 1024 * 1024
    storage_replication_factor: int = 2

    autoscale_min_workers: int = 1
    autoscale_max_workers: int = 10
    autoscale_cpu_high: float = 0.75
    autoscale_queue_depth_high: int = 3
    autoscale_cooldown_s: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
