"""Build a Python wheel from the original source project."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

from benchmark.cases import detect_module_name
from executor_mcp.api_signatures import detect_import_targets


def _detect_wheel_path(wheel_dir: Path) -> Path | None:
    wheels = list(wheel_dir.glob("*.whl"))
    if not wheels:
        return None
    return max(wheels, key=lambda path: (path.stat().st_mtime, path.name))


def _copy_source_tree(source_root: Path, staging: Path) -> None:
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    for path in source_root.iterdir():
        if path.name.startswith("."):
            continue
        if path.name in {"__pycache__", "target", "dist", "build"}:
            continue
        dest = staging / path.name
        if path.is_dir():
            shutil.copytree(
                path,
                dest,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".mypy_cache"),
            )
        elif path.is_file() and path.suffix == ".py":
            shutil.copy2(path, dest)


def _write_flat_setup(staging: Path, *, dist_name: str, module: str) -> None:
    setup_py = staging / "setup.py"
    setup_py.write_text(
        "from setuptools import setup\n\n"
        f"setup(name={dist_name!r}, version='0.1.0', py_modules=[{module!r}])\n",
        encoding="utf-8",
    )


def _write_package_setup(staging: Path, *, dist_name: str, packages: list[str]) -> None:
    setup_py = staging / "setup.py"
    packages_literal = ", ".join(repr(pkg) for pkg in packages)
    setup_py.write_text(
        "from setuptools import setup\n\n"
        f"setup(name={dist_name!r}, version='0.1.0', packages=[{packages_literal}])\n",
        encoding="utf-8",
    )


def _stage_project(source_root: Path, staging: Path) -> str:
    """Copy sources into staging and return the primary import module name."""
    _copy_source_tree(source_root, staging)
    dist_name = f"{source_root.name.replace('-', '_')}_python_bench"

    if (source_root / "pyproject.toml").is_file():
        return dist_name

    module = detect_module_name(source_root)
    if (staging / f"{module}.py").is_file():
        _write_flat_setup(staging, dist_name=dist_name, module=module)
        return module

    try:
        packages = detect_import_targets(source_root)
    except ValueError:
        packages = [source_root.name.replace("-", "_")]

    if packages and (staging / packages[0]).is_dir():
        _write_package_setup(staging, dist_name=dist_name, packages=packages)
        return packages[0]

    _write_flat_setup(staging, dist_name=dist_name, module=module)
    return module


def _build_wheel(project_dir: Path, wheel_dir: Path) -> tuple[bool, str]:
    """Build a wheel using uv (preferred) or python -m pip wheel."""
    wheel_dir.mkdir(parents=True, exist_ok=True)
    uv = shutil.which("uv")
    if uv is not None:
        cmd = [uv, "build", "--wheel", "--out-dir", str(wheel_dir), str(project_dir)]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        output = f"{proc.stdout}\n{proc.stderr}".strip()
        if proc.returncode == 0:
            return True, output
        pip_fallback_output = output
    else:
        pip_fallback_output = ""
    import importlib.util

    if importlib.util.find_spec("pip") is None:
        return False, pip_fallback_output or "Neither uv build nor pip is available to build Python wheels"

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "wheel",
        "--no-deps",
        "-w",
        str(wheel_dir),
        str(project_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output = f"{proc.stdout}\n{proc.stderr}".strip()
    if proc.returncode == 0:
        return True, output
    combined = "\n".join(part for part in (pip_fallback_output, output) if part)
    return False, combined or "wheel build failed"


def build_python_wheel(
    source_root: Path,
    build_root: Path,
) -> tuple[bool, str, Path | None, float]:
    """Build a wheel from the Python source tree (does not install)."""
    build_root.mkdir(parents=True, exist_ok=True)
    wheel_dir = build_root / "wheels"
    wheel_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()

    if (source_root / "pyproject.toml").is_file():
        ok, output = _build_wheel(source_root, wheel_dir)
        elapsed = time.perf_counter() - started
        if not ok:
            return False, output or "wheel build failed", None, elapsed
        wheel = _detect_wheel_path(wheel_dir)
        if wheel is None:
            return False, f"{output}\nNo Python wheel produced", None, elapsed
        return True, output, wheel, elapsed

    staging = build_root / "staging"
    _stage_project(source_root, staging)
    ok, output = _build_wheel(staging, wheel_dir)
    elapsed = time.perf_counter() - started
    if not ok:
        return False, output or "wheel build failed", None, elapsed
    wheel = _detect_wheel_path(wheel_dir)
    if wheel is None:
        return False, f"{output}\nNo Python wheel produced", None, elapsed
    return True, output, wheel, elapsed
