"""Checkpoint persistence and artifact-based migration progress detection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from executor_mcp.rust_wheel import detect_wheel_path

from orchestrator.migration_layout import MigrationLayout, pyo3_lib_rs_scaffold
from orchestrator.models import WorkflowStep

CHECKPOINT_SCHEMA_VERSION = 1


class ProgressSource(str, Enum):
    """How the current workflow step was determined."""

    CHECKPOINT = "checkpoint"
    INFERRED = "inferred"
    NONE = "none"


class ProgressConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class ProgressSnapshot:
    """Detected or restored migration progress for a project."""

    workflow_step: WorkflowStep
    source: ProgressSource
    confidence: ProgressConfidence
    awaiting_human: bool = False
    last_agent_summary: str = ""
    updated_at: datetime | None = None

    @property
    def has_progress(self) -> bool:
        return self.workflow_step not in (WorkflowStep.IDLE, WorkflowStep.DONE)

    @property
    def is_resumable(self) -> bool:
        return self.workflow_step not in (WorkflowStep.IDLE, WorkflowStep.DONE)

    def display_label(self) -> str:
        step_label = self.workflow_step.label
        if self.source == ProgressSource.CHECKPOINT:
            return f"{step_label} (checkpoint)"
        if self.source == ProgressSource.INFERRED:
            return f"{step_label} (inferred, {self.confidence.value} confidence)"
        return step_label


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_updated_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def save_checkpoint(
    layout: MigrationLayout,
    *,
    workflow_step: WorkflowStep,
    awaiting_human: bool = False,
    last_agent_summary: str = "",
) -> Path:
    """Persist orchestrator workflow state under py_tests/.orchestrator/."""
    payload = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "source_root": str(layout.source_root.resolve()),
        "workflow_step": workflow_step.value,
        "awaiting_human": awaiting_human,
        "last_agent_summary": last_agent_summary,
        "updated_at": _utc_now_iso(),
    }
    path = layout.checkpoint_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_checkpoint(layout: MigrationLayout) -> ProgressSnapshot | None:
    """Load checkpoint if present and source_root matches."""
    path = layout.checkpoint_path
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        return None
    stored_source = Path(data.get("source_root", "")).resolve()
    if stored_source != layout.source_root.resolve():
        return None
    try:
        step = WorkflowStep(data["workflow_step"])
    except (KeyError, ValueError):
        return None
    return ProgressSnapshot(
        workflow_step=step,
        source=ProgressSource.CHECKPOINT,
        confidence=ProgressConfidence.HIGH,
        awaiting_human=bool(data.get("awaiting_human", False)),
        last_agent_summary=str(data.get("last_agent_summary", "")),
        updated_at=_parse_updated_at(data.get("updated_at")),
    )


def clear_checkpoint(layout: MigrationLayout) -> None:
    path = layout.checkpoint_path
    if path.is_file():
        path.unlink()


def _has_migration_plan(layout: MigrationLayout) -> bool:
    return (layout.py_tests_root / "migration_plan.md").is_file()


def _has_python_tests(layout: MigrationLayout) -> bool:
    tests_dir = layout.py_tests_root / "tests"
    if not tests_dir.is_dir():
        return False
    return any(
        path.name.startswith("test_") and path.suffix == ".py"
        for path in tests_dir.rglob("*.py")
    )


def _has_release_wheel(layout: MigrationLayout) -> bool:
    return detect_wheel_path(layout.rust_root) is not None


def _has_measurements_report(layout: MigrationLayout) -> bool:
    return (layout.measurements_root / "report.txt").is_file()


def is_rust_scaffold_only(layout: MigrationLayout) -> bool:
    """Return True when Rust crate still matches the empty PyO3 scaffold."""
    lib_rs = layout.rust_root / "src" / "lib.rs"
    if not lib_rs.is_file():
        return True
    text = lib_rs.read_text(encoding="utf-8")
    if "#[pyfunction]" in text or "add_function" in text:
        return False
    package_name = layout.source_root.name.replace("-", "_")
    try:
        from executor_mcp.api_signatures import detect_import_targets

        targets = detect_import_targets(layout.source_root)
        if targets:
            package_name = targets[0]
    except ValueError:
        pass
    scaffold = pyo3_lib_rs_scaffold(package_name)
    normalized = text.strip()
    if normalized == scaffold.strip():
        return True
    extra_rs = [
        path
        for path in (layout.rust_root / "src").glob("*.rs")
        if path.name not in {"lib.rs", "main.rs"}
    ]
    return not extra_rs and "Ok(())" in text and "#[pyfunction]" not in text


def infer_migration_progress(layout: MigrationLayout) -> ProgressSnapshot:
    """Infer workflow step from migration directory artifacts."""
    if not layout.py_tests_root.is_dir():
        return ProgressSnapshot(
            workflow_step=WorkflowStep.IDLE,
            source=ProgressSource.NONE,
            confidence=ProgressConfidence.HIGH,
        )

    if not _has_migration_plan(layout):
        return ProgressSnapshot(
            workflow_step=WorkflowStep.CREATE_TEST_PY,
            source=ProgressSource.INFERRED,
            confidence=ProgressConfidence.HIGH,
        )

    if not _has_python_tests(layout):
        return ProgressSnapshot(
            workflow_step=WorkflowStep.CREATE_TEST_PY,
            source=ProgressSource.INFERRED,
            confidence=ProgressConfidence.MEDIUM,
        )

    if is_rust_scaffold_only(layout):
        return ProgressSnapshot(
            workflow_step=WorkflowStep.REVIEW_PLAN_PY,
            source=ProgressSource.INFERRED,
            confidence=ProgressConfidence.MEDIUM,
        )

    if not _has_release_wheel(layout):
        return ProgressSnapshot(
            workflow_step=WorkflowStep.REVIEW_RUST_CODE,
            source=ProgressSource.INFERRED,
            confidence=ProgressConfidence.MEDIUM,
        )

    if _has_measurements_report(layout):
        return ProgressSnapshot(
            workflow_step=WorkflowStep.DONE,
            source=ProgressSource.INFERRED,
            confidence=ProgressConfidence.MEDIUM,
        )

    return ProgressSnapshot(
        workflow_step=WorkflowStep.RUN_TESTS,
        source=ProgressSource.INFERRED,
        confidence=ProgressConfidence.MEDIUM,
    )


def detect_migration_progress(layout: MigrationLayout) -> ProgressSnapshot:
    """Return checkpoint state when available, otherwise infer from artifacts."""
    checkpoint = load_checkpoint(layout)
    if checkpoint is not None:
        return checkpoint
    return infer_migration_progress(layout)
