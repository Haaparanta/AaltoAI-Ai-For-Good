# Migration Plan

## Summary
This project is a minimal single-module Python utility that exposes one public function, `is_pangram(text: str) -> bool`. Its behavior is straightforward and deterministic: it lowercases alphabetic characters, collects distinct letters, and returns `True` only when exactly 26 unique alphabetic characters are present. The only executable entry-point behavior is a small `__main__` block containing inline assertions, so the migration effort is low-risk and mostly about preserving character-filtering semantics.

## Module inventory

| Path | Role | Public surface | Notes |
| --- | --- | --- | --- |
| `source/main.py` | Entire application module | `is_pangram(text: str) -> bool` | Implements pangram check using a set comprehension over `char.lower()` for characters where `char.isalpha()` is true. Also contains a `__main__` block with example assertions. |

## Dependencies
- No third-party dependencies found.
- Uses only Python built-ins and standard string methods:
  - `str.isalpha()` to decide which characters count as letters.
  - `str.lower()` to normalize case.
  - `set` comprehension to deduplicate letters.
- No packaging metadata (`pyproject.toml`, `setup.cfg`, `requirements.txt`) or additional modules were present in `source/`.

## Migration risks & mitigations
- **Unicode semantics of `isalpha()`**: The implementation counts any Unicode alphabetic character in the intermediate set, not just ASCII `a-z`. This means strings containing 26 distinct alphabetic code points that are not the English alphabet could incorrectly return `True`, and accented/non-Latin letters increase the set size without mapping to English letters.  
  **Mitigation:** Decide whether Rust should preserve the current Python behavior exactly or implement the documented intent (“every English letter”). Tests should lock in current behavior before changing it.
- **Lowercasing behavior is Python-specific**: `char.lower()` follows Python Unicode casing rules.  
  **Mitigation:** If exact compatibility matters, use Rust Unicode-aware lowercase handling and document any deviations.
- **No explicit error handling**: The type hint says `text: str`, but Python does not enforce it. Non-string inputs will fail when iterated or when calling string methods.  
  **Mitigation:** Tests should focus on string inputs only unless compatibility for wrong-type arguments is intentionally required.
- **Script assertions are not a full test suite**: Current verification exists only in the `__main__` block.  
  **Mitigation:** Convert those examples into pytest coverage and add edge cases around punctuation, repeated letters, and mixed case.

## Proposed test focus
The Tester should lock in the observable behavior of `is_pangram` with pytest:
- Returns `True` for known pangrams already embedded in `__main__`:
  - `"The quick brown fox jumps over the lazy dog"`
  - `"Pack my box with five dozen liquor jugs."`
  - `"abcdefghijklmnopqrstuvwxyz"`
- Returns `False` for non-pangrams such as `"Hello, World!"` and the empty string.
- Ignores case differences (`A` and `a` count as the same letter).
- Ignores non-alphabetic characters such as spaces and punctuation.
- Counts repeated letters once only.
- Add at least one test clarifying current Unicode behavior of `isalpha()`/`lower()` so migration choices are explicit.

## Proposed Rust layout
Recommended shape for this project:
- `rust/src/lib.rs`
  - Expose the core pangram-checking function.
- `rust/src/main.rs`
  - Optional small binary wrapper if a CLI/demo entry point is desired to mirror Python’s script usage.

Suggested module mapping:
- Python `main.py` -> Rust `src/lib.rs` function `is_pangram(...)`
- Python `if __name__ == "__main__"` examples -> Rust unit tests and/or a tiny `src/main.rs` demonstration binary

Because the project is a single function, a one-module Rust crate is sufficient; no deeper module hierarchy is needed unless future features are added.
