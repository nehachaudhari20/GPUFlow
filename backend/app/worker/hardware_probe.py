"""Probe real host CPU/RAM and optional NVIDIA GPUs (no simulation)."""
from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass

import psutil

logger = logging.getLogger(__name__)


@dataclass
class HostResources:
    cpu_total: float
    ram_total_gb: float
    gpu_total: float
    gpu_memory_total_gb: float
    source: str


def _probe_nvidia_via_smi() -> tuple[float, float]:
    if not shutil.which("nvidia-smi"):
        return 0.0, 0.0
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return 0.0, 0.0
        mem_mib = [float(line.strip()) for line in result.stdout.splitlines() if line.strip()]
        if not mem_mib:
            return 0.0, 0.0
        gpu_count = float(len(mem_mib))
        gpu_mem_gb = sum(mem_mib) / 1024.0
        return gpu_count, gpu_mem_gb
    except Exception as exc:
        logger.debug("nvidia-smi probe failed: %s", exc)
        return 0.0, 0.0


def _probe_nvidia_via_pynvml() -> tuple[float, float]:
    try:
        import pynvml  # type: ignore

        pynvml.nvmlInit()
        try:
            count = pynvml.nvmlDeviceGetCount()
            if count == 0:
                return 0.0, 0.0
            total_mem = 0.0
            for idx in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_mem += mem.total
            return float(count), total_mem / (1024**3)
        finally:
            pynvml.nvmlShutdown()
    except Exception as exc:
        logger.debug("pynvml probe unavailable: %s", exc)
        return 0.0, 0.0


def probe_host_resources(
    simulate_gpus: bool,
    simulated_gpu_count: float,
    simulated_gpu_memory_gb: float,
) -> HostResources:
    cpu_total = float(psutil.cpu_count(logical=True) or 1)
    ram_total_gb = psutil.virtual_memory().total / (1024**3)

    if simulate_gpus:
        return HostResources(
            cpu_total=cpu_total,
            ram_total_gb=ram_total_gb,
            gpu_total=simulated_gpu_count,
            gpu_memory_total_gb=simulated_gpu_memory_gb,
            source="simulated",
        )

    gpu_total, gpu_mem_gb = _probe_nvidia_via_pynvml()
    if gpu_total <= 0:
        gpu_total, gpu_mem_gb = _probe_nvidia_via_smi()

    source = "nvidia" if gpu_total > 0 else "cpu-only"
    logger.info(
        "Probed host resources: cpu=%s ram=%.1fGB gpu=%s gpu_mem=%.1fGB (%s)",
        cpu_total,
        ram_total_gb,
        gpu_total,
        gpu_mem_gb,
        source,
    )
    return HostResources(
        cpu_total=cpu_total,
        ram_total_gb=ram_total_gb,
        gpu_total=gpu_total,
        gpu_memory_total_gb=gpu_mem_gb,
        source=source,
    )
