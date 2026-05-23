# Migration Plan

## Summary
This project is a minimal single-file Python implementation of a Caesar cipher. The entire functional surface is one public function, `cipher(text: str, shift: int) -> str`, plus a small `__main__` self-check block with assertions instead of a packaged CLI. Migration to Rust should be straightforward because the code is pure, deterministic, and uses only Python built-ins with no external dependencies or file/network I/O.

## Module inventory

| Path | Kind | Public surface | Role |
| --- | --- | --- | --- |
| `source/main.py` | top-level module / script | `cipher(text: str, shift: int) -> str` | Implements Caesar-shift transformation for ASCII letters, preserving case and leaving non-letters unchanged. Also contains inline assertions under `if __name__ == "__main__":`. |

### Observed behavior in `main.py`
- Iterates character-by-character through `text`.
- Lowercase ASCII letters (`"a" <= char <= "z"`) are shifted relative to `ord("a")`.
- Uppercase ASCII letters (`"A" <= char <= "Z"`) are shifted relative to `ord("A")`.
- Shift wrapping uses modulo 26: `(... + shift) % 26`.
- Any non-ASCII-letter character is appended unchanged.
- Returns the transformed string via `"".join(result)`.
- Script-mode behavior is only a set of assertions:
  - `cipher("abc", 1) == "bcd"`
  - `cipher("xyz", 3) == "abc"`
  - `cipher("Hello, World!", 13) == "Uryyb, Jbeyq!"`
  - `cipher("ABC", -1) == "ZAB"`
  - `cipher("", 5) == ""`

## Public surface

From the generated API stub:
- `main.cipher(text: str, shift: int) -> str`

There are no classes, constants, custom exceptions, or additional helper functions exposed. The module is not organized as a package.

## Dependencies
- **Third-party dependencies:** none found.
- **Standard library usage:** only Python built-ins (`ord`, `chr`, list accumulation, string join, assertions).
- **Packaging/config files:** none found at repository root (`pyproject.toml`, `setup.cfg`, `setup.py`, `requirements.txt` absent).

## Migration risks & mitigations
- **ASCII-only letter handling:** The code checks explicit ranges `a-z` and `A-Z`, so letters outside basic ASCII are not shifted. Rust implementation should preserve this exact behavior rather than using broader Unicode alphabetic checks.
  - **Mitigation:** operate on chars with explicit ASCII range checks or byte-wise logic for ASCII letters only.
- **Negative and large shifts:** Behavior relies on modulo 26 and Python’s modulo semantics with negative values. Rust should normalize shifts to preserve identical wraparound behavior.
  - **Mitigation:** normalize with Euclidean remainder (`rem_euclid(26)`) before applying shifts.
- **Non-letter preservation:** Punctuation, whitespace, digits, and non-ASCII characters currently pass through unchanged.
  - **Mitigation:** add tests covering representative unchanged characters, including non-ASCII text.
- **Single-file script layout:** There is no package structure or formal CLI contract; only importable function behavior is meaningful.
  - **Mitigation:** treat `cipher` as the stable API and regard `__main__` assertions as examples/self-checks, not a user-facing command interface.
- **Type assumptions not enforced at runtime:** Signature annotations say `str` and `int`, but Python does not enforce them. Rust/PyO3 boundary will need explicit type conversion behavior if exposed back to Python.
  - **Mitigation:** keep Python tests focused on valid typed usage unless interop requirements later demand type-error parity.

## Proposed test focus
Tester should lock in these behaviors with pytest:
- Basic forward shifting for lowercase text.
- Wraparound at alphabet end for lowercase and uppercase.
- Negative shifts for uppercase and lowercase.
- Mixed-case strings preserve original case while shifting letters.
- Punctuation, spaces, digits, and symbols remain unchanged.
- Empty string returns empty string.
- Large shifts equivalent modulo 26 (for example, `shift=27` equals `shift=1`, and negative large shifts behave as expected).
- Non-ASCII alphabetic characters are unchanged because only ASCII ranges are handled.
- Deterministic full-string examples matching current inline assertions, especially `"Hello, World!"` with shift `13`.

## Proposed Rust layout
A minimal Rust shape is sufficient:

```text
rust/
  Cargo.toml
  src/
    lib.rs
```

Suggested module mapping:
- `source/main.py` -> `rust/src/lib.rs`
  - expose a pure function analogous to `cipher(text: &str, shift: i32) -> String`

If Python bindings are required later, the same core function can remain in `lib.rs` and be wrapped by PyO3 without changing the algorithm.

## Notes / assumptions
- Assumed migration target is the single importable behavior in `main.py`; no separate CLI contract exists beyond script assertions.
- Verified source compiles with `python -m py_compile main.py`.
