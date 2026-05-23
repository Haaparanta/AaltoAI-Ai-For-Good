"""Build and install Rust PyO3 wheels for migration validation."""

from __future__ import annotations

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


def build_and_install_wheel(rust_root: Path) -> tuple[bool, str]:
    """Build a release wheel with maturin and pip-install it."""
    build = subprocess.run(
        [sys.executable, "-m", "maturin", "build", "--release"],
        cwd=rust_root,
        capture_output=True,
        text=True,
        check=False,
    )
    build_output = f"{build.stdout}\n{build.stderr}".strip()
    if build.returncode != 0:
        return False, build_output or "maturin build failed"

    wheel = detect_wheel_path(rust_root)
    if wheel is None:
        return False, f"{build_output}\nNo wheel found under target/wheels/"

    install = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            str(wheel),
            "--force-reinstall",
            "--no-deps",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    install_output = f"{install.stdout}\n{install.stderr}".strip()
    combined = f"{build_output}\nInstalled {wheel.name}\n{install_output}".strip()
    return install.returncode == 0, combined
