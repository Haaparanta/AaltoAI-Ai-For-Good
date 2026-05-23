"""Infer benchmark cases from cached .pyi API signatures."""

from __future__ import annotations

import ast
import json
import random
import re
import string
from pathlib import Path

from benchmark.config import INPUT_SIZE_TIERS, TIER_SCALES, BenchmarkCase

_RANDOM = random.Random(42)


def _random_word(length: int) -> str:
    return "".join(_RANDOM.choice(string.ascii_lowercase) for _ in range(length))


def _normalize_type(type_name: str) -> str:
    cleaned = type_name.replace(" ", "")
    cleaned = cleaned.replace("typing.", "")
    cleaned = re.sub(r"\[.*\]", "", cleaned)
    return cleaned.lower()


def _parse_param_types(stub_text: str) -> dict[str, list[tuple[str, bool]]]:
    """Return function -> list of (param_name, is_optional)."""
    tree = ast.parse(stub_text)
    result: dict[str, list[tuple[str, bool]]] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
            continue
        params: list[tuple[str, bool]] = []
        args = node.args
        defaults_offset = len(args.args) - len(args.defaults)
        for index, arg in enumerate(args.args):
            if arg.arg == "self":
                continue
            optional = index >= defaults_offset
            params.append((arg.arg, optional))
        if params:
            result[node.name] = params
    return result


def _value_for_type(type_hint: str, tier: str) -> object:
    scale = TIER_SCALES[tier]
    normalized = _normalize_type(type_hint)
    if normalized in ("int",):
        return scale["n"]
    if normalized in ("float",):
        return float(scale["n"])
    if normalized in ("bool",):
        return True
    if normalized in ("str",):
        return "x" * scale["text_len"]
    if "list" in normalized and "int" in normalized:
        length = scale["list_len"]
        return [_RANDOM.randint(0, length * 10) for _ in range(length)]
    if "list" in normalized and "str" in normalized:
        return [_random_word(scale["word_len"]) for _ in range(scale["list_len"])]
    if "list" in normalized:
        return list(range(scale["list_len"]))
    if normalized in ("bytes",):
        return b"x" * min(scale["text_len"], 1024)
    return scale["n"]


def _parse_signature_args(stub_text: str, function: str) -> list[tuple[str, str, bool]]:
    """Return (param_name, type_hint, optional) for one function."""
    tree = ast.parse(stub_text)
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != function:
            continue
        params: list[tuple[str, str, bool]] = []
        args = node.args
        defaults_offset = len(args.args) - len(args.defaults)
        for index, arg in enumerate(args.args):
            if arg.arg == "self":
                continue
            hint = ast.unparse(arg.annotation) if arg.annotation else "Any"
            optional = index >= defaults_offset
            params.append((arg.arg, hint, optional))
        return params
    return []


def infer_cases_from_stub(
    stub_path: Path,
    *,
    module: str,
) -> list[BenchmarkCase]:
    """Build tiered benchmark cases from a single .pyi stub file."""
    if not stub_path.is_file():
        return []

    stub_text = stub_path.read_text(encoding="utf-8")
    functions = _parse_param_types(stub_text)
    cases: list[BenchmarkCase] = []

    for function, param_specs in functions.items():
        if function == "main":
            continue
        type_map = {
            name: hint
            for name, hint, _optional in _parse_signature_args(stub_text, function)
        }
        for tier in INPUT_SIZE_TIERS:
            args: list[object] = []
            kwargs: dict[str, object] = {}
            for param_name, optional in param_specs:
                hint = type_map.get(param_name, "Any")
                value = _value_for_type(hint, tier)
                if optional:
                    kwargs[param_name] = value
                else:
                    args.append(value)
            cases.append(
                BenchmarkCase(
                    name=f"{function}_{tier}",
                    module=module,
                    function=function,
                    input_size_tier=tier,
                    args_json=json.dumps(args),
                    kwargs_json=json.dumps(kwargs),
                )
            )
    return cases


def infer_cases_from_signatures(
    signatures_root: Path,
    *,
    module: str,
) -> list[BenchmarkCase]:
    """Load .pyi stubs and infer benchmark cases for all public functions."""
    candidates = [
        signatures_root / f"{module}.pyi",
        signatures_root / module / "__init__.pyi",
    ]
    for stub_path in candidates:
        cases = infer_cases_from_stub(stub_path, module=module)
        if cases:
            return cases
    return []
