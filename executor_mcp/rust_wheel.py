"""Build and install Rust PyO3 wheels for migration validation."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


def detect_wheel_path(rust_root: Path) -> Path | None:
    """Return the newest wheel under rust_root/target/wheels/."""
    wheels_dir = rust_root / "target" / "wheels"
    if not wheels_dir.is_dir():
        return None
    wheels = list(wheels_dir.glob("*.whl"))
    if not wheels:
        return None
    return max(wheels, key=lambda path: (path.stat().st_mtime, path.name))


def _wheel_install_command(wheel: Path) -> list[str]:
    """Return a command that installs a wheel into the active interpreter."""
    wheel_arg = str(wheel)
    install_flags = ["--force-reinstall", "--no-deps"]

    uv = shutil.which("uv")
    if uv is not None:
        return [
            uv,
            "pip",
            "install",
            "--python",
            sys.executable,
            wheel_arg,
            *install_flags,
        ]

    if importlib.util.find_spec("pip") is not None:
        return [sys.executable, "-m", "pip", "install", wheel_arg, *install_flags]

    raise RuntimeError(
        "Cannot install wheel: uv was not found on PATH and pip is not available in this environment"
    )


def install_wheel(wheel: Path) -> tuple[bool, str]:
    """Install a wheel into the active interpreter."""
    try:
        install_cmd = _wheel_install_command(wheel)
    except RuntimeError as exc:
        return False, str(exc)

    install = subprocess.run(
        install_cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{install.stdout}\n{install.stderr}".strip()
    if install.returncode != 0:
        return False, output or "wheel install failed"
    return True, f"Installed {wheel.name}\n{output}".strip()


def build_rust_wheel(rust_root: Path) -> tuple[bool, str, Path | None]:
    """Build a release wheel with maturin (does not install)."""
    build = subprocess.run(
        [sys.executable, "-m", "maturin", "build", "--release"],
        cwd=rust_root,
        capture_output=True,
        text=True,
        check=False,
    )
    build_output = f"{build.stdout}\n{build.stderr}".strip()
    if build.returncode != 0:
        return False, build_output or "maturin build failed", None

    wheel = detect_wheel_path(rust_root)
    if wheel is None:
        return False, f"{build_output}\nNo wheel found under target/wheels/", None
    return True, build_output, wheel


def build_and_install_wheel(rust_root: Path) -> tuple[bool, str]:
    """Build a release wheel with maturin and install it into the active venv."""
    ok, build_output, wheel = build_rust_wheel(rust_root)
    if not ok or wheel is None:
        return False, build_output

    install_ok, install_output = install_wheel(wheel)
    combined = f"{build_output}\n{install_output}".strip()
    return install_ok, combined
