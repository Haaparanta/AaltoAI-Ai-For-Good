"""Sibling migration directories; original project stays read-only."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from executor_mcp.api_signatures import API_SIGNATURES_DIR

PREFIX_SOURCE = "source"
PREFIX_PY_TESTS = "py_tests"
PREFIX_RUST = "rust"
PREFIX_RUST_TESTS = "rust_tests"

_WRITE_PREFIXES = (PREFIX_PY_TESTS, PREFIX_RUST, PREFIX_RUST_TESTS)


@dataclass(frozen=True)
class MigrationLayout:
    """Paths for source (read-only) and migration output siblings."""

    source_root: Path
    py_tests_root: Path
    rust_root: Path
    rust_tests_root: Path

    @classmethod
    def from_source_project(cls, source_project: Path | str) -> MigrationLayout:
        source = Path(source_project).expanduser().resolve()
        parent = source.parent
        name = source.name
        return cls(
            source_root=source,
            py_tests_root=parent / f"{name}_migration_py_tests",
            rust_root=parent / f"{name}_migration_rust",
            rust_tests_root=parent / f"{name}_migration_rust_tests",
        )

    def ensure_scaffold(self) -> None:
        """Create migration directories and minimal Rust workspace files."""
        (self.py_tests_root / "tests").mkdir(parents=True, exist_ok=True)
        (self.py_tests_root / API_SIGNATURES_DIR).mkdir(parents=True, exist_ok=True)
        self._ensure_python_lint_config()
        (self.rust_root / "src").mkdir(parents=True, exist_ok=True)
        (self.rust_tests_root / "tests").mkdir(parents=True, exist_ok=True)

        rust_cargo = self.rust_root / "Cargo.toml"
        if not rust_cargo.is_file():
            rust_cargo.write_text(
                '[package]\nname = "migrated"\nversion = "0.1.0"\nedition = "2021"\n',
                encoding="utf-8",
            )
        lib_rs = self.rust_root / "src/lib.rs"
        if not lib_rs.is_file():
            lib_rs.write_text("pub fn migrated_stub() {}\n", encoding="utf-8")

        rust_dep_path = Path("..") / self.rust_root.name
        tests_cargo = self.rust_tests_root / "Cargo.toml"
        if not tests_cargo.is_file():
            tests_cargo.write_text(
                f'[package]\nname = "migrated-tests"\nversion = "0.1.0"\nedition = "2021"\n\n'
                f'[dependencies]\nmigrated = {{ path = "{rust_dep_path.as_posix()}" }}\n',
                encoding="utf-8",
            )

    @property
    def api_signatures_cache_root(self) -> Path:
        return self.py_tests_root / API_SIGNATURES_DIR

    def _ensure_python_lint_config(self) -> None:
        flake8_path = self.py_tests_root / ".flake8"
        if not flake8_path.is_file():
            flake8_path.write_text(
                "[flake8]\n"
                "max-line-length = 88\n"
                "extend-ignore = E203,W503\n",
                encoding="utf-8",
            )

        mypy_path = self.py_tests_root / "mypy.ini"
        if not mypy_path.is_file():
            source_name = self.source_root.name
            mypy_path.write_text(
                "[mypy]\n"
                "python_version = 3.10\n"
                f"mypy_path = ../{source_name}\n"
                "namespace_packages = True\n"
                "ignore_missing_imports = False\n",
                encoding="utf-8",
            )

    def describe_paths(self) -> str:
        return (
            f"Source (read-only): {self.source_root}\n"
            f"Python tests: {self.py_tests_root}\n"
            f"Rust code: {self.rust_root}\n"
            f"Rust tests: {self.rust_tests_root}"
        )

    def tool_path_guide(self) -> str:
        return (
            "Use these path prefixes in tools (never modify source/):\n"
            f"- `{PREFIX_SOURCE}/` — read original Python project files\n"
            f"- `{PREFIX_PY_TESTS}/` — migration_plan.md, pytest under tests/\n"
            f"- `{PREFIX_RUST}/` — Cargo.toml, src/ implementation\n"
            f"- `{PREFIX_RUST_TESTS}/` — integration tests under tests/"
        )

    def resolve_read(self, user_path: str) -> tuple[Path, str]:
        """Map a tool path to (root, relative path within root)."""
        normalized = user_path.strip().replace("\\", "/")
        for prefix, root in (
            (PREFIX_SOURCE, self.source_root),
            (PREFIX_PY_TESTS, self.py_tests_root),
            (PREFIX_RUST, self.rust_root),
            (PREFIX_RUST_TESTS, self.rust_tests_root),
        ):
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                rel = normalized[len(prefix) :].lstrip("/")
                return root, rel or "."
        return self.source_root, normalized

    def resolve_write(self, user_path: str) -> tuple[Path, str]:
        """Writes must target py_tests/, rust/, or rust_tests/ only."""
        normalized = user_path.strip().replace("\\", "/")
        for prefix, root in (
            (PREFIX_PY_TESTS, self.py_tests_root),
            (PREFIX_RUST, self.rust_root),
            (PREFIX_RUST_TESTS, self.rust_tests_root),
        ):
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                rel = normalized[len(prefix) :].lstrip("/")
                if not rel:
                    raise ValueError(f"Write path must include a file under {prefix}/")
                return root, rel
        raise ValueError(
            "Writes are not allowed in the original project. Use "
            f"{PREFIX_PY_TESTS}/, {PREFIX_RUST}/, or {PREFIX_RUST_TESTS}/ prefixes."
        )

    def resolve_command_cwd(self, cwd: str | None) -> Path:
        if not cwd or not cwd.strip():
            return self.py_tests_root
        normalized = cwd.strip().replace("\\", "/")
        mapping = {
            PREFIX_SOURCE: self.source_root,
            PREFIX_PY_TESTS: self.py_tests_root,
            PREFIX_RUST: self.rust_root,
            PREFIX_RUST_TESTS: self.rust_tests_root,
        }
        for prefix, root in mapping.items():
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                return root
        return self.py_tests_root
