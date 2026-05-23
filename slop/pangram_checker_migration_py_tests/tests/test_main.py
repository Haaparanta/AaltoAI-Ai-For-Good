from pathlib import Path
import importlib.util
import sys

SOURCE_MAIN = Path(__file__).resolve().parents[2] / "pangram_checker" / "main.py"
SPEC = importlib.util.spec_from_file_location(
    "pangram_checker_source_main", SOURCE_MAIN
)
assert SPEC is not None
assert SPEC.loader is not None
MAIN = importlib.util.module_from_spec(SPEC)
sys.modules.setdefault("pangram_checker_source_main", MAIN)
SPEC.loader.exec_module(MAIN)

is_pangram = MAIN.is_pangram


def test_is_pangram_returns_true_for_known_examples() -> None:
    assert is_pangram("The quick brown fox jumps over the lazy dog") is True
    assert is_pangram("Pack my box with five dozen liquor jugs.") is True
    assert is_pangram("abcdefghijklmnopqrstuvwxyz") is True


def test_is_pangram_returns_false_for_non_pangrams() -> None:
    assert is_pangram("Hello, World!") is False
    assert is_pangram("") is False


def test_is_pangram_is_case_insensitive_and_counts_repeated_letters_once() -> None:
    assert is_pangram("AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz") is True


def test_is_pangram_ignores_non_alphabetic_characters() -> None:
    assert is_pangram("abc123!!!") is False
    assert is_pangram("a!b@c#d$e%f^g&h*i(j)k_l+m=n[o]p{q}r|s:t;u,v.w/x?y-z") is True


def test_is_pangram_counts_unicode_alphabetic_characters_toward_length() -> None:
    assert is_pangram("abcdefghijklmnopqrstuvwxyé") is True
    assert is_pangram("abcdefghijklmnopqrstuvwxyzé") is False
