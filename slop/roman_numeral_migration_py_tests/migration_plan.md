# Migration Plan

## Summary
This project is a minimal single-file Python program that exposes one conversion function, `roman_to_int`, in `main.py`. It has no package structure, no declared third-party dependencies, and no configuration files such as `pyproject.toml` or `setup.py` in the repository root. The core behavior is a right-to-left Roman numeral parser using subtractive notation based solely on adjacent value comparisons; preserving its exact acceptance and failure behavior is the main testing need before Rust translation.

## Module inventory

| Path | Kind | Public surface | Role |
|---|---|---|---|
| `source/main.py` | standalone module / script | `roman_to_int(roman: str) -> int` | Implements Roman numeral to integer conversion and includes simple script-time assertions under `if __name__ == "__main__":` |

### Notes on module behavior
- `roman_to_int` defines a local mapping: `{"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}`.
- It iterates `for char in reversed(roman)` and uses a `prev` accumulator to decide whether to add or subtract each symbol.
- The file is also executable as a script; the `__main__` block performs five inline `assert` checks for known examples.

## Dependencies
- **Third-party libraries:** none found.
- **Standard library:** only Python built-ins are used (`reversed`, `assert`, dict lookup).
- **Packaging/build config:** none found in repository root (`pyproject.toml`, `setup.cfg`, `setup.py`, `requirements.txt` absent).

## Migration risks & mitigations
- **Underspecified input validation:** the function does not validate Roman numeral well-formedness. It will compute values for many non-canonical strings (for example, behavior follows the add/subtract algorithm rather than Roman numeral grammar).  
  **Mitigation:** tests should lock in current behavior for canonical examples and explicitly capture treatment of edge cases the Python implementation currently accepts.
- **KeyError on unsupported characters:** `value = values[char]` means any character not in the mapping raises `KeyError`, including lowercase letters, spaces, punctuation, or other invalid symbols.  
  **Mitigation:** include tests for invalid characters so the Rust version preserves exception/error semantics or intentionally documents a change.
- **Empty-string behavior is implicit:** because the loop is skipped, `roman_to_int("")` returns `0`. This is not documented, but it is the current behavior.  
  **Mitigation:** add a test if preserving exact compatibility matters.
- **No package API boundary:** the public surface is the top-level `main` module rather than a library package.  
  **Mitigation:** in Rust, separate library logic from binary entry point even if Python combines them.
- **Script assertions are not a test suite:** the `__main__` block provides examples but does not cover error behavior or edge cases.  
  **Mitigation:** convert these examples into pytest coverage and extend with negative and boundary cases.

## Proposed test focus
Tester should create pytest coverage around the exact observable behavior of `roman_to_int`:

1. **Known examples from source**
   - `III -> 3`
   - `IV -> 4`
   - `IX -> 9`
   - `MCMXCIV -> 1994`
   - `LVIII -> 58`

2. **Basic additive numerals**
   - Single symbols such as `I`, `V`, `X`, `M`
   - Repeated additive forms such as `II`, `XX`, `MM`

3. **Subtractive behavior as implemented**
   - Pairs like `IV`, `IX`, `XL`, `XC`, `CD`, `CM`
   - Mixed strings where the right-to-left `prev` logic matters

4. **Edge cases of current implementation**
   - Empty string returns `0`
   - Invalid character input raises `KeyError`
   - Lowercase input raises `KeyError`

5. **Potentially non-canonical but accepted strings**
   - Inputs that are not proper Roman numerals but still produce a numeric result under the current algorithm, to decide whether compatibility should be preserved during migration

## Proposed Rust layout
Because the Python project is a single script, the Rust port should likely split reusable logic from executable wiring:

```text
rust/
  Cargo.toml
  src/
    lib.rs          # public roman_to_int API
    roman.rs        # conversion implementation and symbol mapping
    main.rs         # optional CLI/demo equivalent to Python script entry point
```

### Suggested module mapping
- `source/main.py::roman_to_int` -> `rust/src/roman.rs` with re-export from `rust/src/lib.rs`
- Python `if __name__ == "__main__":` example usage -> `rust/src/main.rs` as a small executable or omitted if only a library is needed

### Translation guidance
- Preserve the current algorithm directly: iterate input from right to left, compare current value to previous maximum/right neighbor value, subtract when smaller, otherwise add and update `prev`.
- Decide early whether Rust should mirror Python's `KeyError`-style failure via `Result`/panic for invalid characters, or whether the binding layer should translate a structured Rust error into a Python exception compatible with current tests.
