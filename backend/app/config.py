from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "GPUFlow"
    debug: bool = False

    heartbeat_interval: int = 5
    heartbeat_timeout: int = 15
    simulate_gpus: bool = True
    simulated_gpu_count: float = 1.0
    simulated_gpu_memory_gb: float = 16.0
    grpc_port: int = 50051
    scheduler_address: str = "localhost:50051"

    mongo_uri: str | None = None
    mongo_database: str = "gpuflow"

    schedule_gpu_weight: float = 0.40
    schedule_cpu_weight: float = 0.25
    schedule_ram_weight: float = 0.15
    schedule_health_weight: float = 0.10
    schedule_load_balance_weight: float = 0.10

    class Config:
        env_file = ".env"


settings = Settings()
