# Migration Plan

## Summary
This project is a minimal single-module Python program that exposes one public function, `bubble_sort`, in `main.py`. The function performs an ascending bubble sort over a list of integers, copying the input before sorting and using an early-exit optimization when a pass makes no swaps. There are no package boundaries, external dependencies, or configuration files; the only executable entry point is a small `__main__` self-check block with assertions.

## Module inventory

| Path | Role | Public surface | Notes |
|---|---|---|---|
| `source/main.py` | Entire application module and script entry point | `bubble_sort(numbers: list[int]) -> list[int]` | Implements bubble sort on a shallow copy of the input list. `__main__` block runs inline assertions only. |

## Dependencies
- **Third-party dependencies:** none found.
- **Standard library usage:** none beyond Python built-ins and typing syntax.
- **Project config / packaging files:** none found (`pyproject.toml`, `setup.cfg`, `setup.py`, `requirements.txt`, `Pipfile` absent in inspected tree).

## Behavior
- `bubble_sort` creates `result = numbers[:]`, so it **does not mutate the caller's list**.
- Sorting order is ascending, based on the `>` comparison of adjacent elements.
- The implementation is classic bubble sort:
  - outer loop over `range(n)`
  - inner loop over `range(n - i - 1)`
  - adjacent swap when `result[j] > result[j + 1]`
- It includes an **early-exit optimization**: if a full pass performs no swaps, the algorithm breaks immediately.
- Return value is always the copied-and-sorted list.
- The `if __name__ == "__main__":` block contains five assertion-based smoke checks:
  - mixed unsorted input
  - empty list
  - singleton list
  - reverse-sorted list
  - already-sorted list

## Migration risks & mitigations
- **Low overall migration risk:** logic is small, deterministic, and side-effect free.
- **Input immutability expectation:** callers may rely on the input list remaining unchanged because of the slice copy.  
  **Mitigation:** preserve copy-before-sort semantics in Rust/PyO3 API; test that the original Python list is unchanged.
- **Type restriction in public signature:** stubbed API specifies `list[int]`. Python runtime does not enforce this, but migration should align with the declared contract rather than broaden behavior accidentally.  
  **Mitigation:** write tests around integer lists only unless human review requests compatibility with other comparable element types.
- **Script behavior vs library behavior:** module doubles as importable library and executable script.  
  **Mitigation:** if Rust package exposes both, keep a library function and optionally a tiny binary/self-check only if needed; the main preserved behavior is the callable function.
- **Algorithm identity:** a Rust rewrite might be tempted to call standard sort. That would preserve output but not necessarily implementation-specific expectations like copy-first and bubble-sort pass structure.  
  **Mitigation:** for migration correctness, tests should lock in observable behavior only (sorted output, unchanged input), not internal step counts.

## Proposed test focus
Tester should lock in these externally observable behaviors with pytest:
- Returns ascending order for typical unsorted integer lists.
- Handles duplicates correctly (e.g. two `1`s remain present).
- Returns `[]` for empty input.
- Returns the same singleton value for one-element input.
- Correctly sorts reverse-ordered input.
- Leaves already sorted input unchanged in value.
- Does **not mutate** the original input list.
- Returns a new list object rather than the same object when given a list input.

Lower priority / optional:
- Confirm function can be imported from `main` and called directly.
- If script execution is in scope, verify `python main.py` exits successfully because all inline asserts pass.

## Proposed Rust layout
Given the project size, keep the Rust translation minimal:

- `rust/Cargo.toml`
- `rust/src/lib.rs`
  - expose the Python-facing function equivalent to `bubble_sort`
- Optional internal module split only if desired:
  - `rust/src/sort.rs` for algorithm implementation
  - `rust/src/lib.rs` for PyO3 bindings / public export
- Optional binary only if preserving script form is required:
  - `rust/src/main.rs` with lightweight smoke checks or demo invocation

Suggested module mapping:
- `source/main.py` → `rust/src/lib.rs` (or `rust/src/sort.rs` + `lib.rs` re-export)

## Assumptions
- The migration target is the public callable surface, not the exact inline assertion script structure.
- No hidden package files exist beyond the inspected repository tree.
