"""Measure build artifacts and wheel sizes."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactMetrics:
    python_source_bytes: int
    python_wheel_bytes: int
    python_wheel_path: str
    python_build_seconds: float
    rust_wheel_bytes: int
    rust_native_extension_bytes: int
    rust_wheel_path: str
    rust_build_seconds: float

    @property
    def wheel_bytes(self) -> int:
        """Backward-compatible alias for Rust wheel size."""
        return self.rust_wheel_bytes

    @property
    def native_extension_bytes(self) -> int:
        """Backward-compatible alias for Rust native extension size."""
        return self.rust_native_extension_bytes

    @property
    def build_seconds(self) -> float:
        """Backward-compatible alias for Rust build time."""
        return self.rust_build_seconds


def _python_source_bytes(source_root: Path) -> int:
    total = 0
    for path in source_root.rglob("*.py"):
        if path.name.startswith("_") and path.name != "__init__.py":
            continue
        total += path.stat().st_size
    return total


def _native_extension_bytes(wheel: Path) -> int:
    total = 0
    with zipfile.ZipFile(wheel, "r") as archive:
        for name in archive.namelist():
            if name.endswith((".so", ".pyd", ".dylib")):
                total += archive.getinfo(name).file_size
    return total


def collect_artifacts(
    source_root: Path,
    *,
    python_wheel: Path,
    rust_wheel: Path,
    python_build_seconds: float = 0.0,
    rust_build_seconds: float = 0.0,
) -> ArtifactMetrics:
    """Collect artifact sizes from built Python and Rust wheels."""
    return ArtifactMetrics(
        python_source_bytes=_python_source_bytes(source_root),
        python_wheel_bytes=python_wheel.stat().st_size,
        python_wheel_path=str(python_wheel),
        python_build_seconds=python_build_seconds,
        rust_wheel_bytes=rust_wheel.stat().st_size,
        rust_native_extension_bytes=_native_extension_bytes(rust_wheel),
        rust_wheel_path=str(rust_wheel),
        rust_build_seconds=rust_build_seconds,
    )


def format_bytes(num_bytes: int) -> str:
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.2f} MiB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.1f} KiB"
    return f"{num_bytes} B"
