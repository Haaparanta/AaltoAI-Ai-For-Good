"""Auto-generate benchmark cases from common API shapes."""

from __future__ import annotations

import json
import random
import string
from pathlib import Path

from benchmark.config import INPUT_SIZE_TIERS, BenchmarkCase

_TIER_SCALES: dict[str, dict[str, int]] = {
    "small": {"n": 100, "list_len": 50, "word_len": 5, "text_len": 50},
    "medium": {"n": 1_000, "list_len": 500, "word_len": 8, "text_len": 500},
    "large": {"n": 10_000, "list_len": 5_000, "word_len": 12, "text_len": 2_000},
    "xlarge": {"n": 100_000, "list_len": 20_000, "word_len": 16, "text_len": 10_000},
}


def _random_word(length: int, rng: random.Random) -> str:
    return "".join(rng.choice(string.ascii_lowercase) for _ in range(length))


def _cases_for_get_primes(module: str) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for tier in INPUT_SIZE_TIERS:
        n = _TIER_SCALES[tier]["n"]
        cases.append(
            BenchmarkCase(
                name=f"get_primes_{tier}",
                module=module,
                function="get_primes",
                input_size_tier=tier,
                args_json=json.dumps([n]),
            )
        )
    return cases


def _cases_for_group_anagrams(module: str) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    rng = random.Random(42)
    for tier in INPUT_SIZE_TIERS:
        scale = _TIER_SCALES[tier]
        words = [
            _random_word(scale["word_len"], rng)
            for _ in range(scale["list_len"])
        ]
        cases.append(
            BenchmarkCase(
                name=f"group_anagrams_{tier}",
                module=module,
                function="group_anagrams",
                input_size_tier=tier,
                args_json=json.dumps([words]),
            )
        )
    return cases


def _cases_for_roman_to_int(module: str) -> list[BenchmarkCase]:
    roman = "M" * 100 + "CMXCIX" * 10
    cases: list[BenchmarkCase] = []
    for tier in INPUT_SIZE_TIERS:
        length = min(_TIER_SCALES[tier]["text_len"], len(roman))
        cases.append(
            BenchmarkCase(
                name=f"roman_to_int_{tier}",
                module=module,
                function="roman_to_int",
                input_size_tier=tier,
                args_json=json.dumps([roman[:length]]),
            )
        )
    return cases


def _cases_for_cipher(module: str) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    rng = random.Random(7)
    for tier in INPUT_SIZE_TIERS:
        length = _TIER_SCALES[tier]["text_len"]
        text = "".join(rng.choice(string.ascii_letters + " ") for _ in range(length))
        cases.append(
            BenchmarkCase(
                name=f"cipher_{tier}",
                module=module,
                function="cipher",
                input_size_tier=tier,
                args_json=json.dumps([text, 3]),
            )
        )
    return cases


def _cases_for_is_pangram(module: str) -> list[BenchmarkCase]:
    alphabet = string.ascii_lowercase
    cases: list[BenchmarkCase] = []
    for tier in INPUT_SIZE_TIERS:
        repeats = max(1, _TIER_SCALES[tier]["text_len"] // 26)
        text = (alphabet * repeats)[: _TIER_SCALES[tier]["text_len"]]
        cases.append(
            BenchmarkCase(
                name=f"is_pangram_{tier}",
                module=module,
                function="is_pangram",
                input_size_tier=tier,
                args_json=json.dumps([text]),
            )
        )
    return cases


_GENERATORS = {
    "get_primes": _cases_for_get_primes,
    "group_anagrams": _cases_for_group_anagrams,
    "roman_to_int": _cases_for_roman_to_int,
    "cipher": _cases_for_cipher,
    "is_pangram": _cases_for_is_pangram,
}


def detect_module_name(source_root: Path) -> str:
    main_py = source_root / "main.py"
    if main_py.is_file():
        return "main"
    try:
        from executor_mcp.api_signatures import detect_import_targets

        targets = detect_import_targets(source_root)
        if targets:
            return targets[0]
    except ValueError:
        pass
    return source_root.name.replace("-", "_")


def discover_public_functions(source_root: Path, module: str) -> list[str]:
    module_path = source_root / f"{module}.py"
    if not module_path.is_file():
        package_init = source_root / module / "__init__.py"
        if package_init.is_file():
            module_path = package_init
        else:
            return []
    names: list[str] = []
    for line in module_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("def ") and not stripped.startswith("def _"):
            names.append(stripped.split("(")[0].removeprefix("def ").strip())
    return names


def generate_cases(source_root: Path) -> list[BenchmarkCase]:
    """Build benchmark cases from detected public functions."""
    module = detect_module_name(source_root)
    functions = discover_public_functions(source_root, module)
    cases: list[BenchmarkCase] = []
    for fn in functions:
        generator = _GENERATORS.get(fn)
        if generator is not None:
            cases.extend(generator(module))
    if not cases and functions:
        fn = functions[0]
        cases.append(
            BenchmarkCase(
                name=f"{fn}_small",
                module=module,
                function=fn,
                input_size_tier="small",
                args_json="[]",
            )
        )
    return cases
