"""Install wheels into isolated directories to avoid site-packages name clashes."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


def wheel_env_dir(measurements_root: Path, backend: str) -> Path:
    return measurements_root / ".wheel_env" / backend


def install_wheel_isolated(wheel: Path, env_dir: Path) -> tuple[bool, str]:
    """Install a wheel into env_dir (--target), replacing any previous contents."""
    if env_dir.exists():
        shutil.rmtree(env_dir)
    env_dir.mkdir(parents=True, exist_ok=True)

    wheel_arg = str(wheel.resolve())
    install_flags = ["--force-reinstall", "--no-deps", "--target", str(env_dir)]

    uv = shutil.which("uv")
    if uv is not None:
        cmd = [uv, "pip", "install", "--python", sys.executable, wheel_arg, *install_flags]
    elif importlib.util.find_spec("pip") is not None:
        cmd = [sys.executable, "-m", "pip", "install", wheel_arg, *install_flags]
    else:
        return False, "Neither uv nor pip is available for isolated wheel install"

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output = f"{proc.stdout}\n{proc.stderr}".strip()
    if proc.returncode != 0:
        return False, output or "isolated wheel install failed"
    return True, f"Installed {wheel.name} into {env_dir}\n{output}".strip()


def subprocess_env(site_dir: Path) -> dict[str, str]:
    """Environment for benchmark subprocesses: prefer isolated site over venv packages."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(site_dir.resolve())
    env["BENCHMARK_SITE"] = str(site_dir.resolve())
    return env
