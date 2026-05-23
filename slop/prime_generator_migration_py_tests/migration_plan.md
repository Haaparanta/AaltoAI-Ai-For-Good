# Migration Plan

## Summary
This project is a very small single-module Python program centered on one public function, `get_primes(n)`, implemented in `main.py`. It computes prime numbers up to and including a bound using the Sieve of Eratosthenes and includes a few inline assertions under the `__main__` guard instead of a formal test suite or packaging metadata. The migration surface is narrow, with minimal dependencies and side effects, so the main goal is preserving exact output behavior for edge cases and typical bounds.

## Module inventory

| Path | Role | Public surface | Notes |
| --- | --- | --- | --- |
| `source/main.py` | Entire application module | `get_primes(n: int) -> list[int]` | Contains the prime-generation logic and inline smoke assertions under `if __name__ == "__main__":`. |

### Entry points
- `source/main.py` has a script entry point via `if __name__ == "__main__":`.
- Running the file executes only assertions; there is no CLI parsing, printing, or file I/O.

### Packaging/configuration
- No `pyproject.toml`, `setup.cfg`, or `requirements.txt` were present at repository root under `source/`.
- Public API stub generation found a single module: `main`.

## Dependencies
- **Third-party dependencies:** none found.
- **Standard library:** only Python built-ins are used.
- The implementation is self-contained and does not rely on external packages, OS services, or data files.

## Behavior

### `get_primes(n: int) -> list[int]`
Observed implementation in `source/main.py`:
- Returns `[]` for `n < 2`.
- Allocates a boolean list `is_prime = [True] * (n + 1)`.
- Marks indices `0` and `1` as non-prime.
- Iterates `i` from `2` through `int(n**0.5) + 1`.
- When `is_prime[i]` is true, marks multiples from `i * i` through `n` with step `i` as composite.
- Returns all indices `i` in `2..n` where `is_prime[i]` remains true.

### Side effects and control flow
- `get_primes` is pure for integer inputs: no I/O, no global state mutation, no randomness.
- The only top-level executable behavior is the `__main__` assertion block.
- Error handling is implicit only; the function does not validate types beyond Python’s runtime behavior.

## Migration risks & mitigations

### Low-risk areas
- Algorithm is deterministic and straightforward to port to Rust.
- No dynamic imports, reflection, metaprogramming, concurrency, or platform-specific branches.
- No classes, inheritance, decorators, or mutable shared state.

### Behavior risks to preserve
1. **Inclusive upper bound**
   - The function returns primes up to **and including** `n`.
   - Mitigation: add tests covering prime and non-prime bounds such as `2`, `10`, and `19`/`20`.

2. **Boundary handling for small inputs**
   - The implementation explicitly returns `[]` for values below `2`.
   - Mitigation: test `n = 0`, `1`, and a negative value.

3. **Python numeric-type semantics**
   - The signature says `int`, but Python does not enforce it at runtime.
   - Non-integer inputs may fail at list allocation or `range(...)` usage rather than via explicit validation.
   - Mitigation: for Python-side tests in this phase, focus on integer behavior unless human review requests compatibility for invalid types. If invalid-type behavior matters, capture the exact exception types before translation.

4. **Memory behavior for large `n`**
   - The sieve allocates `n + 1` booleans, so large bounds scale linearly in memory.
   - Mitigation: preserve algorithmic shape in Rust unless a reviewed optimization is intentionally introduced.

## Proposed test focus
Tester should lock in these behaviors with pytest:
- Correct outputs for the inline smoke cases already embedded in `__main__`:
  - `get_primes(1) == []`
  - `get_primes(2) == [2]`
  - `get_primes(10) == [2, 3, 5, 7]`
  - `get_primes(20) == [2, 3, 5, 7, 11, 13, 17, 19]`
  - `get_primes(0) == []`
- Additional small boundary case: negative input returns `[]` because of the `n < 2` guard.
- Inclusive-bound behavior: if `n` itself is prime, it appears in the result.
- Composite exclusion: values such as `4`, `6`, `8`, `9`, `10` do not appear.
- Output ordering: primes are returned in ascending order with no duplicates.
- A somewhat larger sanity case (for example `30` or `50`) to ensure sieve marking remains correct beyond trivial inputs.

## Proposed Rust layout
Given the tiny scope, a minimal crate is appropriate:

- `rust/Cargo.toml`
- `rust/src/lib.rs`
  - expose a public function analogous to `get_primes(n: usize) -> Vec<usize>` or a reviewed signed-integer wrapper if negative-input compatibility is required
- `rust/src/main.rs` (optional)
  - only needed if the migrated project should retain a runnable binary target; otherwise library-only is sufficient

### Suggested module mapping
- Python `main.py` -> Rust `src/lib.rs` for the reusable prime-generation logic.
- Optional Rust binary `src/main.rs` can contain smoke checks or a simple entry point if maintaining a script-style executable is desired, though the original project has no real CLI behavior.

## Assumptions
- Analysis is based on the files present under `source/`, which contained only `main.py`.
- No hidden package metadata or external test suite was present in the provided project root.
