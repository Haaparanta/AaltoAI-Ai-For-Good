"""Tests for signature-based benchmark inference."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.inference import infer_cases_from_stub


def test_infer_cases_from_int_and_list_stub(tmp_path: Path) -> None:
    stub = tmp_path / "main.pyi"
    stub.write_text(
        "def bubble_sort(numbers: list[int]) -> list[int]: ...\n",
        encoding="utf-8",
    )
    cases = infer_cases_from_stub(stub, module="main")
    assert len(cases) == 4
    small = next(case for case in cases if case.input_size_tier == "small")
    args = json.loads(small.args_json)
    assert len(args) == 1
    assert isinstance(args[0], list)
    assert len(args[0]) > 0


def test_infer_cases_skips_private_functions(tmp_path: Path) -> None:
    stub = tmp_path / "main.pyi"
    stub.write_text(
        "def _helper(x: int) -> int: ...\n"
        "def visible(n: int) -> int: ...\n",
        encoding="utf-8",
    )
    cases = infer_cases_from_stub(stub, module="main")
    names = {case.function for case in cases}
    assert names == {"visible"}
