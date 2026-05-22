"""Mutable orchestrator state consumed by the TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from orchestrator.models import (
    AgentId,
    AgentInfo,
    AgentStatus,
    LogEntry,
    ReviewContext,
    WorkflowStep,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class OrchestratorState:
    """Full UI-facing state for the migration orchestrator."""

    workflow_step: WorkflowStep = WorkflowStep.IDLE
    agents: dict[AgentId, AgentInfo] = field(default_factory=dict)
    log: list[LogEntry] = field(default_factory=list)
    awaiting_human: bool = False
    review: ReviewContext | None = None
    workspace: str = "."
    running: bool = False
    last_user_feedback: str = ""

    def __post_init__(self) -> None:
        if not self.agents:
            self.agents = {aid: AgentInfo.default(aid) for aid in AgentId}

    def append_log(self, message: str, level: str = "info") -> LogEntry:
        entry = LogEntry(timestamp=_utc_now(), level=level, message=message)
        self.log.append(entry)
        return entry

    def set_agent(
        self,
        agent_id: AgentId,
        status: AgentStatus,
        *,
        detail: str = "",
    ) -> None:
        current = self.agents[agent_id]
        self.agents[agent_id] = AgentInfo(
            agent_id=current.agent_id,
            display_name=current.display_name,
            role=current.role,
            status=status,
            detail=detail or current.detail,
        )

    def reset_agents_to_idle(self, except_orchestrator: bool = False) -> None:
        for agent_id in AgentId:
            if except_orchestrator and agent_id == AgentId.ORCHESTRATOR:
                continue
            self.set_agent(agent_id, AgentStatus.IDLE, detail="")

    def clear_human_review(self) -> None:
        self.awaiting_human = False
        self.review = None
        self.set_agent(AgentId.ORCHESTRATOR, AgentStatus.RUNNING, detail="")
