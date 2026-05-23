"""Generate and cache Python API signatures (.pyi) for test authoring."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

API_SIGNATURES_DIR = ".api_signatures"


class ApiSignaturesError(ValueError):
    """Raised when API signature generation or lookup fails."""


@dataclass(frozen=True)
class ApiSignaturesResult:
    """Outcome of get_api_signatures."""

    modules: list[str]
    content: str | None
    source: str
    cache_dir: str
    regenerated: bool


def detect_import_targets(source_root: Path) -> list[str]:
    """Return top-level package/module names importable from source_root."""
    targets: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        if name and name not in seen and not name.startswith("_"):
            seen.add(name)
            targets.append(name)

    pyproject = source_root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8")
        for match in re.finditer(
            r'^\s*(?:packages\s*=\s*\[\s*"([^"]+)"|name\s*=\s*"([^"]+)")',
            text,
            re.MULTILINE,
        ):
            add(match.group(1) or match.group(2) or "")

    for child in sorted(source_root.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_dir() and (child / "__init__.py").is_file():
            add(child.name)
        elif child.suffix == ".py" and child.name != "__init__.py":
            add(child.stem)

    setup_cfg = source_root / "setup.cfg"
    if setup_cfg.is_file():
        text = setup_cfg.read_text(encoding="utf-8")
        for match in re.finditer(r"^name\s*=\s*(.+)$", text, re.MULTILINE):
            add(match.group(1).strip())

    if not targets:
        raise ApiSignaturesError(
            f"No import targets detected under {source_root}. "
            "Add a package directory or top-level .py module."
        )
    return targets


def _module_to_stub_path(cache_root: Path, module: str) -> Path:
    parts = module.split(".")
    if len(parts) == 1:
        package_init = cache_root / parts[0] / "__init__.pyi"
        if package_init.is_file():
            return package_init
        return cache_root / f"{module}.pyi"
    return cache_root / Path(*parts[:-1]) / f"{parts[-1]}.pyi"


def _stub_path_to_module(cache_root: Path, path: Path) -> str:
    rel = path.relative_to(cache_root)
    if len(rel.parts) == 1:
        return rel.stem
    if rel.name == "__init__.pyi":
        return ".".join(rel.parts[:-1])
    return ".".join([*rel.parts[:-1], rel.stem])


def _collect_stub_modules(cache_root: Path) -> list[str]:
    if not cache_root.is_dir():
        return []
    modules: list[str] = []
    for path in sorted(cache_root.rglob("*.pyi")):
        modules.append(_stub_path_to_module(cache_root, path))
    return modules


def _stubgen_executable() -> str:
    exe = shutil.which("stubgen")
    if exe:
        return exe
    venv_stubgen = Path(sys.executable).with_name("stubgen")
    if venv_stubgen.is_file():
        return str(venv_stubgen)
    raise ApiSignaturesError("stubgen not found; install mypy")


def _run_stubgen_cli(
    target: str,
    *,
    source_root: Path,
    cache_root: Path,
    mode: str = "package",
) -> tuple[bool, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(source_root), env.get("PYTHONPATH", "")])
    flag = "-p" if mode == "package" else "-m"
    cmd = [
        _stubgen_executable(),
        "--include-docstrings",
        "--output",
        str(cache_root),
        flag,
        target,
    ]
    result = subprocess.run(
        cmd,
        cwd=source_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}".strip()
    return result.returncode == 0, output


def _run_stubgen_programmatic(
    target: str,
    *,
    source_root: Path,
    cache_root: Path,
) -> tuple[bool, str]:
    """Fallback stubgen invocations when package mode fails."""
    ok, output = _run_stubgen_cli(
        target,
        source_root=source_root,
        cache_root=cache_root,
        mode="module",
    )
    if ok:
        return True, output

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(source_root), env.get("PYTHONPATH", "")])
    cmd = [
        _stubgen_executable(),
        "--include-docstrings",
        "--ignore-errors",
        "--output",
        str(cache_root),
        "-p",
        target,
    ]
    result = subprocess.run(
        cmd,
        cwd=source_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    retry_output = f"{result.stdout}\n{result.stderr}".strip()
    return result.returncode == 0, output or retry_output


def generate_api_signatures(
    source_root: Path,
    cache_root: Path,
    *,
    refresh: bool = False,
) -> tuple[list[str], str]:
    """Generate .pyi stubs for all detected import targets."""
    if refresh and cache_root.is_dir():
        for path in cache_root.rglob("*.pyi"):
            path.unlink(missing_ok=True)

    existing = _collect_stub_modules(cache_root)
    if existing and not refresh:
        return existing, "cache"

    cache_root.mkdir(parents=True, exist_ok=True)
    targets = detect_import_targets(source_root)
    sources: list[str] = []
    errors: list[str] = []

    for target in targets:
        ok, output = _run_stubgen_cli(target, source_root=source_root, cache_root=cache_root)
        if ok:
            sources.append("stubgen")
            continue
        ok, fallback_output = _run_stubgen_programmatic(
            target, source_root=source_root, cache_root=cache_root
        )
        if ok:
            sources.append("programmatic")
        else:
            errors.append(f"{target}: {output or fallback_output}")

    modules = _collect_stub_modules(cache_root)
    if not modules:
        detail = "; ".join(errors) if errors else "unknown error"
        raise ApiSignaturesError(f"Failed to generate API signatures: {detail}")

    source_label = sources[0] if sources else "cache"
    if len(set(sources)) > 1:
        source_label = "mixed"
    return modules, source_label


def get_api_signatures_impl(
    source_root: Path,
    cache_root: Path,
    *,
    module: str | None = None,
    refresh: bool = False,
) -> ApiSignaturesResult:
    """Return cached or freshly generated API signature stubs."""
    cache_tool_path = f"py_tests/{API_SIGNATURES_DIR}/"
    regenerated = False

    existing = _collect_stub_modules(cache_root)
    if refresh or not existing:
        modules, source = generate_api_signatures(
            source_root, cache_root, refresh=refresh
        )
        regenerated = True
    else:
        modules = existing
        source = "cache"

    content: str | None = None
    if module:
        stub_path = _module_to_stub_path(cache_root, module)
        if not stub_path.is_file():
            raise ApiSignaturesError(
                f"No stub found for module {module!r}. "
                f"Available modules: {', '.join(modules) or '(none)'}"
            )
        content = stub_path.read_text(encoding="utf-8")

    return ApiSignaturesResult(
        modules=modules,
        content=content,
        source=source,
        cache_dir=cache_tool_path,
        regenerated=regenerated,
    )


def result_to_dict(result: ApiSignaturesResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "modules": result.modules,
        "source": result.source,
        "cache_dir": result.cache_dir,
        "regenerated": result.regenerated,
    }
    if result.content is not None:
        payload["content"] = result.content
    return payload


def resolve_api_roots(workspace_root: Path) -> tuple[Path, Path]:
    """Resolve source and cache directories for API signature generation."""
    source_candidate = workspace_root / "source"
    if source_candidate.is_dir():
        source_root = source_candidate
    else:
        source_root = workspace_root

    py_tests = workspace_root / "py_tests"
    if py_tests.is_dir():
        cache_root = py_tests / API_SIGNATURES_DIR
    else:
        cache_root = workspace_root / API_SIGNATURES_DIR
    cache_root.mkdir(parents=True, exist_ok=True)
    return source_root, cache_root


def register(mcp: Any, workspace_root: Path) -> None:
    """Register the get_api_signatures tool on the MCP server."""
    from mcp.server.fastmcp import FastMCP

    if not isinstance(mcp, FastMCP):
        raise TypeError("mcp must be a FastMCP instance")

    @mcp.tool()
    def get_api_signatures(
        module: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Load public API signatures (.pyi stubs) for the source project."""
        source_root, cache_root = resolve_api_roots(workspace_root)
        try:
            result = get_api_signatures_impl(
                source_root,
                cache_root,
                module=module,
                refresh=refresh,
            )
        except ApiSignaturesError as exc:
            raise ValueError(str(exc)) from exc
        return {"ok": True, **result_to_dict(result)}
