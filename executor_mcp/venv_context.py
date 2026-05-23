"""Resolve and introspect a source-project Python virtual environment."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SOURCE_VENV_ENV = "EXECUTOR_SOURCE_VENV"
MAX_INSTALLED_PACKAGES = 200


class VenvContextError(ValueError):
    """Raised when a source venv path is invalid or unusable."""


@dataclass(frozen=True)
class VenvContext:
    """Resolved Python venv used for source-project import resolution."""

    root: Path
    python: Path
    site_packages: tuple[Path, ...]


def _venv_python_candidates(root: Path) -> list[Path]:
    if sys.platform == "win32":
        return [
            root / "Scripts" / "python.exe",
            root / "Scripts" / "python",
        ]
    return [
        root / "bin" / "python",
        root / "bin" / "python3",
    ]


def _resolve_python_executable(root: Path) -> Path:
    for candidate in _venv_python_candidates(root):
        if candidate.is_file():
            return candidate
    raise VenvContextError(
        f"No Python interpreter found under venv {root}. "
        "Expected bin/python (or Scripts/python.exe on Windows)."
    )


def _discover_site_packages(python: Path, venv_root: Path) -> tuple[Path, ...]:
    script = (
        "import json, sysconfig\n"
        "paths = sysconfig.get_paths()\n"
        "pure = paths.get('purelib')\n"
        "plat = paths.get('platlib')\n"
        "seen = []\n"
        "for p in (pure, plat):\n"
        "    if p and p not in seen:\n"
        "        seen.append(p)\n"
        "print(json.dumps(seen))\n"
    )
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(venv_root)
    result = subprocess.run(
        [str(python), "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = f"{result.stdout}\n{result.stderr}".strip()
        raise VenvContextError(
            f"Failed to locate site-packages for venv python {python}: {detail}"
        )
    try:
        raw_paths = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise VenvContextError(
            f"Unexpected site-packages output from venv python {python}"
        ) from exc

    site_packages: list[Path] = []
    for raw in raw_paths:
        path = Path(str(raw)).resolve()
        if path.is_dir():
            site_packages.append(path)
    if not site_packages:
        raise VenvContextError(
            f"No site-packages directories found for venv python {python}"
        )
    return tuple(site_packages)


def resolve_source_venv(path: Path | str) -> VenvContext:
    """Validate and resolve a source-project virtual environment."""
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise VenvContextError(f"Source venv path is not a directory: {root}")
    if not (root / "pyvenv.cfg").is_file():
        raise VenvContextError(
            f"Source venv path does not look like a Python venv (missing pyvenv.cfg): {root}"
        )

    python = _resolve_python_executable(root)
    site_packages = _discover_site_packages(python, root)
    return VenvContext(root=root, python=python, site_packages=site_packages)


def resolve_source_venv_from_env() -> VenvContext | None:
    """Return venv context from EXECUTOR_SOURCE_VENV when set."""
    override = os.environ.get(SOURCE_VENV_ENV)
    if not override:
        return None
    return resolve_source_venv(override)


def build_import_env(
    ctx: VenvContext,
    source_root: Path,
    *,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build subprocess env with source root and venv site-packages on PYTHONPATH."""
    env = (base_env or os.environ.copy()).copy()
    pythonpath_parts = [str(source_root.resolve()), *map(str, ctx.site_packages)]
    existing = env.get("PYTHONPATH", "")
    if existing:
        pythonpath_parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    bin_dir = ctx.python.parent
    env["PATH"] = os.pathsep.join([str(bin_dir), env.get("PATH", "")])
    env["VIRTUAL_ENV"] = str(ctx.root)
    return env


def list_installed_packages(ctx: VenvContext) -> list[dict[str, str]]:
    """Return installed distribution names and versions from the venv."""
    script = (
        "import importlib.metadata as md\n"
        "import json\n"
        f"limit = {MAX_INSTALLED_PACKAGES}\n"
        "rows = []\n"
        "for dist in sorted(md.distributions(), key=lambda d: (d.metadata.get('Name') or d.name or '').lower()):\n"
        "    name = dist.metadata.get('Name') or dist.name\n"
        "    if not name:\n"
        "        continue\n"
        "    rows.append({'name': name, 'version': dist.version})\n"
        "    if len(rows) >= limit:\n"
        "        break\n"
        "print(json.dumps(rows))\n"
    )
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(ctx.root)
    result = subprocess.run(
        [str(ctx.python), "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = f"{result.stdout}\n{result.stderr}".strip()
        raise VenvContextError(
            f"Failed to list installed packages for venv {ctx.root}: {detail}"
        )
    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise VenvContextError(
            f"Unexpected package list output from venv python {ctx.python}"
        ) from exc
    if not isinstance(payload, list):
        raise VenvContextError(
            f"Unexpected package list output from venv python {ctx.python}"
        )
    return [
        {"name": str(row["name"]), "version": str(row["version"])}
        for row in payload
        if isinstance(row, dict) and "name" in row and "version" in row
    ]


def stubgen_executable(ctx: VenvContext) -> list[str]:
    """Return argv prefix to invoke stubgen from the venv."""
    stubgen = ctx.python.with_name("stubgen")
    if stubgen.is_file():
        return [str(stubgen)]
    return [str(ctx.python), "-m", "mypy.stubgen"]


def mypy_executable(ctx: VenvContext) -> list[str]:
    """Return argv prefix to invoke mypy from the source venv."""
    mypy_bin = ctx.python.with_name("mypy")
    if mypy_bin.is_file():
        return [str(mypy_bin)]

    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(ctx.root)
    probe = subprocess.run(
        [str(ctx.python), "-c", "import mypy"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode == 0:
        return [str(ctx.python), "-m", "mypy"]

    raise VenvContextError(
        "mypy not found in source venv; install mypy in the source environment"
    )