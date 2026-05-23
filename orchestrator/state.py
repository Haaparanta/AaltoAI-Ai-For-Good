"""Mutable orchestrator state consumed by the TUI."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from agents.registry import get_spec
from orchestrator.migration_layout import MigrationLayout
from orchestrator.models import (
    AgentId,
    AgentInfo,
    AgentRunInfo,
    AgentStatus,
    LogEntry,
    ReviewContext,
    RunGroup,
    RunKind,
    WorkflowStep,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


_ACTIVE_RUN_STATUSES = frozenset({AgentStatus.RUNNING, AgentStatus.WAITING})


@dataclass
class OrchestratorState:
    """Full UI-facing state for the migration orchestrator."""

    workflow_step: WorkflowStep = WorkflowStep.IDLE
    agents: dict[AgentId, AgentInfo] = field(default_factory=dict)
    runs: dict[str, AgentRunInfo] = field(default_factory=dict)
    run_groups: dict[str, RunGroup] = field(default_factory=dict)
    log: list[LogEntry] = field(default_factory=list)
    awaiting_human: bool = False
    review: ReviewContext | None = None
    workspace: str = "."
    source_venv: str | None = None
    layout: MigrationLayout | None = None
    llm_display: str = ""
    running: bool = False
    last_user_feedback: str = ""
    last_agent_summary: str = ""
    selected_run_id: str | None = None
    log_filter: str = "all"
    compact_ui: bool = False
    max_concurrency: int = 4
    _instance_counters: dict[AgentId, int] = field(default_factory=dict)
    _cancel_event: threading.Event = field(
        default_factory=threading.Event,
        repr=False,
        compare=False,
    )

    def request_cancel(self) -> None:
        self._cancel_event.set()

    def clear_cancel(self) -> None:
        self._cancel_event.clear()

    def cancel_requested(self) -> bool:
        return self._cancel_event.is_set()

    @property
    def cancel_event(self) -> threading.Event:
        return self._cancel_event

    def __post_init__(self) -> None:
        if not self.agents:
            self.agents = {aid: AgentInfo.default(aid) for aid in AgentId}

    def append_log(
        self,
        message: str,
        level: str = "info",
        *,
        run_id: str | None = None,
        role: AgentId | None = None,
        instance: int | None = None,
    ) -> LogEntry:
        if run_id is not None and role is None:
            run = self.runs.get(run_id)
            if run is not None:
                role = run.role
                instance = run.instance
        entry = LogEntry(
            timestamp=_utc_now(),
            level=level,
            message=message,
            run_id=run_id,
            role=role,
            instance=instance,
        )
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

    def start_run(
        self,
        *,
        role: AgentId,
        label: str,
        step: WorkflowStep,
        kind: RunKind,
        group_id: str | None = None,
        scope: str = "",
        detail: str = "",
    ) -> AgentRunInfo:
        instance = self._instance_counters.get(role, 0) + 1
        self._instance_counters[role] = instance
        run_id = uuid4().hex[:8]
        run = AgentRunInfo(
            run_id=run_id,
            role=role,
            instance=instance,
            label=label,
            status=AgentStatus.RUNNING,
            detail=detail,
            step=step,
            kind=kind,
            started_at=_utc_now(),
            group_id=group_id,
            scope=scope,
        )
        self.runs[run_id] = run
        if group_id is not None:
            group = self.run_groups.get(group_id)
            if group is None:
                group = RunGroup(group_id=group_id, step=step, label=label)
                self.run_groups[group_id] = group
            group.run_ids.append(run_id)
        self.recompute_agent_aggregate(role)
        return run

    def update_run(
        self,
        run_id: str,
        *,
        status: AgentStatus | None = None,
        detail: str | None = None,
        last_tool: str | None = None,
    ) -> None:
        run = self.runs[run_id]
        self.runs[run_id] = AgentRunInfo(
            run_id=run.run_id,
            role=run.role,
            instance=run.instance,
            label=run.label,
            status=status if status is not None else run.status,
            detail=detail if detail is not None else run.detail,
            step=run.step,
            kind=run.kind,
            started_at=run.started_at,
            group_id=run.group_id,
            scope=run.scope,
            last_tool=last_tool if last_tool is not None else run.last_tool,
        )
        self.recompute_agent_aggregate(run.role)

    def finish_run(
        self,
        run_id: str,
        status: AgentStatus,
        *,
        detail: str = "",
    ) -> None:
        self.update_run(run_id, status=status, detail=detail)
        self.recompute_agent_aggregate(self.runs[run_id].role)

    def recompute_agent_aggregate(self, role: AgentId) -> None:
        role_runs = [run for run in self.runs.values() if run.role == role]
        if not role_runs:
            return
        spec = get_spec(role.value)
        if any(run.status == AgentStatus.ERROR for run in role_runs):
            failed = next(run for run in role_runs if run.status == AgentStatus.ERROR)
            self.set_agent(role, AgentStatus.ERROR, detail=failed.detail)
            return
        active = [run for run in role_runs if run.status in _ACTIVE_RUN_STATUSES]
        if active:
            if len(active) == 1:
                detail = active[0].detail or active[0].label
            else:
                detail = f"{len(active)} active"
            self.set_agent(role, AgentStatus.RUNNING, detail=detail)
            return
        if all(run.status == AgentStatus.COMPLETED for run in role_runs):
            latest = role_runs[-1]
            self.set_agent(
                role,
                AgentStatus.COMPLETED,
                detail=latest.detail or "Done",
            )
            return
        self.set_agent(role, AgentStatus.IDLE, detail=spec.role)

    def clear_runs(self) -> None:
        self.runs.clear()
        self.run_groups.clear()
        self.selected_run_id = None
        self._instance_counters.clear()

    def reset_agents_to_idle(self, except_orchestrator: bool = False) -> None:
        self.clear_runs()
        for agent_id in AgentId:
            if except_orchestrator and agent_id == AgentId.ORCHESTRATOR:
                continue
            self.set_agent(agent_id, AgentStatus.IDLE, detail="")

    def clear_human_review(self) -> None:
        self.awaiting_human = False
        self.review = None
        self.set_agent(AgentId.ORCHESTRATOR, AgentStatus.RUNNING, detail="")

    @property
    def active_run_count(self) -> int:
        return sum(
            1 for run in self.runs.values() if run.status in _ACTIVE_RUN_STATUSES
        )
