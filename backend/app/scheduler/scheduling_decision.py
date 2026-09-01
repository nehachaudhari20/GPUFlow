import time
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class ResourceScoreBreakdown(BaseModel):
    gpu_availability: float = Field(description="Normalized GPU availability score (0-100)")
    cpu_availability: float = Field(description="Normalized CPU availability score (0-100)")
    ram_availability: float = Field(description="Normalized RAM availability score (0-100)")
    gpu_memory_availability: float = Field(
        description="Normalized GPU memory availability score (0-100)"
    )
    health: float = Field(description="Normalized node health score (0-100)")
    load_balance: float = Field(description="Normalized load-balance score (0-100)")
    total: float = Field(description="Weighted total score (0-100)")


class RejectedNode(BaseModel):
    node_id: str
    hostname: str
    reasons: List[str]


class CandidateNode(BaseModel):
    node_id: str
    hostname: str
    scores: ResourceScoreBreakdown
    eligible: bool = True


class SchedulingDecision(BaseModel):
    job_id: str
    workload_name: str
    candidate_nodes: List[CandidateNode] = []
    rejected_nodes: List[RejectedNode] = []
    selected_node: Optional[str] = None
    allocation_success: bool = False
    kept_queued: bool = False
    reason: Optional[str] = None
    scheduling_timestamp: float = Field(default_factory=time.time)

    def summary(self) -> str:
        lines = [self.workload_name, ""]
        for rejected in self.rejected_nodes:
            lines.append(rejected.node_id)
            lines.append("Rejected:")
            for reason in rejected.reasons:
                lines.append(f"  {reason}")
            lines.append("")

        for candidate in self.candidate_nodes:
            lines.append(candidate.node_id)
            lines.append("Eligible:")
            lines.append(f"  Score = {candidate.scores.total:.1f}")
            lines.append("")

        if self.selected_node:
            lines.append("Selected:")
            lines.append(self.selected_node)
        elif self.kept_queued:
            lines.append("Selected:")
            lines.append("None (job kept QUEUED)")
            if self.reason:
                lines.append(f"Reason: {self.reason}")

        return "\n".join(lines)
