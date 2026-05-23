from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[2].parent / "slop" / "prime_generator" / "main.py"
)
SPEC = spec_from_file_location("prime_generator_main", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

get_primes = MODULE.get_primes


def test_get_primes_returns_empty_for_values_below_two() -> None:
    assert get_primes(-5) == []
    assert get_primes(0) == []
    assert get_primes(1) == []


def test_get_primes_returns_only_two_for_upper_bound_two() -> None:
    assert get_primes(2) == [2]


def test_get_primes_returns_expected_primes_up_to_ten() -> None:
    assert get_primes(10) == [2, 3, 5, 7]


def test_get_primes_includes_prime_upper_bound() -> None:
    assert get_primes(19) == [2, 3, 5, 7, 11, 13, 17, 19]


def test_get_primes_excludes_composite_upper_bound() -> None:
    assert get_primes(20) == [2, 3, 5, 7, 11, 13, 17, 19]


def test_get_primes_returns_sorted_unique_primes_for_larger_input() -> None:
    result = get_primes(30)

    assert result == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    assert result == sorted(result)
    assert len(result) == len(set(result))
    assert all(prime not in result for prime in [4, 6, 8, 9, 10, 12, 14, 15])
