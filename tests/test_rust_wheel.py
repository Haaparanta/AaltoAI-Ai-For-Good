"""Tests for Rust wheel build helpers."""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from executor_mcp.rust_wheel import build_and_install_wheel, detect_wheel_path


def test_detect_wheel_path_returns_newest(tmp_path: Path) -> None:
    wheels_dir = tmp_path / "target" / "wheels"
    wheels_dir.mkdir(parents=True)
    older = wheels_dir / "old-0.1.0-py3-none-any.whl"
    newer = wheels_dir / "new-0.1.0-py3-none-any.whl"
    older.write_text("old", encoding="utf-8")
    newer.write_text("new", encoding="utf-8")
    now = time.time()
    os.utime(older, (now - 10, now - 10))
    os.utime(newer, (now, now))
    assert detect_wheel_path(tmp_path) == newer


@patch("executor_mcp.rust_wheel.subprocess.run")
def test_build_and_install_wheel_success(mock_run: MagicMock, tmp_path: Path) -> None:
    wheels_dir = tmp_path / "target" / "wheels"
    wheels_dir.mkdir(parents=True)
    wheel = wheels_dir / "pkg-0.1.0-cp312-cp312-linux_x86_64.whl"
    wheel.write_text("wheel", encoding="utf-8")

    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="built", stderr=""),
        MagicMock(returncode=0, stdout="installed", stderr=""),
    ]

    ok, output = build_and_install_wheel(tmp_path)
    assert ok is True
    assert "installed" in output
    assert mock_run.call_count == 2


@patch("executor_mcp.rust_wheel.subprocess.run")
def test_build_and_install_wheel_build_failure(
    mock_run: MagicMock, tmp_path: Path
) -> None:
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="maturin failed")
    ok, output = build_and_install_wheel(tmp_path)
    assert ok is False
    assert "maturin failed" in output
