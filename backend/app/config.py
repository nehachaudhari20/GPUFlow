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

    class Config:
        env_file = ".env"


settings = Settings()
