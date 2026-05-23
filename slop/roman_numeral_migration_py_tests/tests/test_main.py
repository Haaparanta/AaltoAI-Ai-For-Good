from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_PATH = PROJECT_ROOT / "roman_numeral" / "main.py"
SPEC = spec_from_file_location("roman_numeral_source_main", MAIN_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
roman_to_int = MODULE.roman_to_int


@pytest.mark.parametrize(
    ("roman", "expected"),
    [
        ("III", 3),
        ("IV", 4),
        ("IX", 9),
        ("MCMXCIV", 1994),
        ("LVIII", 58),
    ],
)
def test_roman_to_int_examples_from_source(roman: str, expected: int) -> None:
    assert roman_to_int(roman) == expected


@pytest.mark.parametrize(
    ("roman", "expected"),
    [
        ("I", 1),
        ("V", 5),
        ("X", 10),
        ("M", 1000),
        ("II", 2),
        ("XX", 20),
        ("MM", 2000),
        ("VIII", 8),
    ],
)
def test_roman_to_int_additive_numerals(roman: str, expected: int) -> None:
    assert roman_to_int(roman) == expected


@pytest.mark.parametrize(
    ("roman", "expected"),
    [
        ("IV", 4),
        ("IX", 9),
        ("XL", 40),
        ("XC", 90),
        ("CD", 400),
        ("CM", 900),
        ("XIV", 14),
        ("MCM", 1900),
        ("MCMXC", 1990),
    ],
)
def test_roman_to_int_subtractive_patterns(roman: str, expected: int) -> None:
    assert roman_to_int(roman) == expected


@pytest.mark.parametrize(
    ("roman", "expected"),
    [
        ("", 0),
        ("IIII", 4),
        ("IIV", 3),
        ("VX", 5),
        ("IC", 99),
        ("XM", 990),
    ],
)
def test_roman_to_int_accepts_noncanonical_strings_per_algorithm(
    roman: str, expected: int
) -> None:
    assert roman_to_int(roman) == expected


@pytest.mark.parametrize("roman", ["A", "iv", "XI!", " "])
def test_roman_to_int_invalid_characters_raise_keyerror(roman: str) -> None:
    with pytest.raises(KeyError):
        roman_to_int(roman)
