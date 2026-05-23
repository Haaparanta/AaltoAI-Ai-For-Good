"""Mine benchmark call examples from migration pytest files."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from benchmark.config import INPUT_SIZE_TIERS, BenchmarkCase
from benchmark.scaling import scale_args_for_tier


def _literal_value(node: ast.AST) -> object | None:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        items = [_literal_value(elt) for elt in node.elts]
        if any(item is None for item in items):
            return None
        return list(items) if isinstance(node, ast.List) else tuple(items)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _literal_value(node.operand)
        if isinstance(inner, int):
            return -inner
    return None


def _resolve_name(node: ast.AST, scope: dict[str, object]) -> object | None:
    if isinstance(node, ast.Name):
        return scope.get(node.id)
    return _literal_value(node)


def _collect_scope(body: list[ast.stmt]) -> dict[str, object]:
    scope: dict[str, object] = {}
    for stmt in body:
        if isinstance(stmt, ast.Assign):
            value = _literal_value(stmt.value)
            if value is None:
                continue
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    scope[target.id] = value
    return scope


def _mine_calls_from_file(
    path: Path,
    *,
    module: str,
    function: str,
) -> list[list[object]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls: list[list[object]] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        scope = _collect_scope(node.body)
        for stmt in ast.walk(node):
            if not isinstance(stmt, ast.Call):
                continue
            callee = stmt.func
            if not isinstance(callee, ast.Name) or callee.id != function:
                continue
            args: list[object] = []
            ok = True
            for arg in stmt.args:
                value = _resolve_name(arg, scope)
                if value is None:
                    ok = False
                    break
                args.append(value)
            if ok and args:
                calls.append(args)
    return calls


def mine_cases_from_pytests(
    py_tests_root: Path,
    *,
    module: str,
    function: str,
) -> list[BenchmarkCase]:
    """Build tiered cases using pytest call patterns as small-tier seeds."""
    tests_dir = py_tests_root / "tests"
    if not tests_dir.is_dir():
        return []

    seed_args: list[object] | None = None
    for path in sorted(tests_dir.glob("test_*.py")):
        for call_args in _mine_calls_from_file(
            path, module=module, function=function
        ):
            if call_args:
                seed_args = call_args
                break
        if seed_args is not None:
            break

    if seed_args is None:
        return []

    cases: list[BenchmarkCase] = []
    for tier in INPUT_SIZE_TIERS:
        scaled = scale_args_for_tier(seed_args, tier)
        cases.append(
            BenchmarkCase(
                name=f"{function}_{tier}",
                module=module,
                function=function,
                input_size_tier=tier,
                args_json=json.dumps(scaled),
            )
        )
    return cases


def mine_all_cases_from_pytests(
    py_tests_root: Path,
    *,
    module: str,
    functions: list[str],
) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for function in functions:
        cases.extend(
            mine_cases_from_pytests(
                py_tests_root,
                module=module,
                function=function,
            )
        )
    return cases
