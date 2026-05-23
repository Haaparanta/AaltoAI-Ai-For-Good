"""Sibling migration directories; original project stays read-only."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from executor_mcp.api_signatures import API_SIGNATURES_DIR, detect_import_targets
from executor_mcp.python_test_quality import FLAKE8_MAX_LINE_LENGTH
from executor_mcp.venv_context import VenvContext, resolve_source_venv

PREFIX_SOURCE = "source"
PREFIX_PY_TESTS = "py_tests"
PREFIX_RUST = "rust"
PREFIX_MEASUREMENTS = "measurements"

_WRITE_PREFIXES = (PREFIX_PY_TESTS, PREFIX_RUST, PREFIX_MEASUREMENTS)


def _primary_package_name(source_root: Path) -> str:
    try:
        targets = detect_import_targets(source_root)
        if targets:
            return targets[0]
    except ValueError:
        pass
    return source_root.name.replace("-", "_")


def _pyo3_cargo_toml(package_name: str) -> str:
    return (
        "[package]\n"
        f'name = "{package_name}"\n'
        'version = "0.1.0"\n'
        'edition = "2021"\n\n'
        "[lib]\n"
        f'name = "{package_name}"\n'
        'crate-type = ["cdylib"]\n\n'
        "[dependencies]\n"
        'pyo3 = { version = "0.23", features = ["extension-module"] }\n'
    )


def _pyo3_pyproject_toml(package_name: str) -> str:
    return (
        "[build-system]\n"
        'requires = ["maturin>=1.0,<2.0"]\n'
        'build-backend = "maturin"\n\n'
        "[project]\n"
        f'name = "{package_name}"\n'
        'requires-python = ">=3.10"\n\n'
        "[tool.maturin]\n"
        'features = ["pyo3/extension-module"]\n'
    )


def pyo3_lib_rs_scaffold(package_name: str) -> str:
    """Return the minimal PyO3 lib.rs scaffold written for new migrations."""
    return (
        "use pyo3::prelude::*;\n\n"
        "#[pymodule]\n"
        f"fn {package_name}(m: &Bound<'_, PyModule>) -> PyResult<()> {{\n"
        "    Ok(())\n"
        "}\n"
    )


def _pyo3_lib_rs(package_name: str) -> str:
    return pyo3_lib_rs_scaffold(package_name)


ORCHESTRATOR_STATE_DIR = ".orchestrator"
CHECKPOINT_FILENAME = "state.json"


@dataclass(frozen=True)
class MigrationLayout:
    """Paths for source (read-only) and migration output siblings."""

    source_root: Path
    py_tests_root: Path
    rust_root: Path
    source_venv: VenvContext | None = None

    @classmethod
    def from_source_project(
        cls,
        source_project: Path | str,
        source_venv: Path | str | None = None,
    ) -> MigrationLayout:
        source = Path(source_project).expanduser().resolve()
        parent = source.parent
        name = source.name
        venv_ctx = resolve_source_venv(source_venv) if source_venv else None
        return cls(
            source_root=source,
            py_tests_root=parent / f"{name}_migration_py_tests",
            rust_root=parent / f"{name}_migration_rust",
            source_venv=venv_ctx,
        )

    def ensure_scaffold(self) -> None:
        """Create migration directories and minimal PyO3/maturin scaffold."""
        (self.py_tests_root / "tests").mkdir(parents=True, exist_ok=True)
        (self.py_tests_root / API_SIGNATURES_DIR).mkdir(parents=True, exist_ok=True)
        self._ensure_python_lint_config()
        (self.rust_root / "src").mkdir(parents=True, exist_ok=True)

        package_name = _primary_package_name(self.source_root)

        rust_cargo = self.rust_root / "Cargo.toml"
        if not rust_cargo.is_file():
            rust_cargo.write_text(_pyo3_cargo_toml(package_name), encoding="utf-8")

        pyproject = self.rust_root / "pyproject.toml"
        if not pyproject.is_file():
            pyproject.write_text(_pyo3_pyproject_toml(package_name), encoding="utf-8")

        lib_rs = self.rust_root / "src/lib.rs"
        if not lib_rs.is_file():
            lib_rs.write_text(_pyo3_lib_rs(package_name), encoding="utf-8")

    @property
    def api_signatures_cache_root(self) -> Path:
        return self.py_tests_root / API_SIGNATURES_DIR

    @property
    def checkpoint_path(self) -> Path:
        return self.py_tests_root / ORCHESTRATOR_STATE_DIR / CHECKPOINT_FILENAME

    @property
    def measurements_root(self) -> Path:
        name = self.source_root.name
        return self.source_root.parent / f"{name}_measurements"

    def _ensure_python_lint_config(self) -> None:
        flake8_path = self.py_tests_root / ".flake8"
        flake8_path.write_text(
            "[flake8]\n"
            f"max-line-length = {FLAKE8_MAX_LINE_LENGTH}\n"
            "extend-ignore = E203,W503\n",
            encoding="utf-8",
        )

        mypy_path = self.py_tests_root / "mypy.ini"
        if not mypy_path.is_file():
            mypy_path.write_text(
                "[mypy]\n"
                "python_version = 3.10\n"
                f"mypy_path = {self.source_root.resolve()}\n"
                "namespace_packages = True\n"
                "ignore_missing_imports = False\n",
                encoding="utf-8",
            )

    def describe_paths(self) -> str:
        if self.source_venv is not None:
            venv_line = f"Source venv: {self.source_venv.root}"
        else:
            venv_line = "Source venv: (not configured)"
        return (
            f"Source (read-only): {self.source_root}\n"
            f"{venv_line}\n"
            f"Python tests: {self.py_tests_root}\n"
            f"Rust code (PyO3): {self.rust_root}\n"
            f"Benchmarks: {self.measurements_root}"
        )

    def tool_path_guide(self) -> str:
        return (
            "Use these path prefixes in tools (never modify source/):\n"
            f"- `{PREFIX_SOURCE}/` — read original Python project files\n"
            f"- `{PREFIX_PY_TESTS}/` — migration_plan.md, pytest under tests/\n"
            f"- `{PREFIX_RUST}/` — Cargo.toml, pyproject.toml, PyO3 src/\n"
            f"- `{PREFIX_MEASUREMENTS}/` — benchmark reports, graphs, optional benchmark_suite.toml"
        )

    def resolve_read(self, user_path: str) -> tuple[Path, str]:
        """Map a tool path to (root, relative path within root)."""
        normalized = user_path.strip().replace("\\", "/")
        for prefix, root in (
            (PREFIX_SOURCE, self.source_root),
            (PREFIX_PY_TESTS, self.py_tests_root),
            (PREFIX_RUST, self.rust_root),
            (PREFIX_MEASUREMENTS, self.measurements_root),
        ):
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                rel = normalized[len(prefix) :].lstrip("/")
                return root, rel or "."
        return self.source_root, normalized

    def resolve_write(self, user_path: str) -> tuple[Path, str]:
        """Writes must target py_tests/, rust/, or measurements/."""
        normalized = user_path.strip().replace("\\", "/")
        for prefix, root in (
            (PREFIX_PY_TESTS, self.py_tests_root),
            (PREFIX_RUST, self.rust_root),
            (PREFIX_MEASUREMENTS, self.measurements_root),
        ):
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                rel = normalized[len(prefix) :].lstrip("/")
                if not rel:
                    raise ValueError(f"Write path must include a file under {prefix}/")
                return root, rel
        raise ValueError(
            "Writes are not allowed in the original project. Use "
            f"{PREFIX_PY_TESTS}/, {PREFIX_RUST}/, or {PREFIX_MEASUREMENTS}/ prefixes."
        )

    def resolve_command_cwd(self, cwd: str | None) -> Path:
        if not cwd or not cwd.strip():
            return self.py_tests_root
        normalized = cwd.strip().replace("\\", "/")
        mapping = {
            PREFIX_SOURCE: self.source_root,
            PREFIX_PY_TESTS: self.py_tests_root,
            PREFIX_RUST: self.rust_root,
            PREFIX_MEASUREMENTS: self.measurements_root,
        }
        for prefix, root in mapping.items():
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                return root
        return self.py_tests_root
