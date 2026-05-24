# Migration Plan

## Summary
This project is a very small single-module Python program that exposes one public function, `group_anagrams`, in `main.py`. The implementation is pure Python, deterministic, and uses only standard library features with no external dependencies, file I/O, or concurrency. Migration to Rust should be straightforward; the main behavior to preserve is grouping words by their sorted-character signature while preserving input order within each group and first-seen group order.

## Module inventory

| Path | Role | Public surface | Notes |
|---|---|---|---|
| `source/main.py` | Sole module and script entry point | `group_anagrams(words: list[str]) -> list[list[str]]` | Implements grouping via `tuple(sorted(word))` keys in a `dict`; also contains inline assertions under `if __name__ == "__main__":` that act as smoke tests. |

### Observed behavior in `main.py`
- Builds a dictionary `groups: dict[tuple[str, ...], list[str]] = {}`.
- For each input word, computes `key = tuple(sorted(word))`.
- Uses `groups.setdefault(key, []).append(word)` to collect original words.
- Returns `list(groups.values())`.
- Because Python dicts preserve insertion order, output group order follows the first occurrence of each anagram class in the input.
- Words remain in original encounter order inside each group.

## Dependencies
- **Runtime dependencies:** none beyond Python standard library / built-ins.
- **Project/config files:** none observed (`pyproject.toml`, `setup.cfg`, `requirements.txt`, package layout, and test directory are absent from the inspected tree).
- **Typing:** inline type hints only; no runtime type enforcement.

## Migration risks & mitigations
- **Order-sensitive behavior hidden behind dict semantics:**
  - Risk: a Rust implementation could group correctly but return groups in a different order.
  - Mitigation: preserve first-seen group order explicitly, either with an ordered map/index structure or a `HashMap` plus a separate ordered key list.
- **Unicode/character-sorting semantics:**
  - Risk: Python sorts strings by Unicode code points after iterating characters; a Rust translation must define whether it operates on Unicode scalar values, bytes, or grapheme clusters.
  - Mitigation: match Python behavior by sorting `char` values, not bytes grouped by UTF-8 encoding. Add tests for non-ASCII inputs if Unicode compatibility is desired.
- **No runtime input validation:**
  - Risk: Python type hints suggest `list[str]`, but the function does not validate types. Rust will likely need stricter types at the boundary.
  - Mitigation: for parity, keep the Rust/PyO3 boundary typed as a sequence of strings and treat non-string inputs as type errors at the boundary rather than adding new semantic validation inside the core algorithm.
- **Script-only smoke tests:**
  - Risk: behavior currently demonstrated only by `assert` statements in `__main__`; these are easy to overlook in migration.
  - Mitigation: convert those cases into explicit pytest coverage before translation.
- **Performance shape for long words:**
  - Risk: key generation is `O(k log k)` per word due to sorting characters.
  - Mitigation: preserve algorithm first for correctness; optimize later only if benchmarks justify it.

## Proposed test focus
Tester should lock down these behaviors with pytest:
- Basic grouping of a mixed list such as `['eat', 'tea', 'tan', 'ate', 'nat', 'bat']`.
- Empty input returns `[]`.
- Single-item input returns a single singleton group.
- Duplicate words are preserved, e.g. `['ab', 'ba', 'ab']` results in one group containing both `ab` occurrences.
- All-anagram input produces exactly one group.
- Output ordering semantics:
  - group order follows first appearance of each anagram family;
  - word order inside each group follows original input order.
- Non-anagram distinct words remain in separate groups.
- Optional but useful: Unicode characters to confirm sorted-character behavior on non-ASCII strings.

## Proposed Rust layout
Given the tiny scope, keep the Rust structure minimal:

- `rust/Cargo.toml`
- `rust/src/lib.rs`
  - expose the core grouping function
  - if PyO3 is used later, this can also host Python bindings or re-export from a core module
- Optional split if desired for clarity:
  - `rust/src/anagram.rs` — core implementation of `group_anagrams`
  - `rust/src/lib.rs` — module wiring and public exports
- Optional binary only if script parity is wanted:
  - `rust/src/main.rs` — reproduce the demo/assert-style smoke behavior or a simple CLI wrapper

### Suggested module mapping
- Python `main.py` -> Rust `src/lib.rs` or `src/anagram.rs`
- Python `if __name__ == "__main__":` demo block -> optional Rust `src/main.rs` or omitted in favor of tests

## Assumptions
- The inspected project consists only of `source/main.py`; no additional package files or hidden modules were found in the repository tree under `source/`.
- Public API is the single stubbed function `main.group_anagrams`.
