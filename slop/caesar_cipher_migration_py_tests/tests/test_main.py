from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

module_path = Path(__file__).resolve().parents[2] / "caesar_cipher" / "main.py"
spec = spec_from_file_location("caesar_cipher_source_main", module_path)
assert spec is not None
assert spec.loader is not None
main_module = module_from_spec(spec)
spec.loader.exec_module(main_module)
cipher = main_module.cipher


def test_cipher_shifts_lowercase_forward() -> None:
    assert cipher("abc", 1) == "bcd"


def test_cipher_wraps_lowercase_at_end_of_alphabet() -> None:
    assert cipher("xyz", 3) == "abc"


def test_cipher_wraps_uppercase_with_negative_shift() -> None:
    assert cipher("ABC", -1) == "ZAB"


def test_cipher_preserves_case_in_mixed_text() -> None:
    assert cipher("AbCz", 2) == "CdEb"


def test_cipher_preserves_non_letters() -> None:
    assert cipher("a1-b C!", 1) == "b1-c D!"


def test_cipher_returns_empty_string_for_empty_input() -> None:
    assert cipher("", 5) == ""


def test_cipher_large_positive_shift_matches_modulo_26() -> None:
    assert cipher("Hello, World!", 27) == cipher("Hello, World!", 1)


def test_cipher_large_negative_shift_matches_modulo_26() -> None:
    assert cipher("abcXYZ", -27) == cipher("abcXYZ", -1)


def test_cipher_rot13_example_matches_current_behavior() -> None:
    assert cipher("Hello, World!", 13) == "Uryyb, Jbeyq!"


def test_cipher_leaves_non_ascii_letters_unchanged() -> None:
    assert cipher("åäö Éè ß ñ", 5) == "åäö Éè ß ñ"
