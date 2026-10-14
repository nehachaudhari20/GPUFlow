from pydantic import BaseModel, model_validator


class SchedulingPolicy(BaseModel):
    gpu_weight: float = 0.40
    cpu_weight: float = 0.25
    ram_weight: float = 0.15
    health_weight: float = 0.10
    load_balance_weight: float = 0.10

    @model_validator(mode="after")
    def validate_weights_sum_to_one(self):
        total = (
            self.gpu_weight
            + self.cpu_weight
            + self.ram_weight
            + self.health_weight
            + self.load_balance_weight
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Scheduling weights must sum to 1.0, got {total}")
        return self

    @classmethod
    def from_settings(cls) -> "SchedulingPolicy":
        from backend.app.config import settings

        if settings.cpu_only_mode:
            return cls(
                gpu_weight=0.0,
                cpu_weight=0.45,
                ram_weight=0.25,
                health_weight=0.10,
                load_balance_weight=0.20,
            )

        return cls(
            gpu_weight=settings.schedule_gpu_weight,
            cpu_weight=settings.schedule_cpu_weight,
            ram_weight=settings.schedule_ram_weight,
            health_weight=settings.schedule_health_weight,
            load_balance_weight=settings.schedule_load_balance_weight,
        )
