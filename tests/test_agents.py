"""Tests for agent system prompts."""

from __future__ import annotations

import pytest

from agents import (
    ANALYZER_SYSTEM_PROMPT,
    BENCHMARKER_SYSTEM_PROMPT,
    PY_TESTER_SYSTEM_PROMPT,
    REVIEWER_SYSTEM_PROMPT,
    SCAFFOLDER_SYSTEM_PROMPT,
    SYSTEM_PROMPTS,
    TRANSLATOR_SYSTEM_PROMPT,
    get_spec,
    get_system_prompt,
)
from agents.registry import can_run_parallel


def test_all_prompts_non_empty() -> None:
    for agent_id, prompt in SYSTEM_PROMPTS.items():
        assert prompt.strip(), f"{agent_id} prompt must not be empty"


def test_get_system_prompt_round_trip() -> None:
    assert get_system_prompt("analyzer") is ANALYZER_SYSTEM_PROMPT
    assert get_system_prompt("py_tester") is PY_TESTER_SYSTEM_PROMPT
    assert get_system_prompt("scaffolder") is SCAFFOLDER_SYSTEM_PROMPT
    assert get_system_prompt("translator") is TRANSLATOR_SYSTEM_PROMPT
    assert get_system_prompt("reviewer") is REVIEWER_SYSTEM_PROMPT


def test_registry_write_prefixes() -> None:
    assert get_spec("py_tester").write_prefixes == ("py_tests/",)
    assert get_spec("translator").write_prefixes == ("rust/",)
    assert get_spec("benchmarker").write_prefixes == ("measurements/",)
    assert get_spec("reviewer").read_only is True


def test_benchmarker_prompt_and_role() -> None:
    assert BENCHMARKER_SYSTEM_PROMPT.strip()
    assert "Step 6" in BENCHMARKER_SYSTEM_PROMPT
    spec = get_spec("benchmarker")
    assert spec.llm is False
    assert "measurements" in spec.role


def test_get_system_prompt_unknown_agent() -> None:
    with pytest.raises(ValueError, match="Unknown agent_id"):
        get_system_prompt("orchestrator")
