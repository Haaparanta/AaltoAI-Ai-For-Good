# Migration Plan

## Summary
`qrcode` is a pure-Python QR code generator library with a small CLI (`qr`) and a public API centered on `qrcode.QRCode` and `qrcode.make()`. Core behavior is deterministic QR matrix generation plus rendering through pluggable image factories: terminal ASCII/TTY output, PNG via Pillow or pypng, and SVG via ElementTree. The migration should preserve QR encoding semantics, validation/error behavior, automatic version fitting, image-factory selection rules, and CLI behavior, while treating optional rendering backends as feature-gated adapters.

## Module inventory

| Path | Role | Public / internal notes |
|---|---|---|
| `qrcode/__init__.py` | Top-level package API re-export | Public: `QRCode`, `make`, error-correction constants, `image`, `run_example` |
| `qrcode/__main__.py` | Module entry point | Calls `qrcode.console_scripts.main()` unconditionally |
| `qrcode/main.py` | Core QRCode implementation | Public core surface; matrix generation, fitting, mask choice, terminal printing, image creation |
| `qrcode/util.py` | Encoding utilities | Public-ish helper surface used by tests and callers: modes, `QRData`, `BitBuffer`, `create_data`, version checks, chunk optimization |
| `qrcode/base.py` | Reed-Solomon / polynomial math and RS block tables | Internal algorithm support but behavior-critical |
| `qrcode/constants.py` | Error correction constants and Pillow availability probe | Public constants |
| `qrcode/exceptions.py` | Custom exception types | Public: `DataOverflowError` |
| `qrcode/console_scripts.py` | `qr` CLI | Public script entry point; chooses stdout ASCII vs image output |
| `qrcode/image/base.py` | Abstract image interfaces | Public extension surface for image factories / drawers |
| `qrcode/image/pil.py` | Pillow image factory | Public optional backend; default if Pillow import succeeds |
| `qrcode/image/pure.py` | pypng image factory | Public optional backend and fallback when Pillow unavailable |
| `qrcode/image/styledpil.py` | Styled Pillow rendering with drawers, color masks, embedded image | Public optional backend; depends on style subpackages |
| `qrcode/image/svg.py` | SVG image factories | Public optional backend; fragment/full/path variants |
| `qrcode/compat/png.py` | Optional import shim for pypng | Internal compatibility layer |
| `qrcode/compat/etree.py` | Optional import shim for lxml vs stdlib ElementTree | Internal compatibility layer |
| `qrcode/LUT.py` | Precomputed Reed-Solomon polynomial lookup tables | Internal data table |
| `qrcode/release.py` | Release-time manpage updater | Packaging/release utility, not runtime API |
| `qrcode/tests/*.py` | Upstream behavioral tests | Good source of expected behavior to preserve |

### Core public API details
- `qrcode.make(data=None, **kwargs)` creates a `QRCode`, adds data, and returns `make_image()`.
- `qrcode.QRCode(...)` constructor parameters: `version`, `error_correction`, `box_size`, `border`, `image_factory`, `mask_pattern`.
- `QRCode` public methods used externally or tested: `add_data`, `make`, `make_image`, `print_ascii`, `print_tty`, `get_matrix`, `clear`, `best_fit`, `best_mask_pattern`, `active_with_neighbors`.
- `qrcode.util` exposes mode constants, `QRData`, `BitBuffer`, `optimal_data_chunks`, `create_data`, `check_version`, etc.; tests rely on this surface.
- CLI public helpers: `main`, `get_factory`, `get_drawer_help`, `commas`.
- Rendering extension points: `BaseImage`, `BaseImageWithDrawer`, and concrete image classes.

## Layout / entry points
- Packaging is declared only in `pyproject.toml`; no `setup.py`, `setup.cfg`, or `requirements.txt`.
- Installable script entry point: `qr = qrcode.console_scripts:main`.
- `python -m qrcode` dispatches to the same CLI via `__main__.py`.
- Runtime package is `qrcode`; tests are vendored under `qrcode/tests/` in source.

## Dependencies

### Required runtime
- `deprecation`: used in `qrcode/image/styledpil.py` for the deprecated `draw_embeded_image()` method.
- `colorama` on Windows only: initialized in CLI for proper terminal output.

### Optional runtime
- `pillow >= 9.1.0`: used by `qrcode/image/pil.py` and `qrcode/image/styledpil.py`; default image backend if importable.
- `pypng`: used by `qrcode/image/pure.py`; fallback backend when Pillow is unavailable, and explicit backend for CLI `--factory=png`.
- `lxml` optional: `qrcode/compat/etree.py` prefers `lxml.etree`, otherwise falls back to stdlib `xml.etree.ElementTree`.

### Dependency usage notes
- Core QR generation is stdlib-only aside from optional rendering/release helpers.
- Rendering backends are loosely coupled through `BaseImage`; this maps well to Rust traits or enums plus feature flags.

## Behavior to preserve

### Data handling and encoding
- Non-bytes input is converted with `str(data).encode("utf-8")` in `util.to_bytestring`.
- `QRCode.add_data` accepts either a `util.QRData` instance or raw data.
- With `optimize > 0`, input is split into chunks using regex-based numeric/alphanumeric detection (`util.optimal_data_chunks`); with `optimize=0`, a single `QRData` is created.
- Supported modes in practice are numeric, alphanumeric, and 8-bit byte. KANJI constant exists but `QRData` explicitly “doesn't currently handle KANJI.”

### Version fitting and overflow
- `QRCode.version` may be explicit or lazily computed by `best_fit()`.
- `best_fit()` builds a bit buffer, uses `bisect_left` against `util.BIT_LIMIT_TABLE[self.error_correction][:]`, and intentionally passes a copy of that list for thread safety on Python 3.13+.
- If the chosen version would be 41, `exceptions.DataOverflowError` is raised.
- `util.create_data()` also raises `DataOverflowError` with a detailed message if encoded bits exceed capacity.

### Matrix generation
- `make()` picks best version if needed and either user-specified mask or `best_mask_pattern()`.
- `best_mask_pattern()` evaluates all 8 masks by fully building the symbol and scoring via `util.lost_point()`.
- Blank module templates are cached globally in `precomputed_qr_blanks` keyed only by version, then copied before filling with type/data bits.
- `get_matrix()` includes border rows/columns unless `border == 0`.

### Rendering and output
- `make_image()`:
  - warns on deprecated typo kwargs `embeded_*`;
  - requires `ERROR_CORRECT_H` if any embedded-image arg is present;
  - validates positive `box_size` at render time too;
  - chooses image factory in this order: explicit arg, `self.image_factory`, otherwise Pillow backend if importable else PyPNG.
- `BaseImage` subclasses expose `save()` and `get_image()`; Pillow/styled backends also forward unknown attributes to the underlying PIL image via `__getattr__`.
- `print_ascii()` writes CP437 block characters, can emit ANSI color escapes when `tty=True`, and raises `OSError("Not a tty")` if TTY mode is requested on a non-TTY stream.
- `print_tty()` always requires a TTY-capable stream and writes ANSI escape sequences directly.

### CLI behavior
- Input source: first positional arg encoded with `errors="surrogateescape"`, otherwise `sys.stdin.buffer.read()`.
- If `--output` is given, generated image is written to that path in binary mode.
- Without `--output`, when no image factory is selected and stdout is a TTY (or `--ascii` is used), CLI prints ASCII instead of image bytes.
- Drawer aliases are validated against the selected factory's `drawer_aliases`; invalid options terminate through `optparse.OptionParser.error()` (observed as `SystemExit`).
- Factory names can be shortcuts (`pil`, `png`, `svg`, `svg-fragment`, `svg-path`) or full import paths.

## Migration risks & mitigations

### 1. Algorithmic correctness risk
**Risk:** Reed-Solomon math, mask scoring, version fitting, and data placement are compact but correctness-sensitive. Small deviations will produce visually plausible but non-standard QR codes.

**Mitigation:** Lock in matrix-level behavior with tests around `get_matrix()`, chosen version, chosen mask, overflow exceptions, and known regressions from upstream tests.

### 2. Dynamic typing / permissive inputs
**Risk:** Python accepts many loosely typed inputs (`str`, `bytes`, arbitrary objects via `str()`, custom `QRData`, optional image factories, streams with duck-typed `isatty`). Rust will need stricter APIs.

**Mitigation:** Define explicit Rust/PyO3 conversion rules for accepted Python-visible inputs and preserve Python exception types/messages where feasible.

### 3. Optional backend selection
**Risk:** Default backend depends on import availability at runtime (`PIL` preferred, else pypng). Rust implementation may not mirror Python import probing naturally.

**Mitigation:** Preserve Python-facing selection semantics in the PyO3 layer, possibly exposing feature detection and selecting equivalent backend wrappers there.

### 4. Global mutable cache / concurrency
**Risk:** `precomputed_qr_blanks` is global mutable state; `best_fit()` includes a specific copy workaround for thread safety with `bisect_left` and `BIT_LIMIT_TABLE`.

**Mitigation:** In Rust, use immutable precomputed templates or synchronized lazy caches. Add concurrency tests around repeated fitting/rendering if shared global state remains.

### 5. Deprecated typo parameters and backward compatibility
**Risk:** `embeded_image*` typo kwargs still work and emit `DeprecationWarning`; callers may depend on them.

**Mitigation:** Preserve deprecated argument aliases in the Python API shim even if Rust internals normalize names immediately.

### 6. SVG / rendering ecosystem differences
**Risk:** Current code can use either `lxml` or stdlib `ElementTree`; output formatting details may vary. Styled rendering also depends on separate style modules not inspected here but referenced by public API.

**Mitigation:** Test structural properties rather than byte-for-byte XML where possible. Treat style drawers/color masks as adapter-driven behavior and port only the actually exported combinations used by tests first.

### 7. CLI platform behavior
**Risk:** Windows-specific `colorama.init()` and TTY detection differences may be hard to mirror exactly in Rust.

**Mitigation:** Preserve externally visible behavior in Python tests by mocking `os.isatty`, `sys.stdout`, and CLI option parsing rather than depending on platform terminals.

## Proposed test focus
Tester should prioritize high-value behavioral locks rather than exhaustive internal implementation tests.

1. **Top-level API and construction**
   - `qrcode.make()` returns a renderable image.
   - `QRCode` validates `version`, `border`, `box_size`, `mask_pattern`, `image_factory`.

2. **Encoding and fitting behavior**
   - `add_data(..., optimize=0)` mode selection for numeric, alphanumeric, byte, newline/comma edge cases.
   - `optimize` chunk splitting behavior and version reduction.
   - `best_fit()` version selection and overflow raising.
   - Regression cases for zero-heavy / binary-null-heavy inputs.
   - `best_mask_pattern()` known expected result for `"hello"` with `ERROR_CORRECT_H`.

3. **Matrix semantics**
   - `get_matrix()` with and without border.
   - Matrix generation stability for representative inputs.
   - `active_with_neighbors()` / eye-context-sensitive behavior if styled drawers are ported.

4. **Terminal output**
   - `print_ascii()` text prefix, invert/tty behavior, and `OSError` on non-TTY.
   - `print_tty()` ANSI output prefix and non-TTY failure.

5. **Image factory selection and rendering**
   - Explicit factory selection for PIL, PyPNG, SVG variants where deps are available.
   - Default backend preference: PIL if installed, else PyPNG.
   - `embedded_image*` requires `ERROR_CORRECT_H`.
   - Deprecated `embeded_*` args emit warning but still work.

6. **CLI behavior**
   - `python -m qrcode` delegates to console main.
   - `qr` uses positional arg vs stdin correctly.
   - ASCII-vs-image branch selection based on tty / `--ascii` / `--output`.
   - `--factory`, invalid factory, `--factory-drawer`, and helper `commas()` behavior.

7. **Thread-safety regression**
   - Preserve test asserting `best_fit()` passes a copy, not the original `BIT_LIMIT_TABLE` row, into `bisect_left`.

## Proposed Rust layout

Suggested crate structure should separate algorithm core from Python-facing adapters and optional renderers.

```text
rust/
  Cargo.toml
  src/
    lib.rs                # PyO3 module exports matching qrcode package surface
    errors.rs             # DataOverflowError mapping / Python exception glue
    constants.rs          # error-correction constants, capability flags
    qr/
      mod.rs              # QRCode type and top-level make()
      matrix.rs           # module matrix construction, patterns, mapping
      encode.rs           # QRData, bit buffer, chunk optimization, create_data
      rs.rs               # Reed-Solomon math, polynomial ops, rs_blocks
      mask.rs             # mask functions and lost-point scoring
      cache.rs            # blank template cache / immutable precomputed data
    image/
      mod.rs              # Base image abstractions exposed to Python
      pil.rs              # Pillow-backed adapter or compatibility shim
      png.rs              # PNG writer backend / pypng-compatible behavior
      svg.rs              # SVG fragment/full/path generation
      styled.rs           # styled image orchestration, embedded-image rules
    cli.rs                # optional if CLI is reimplemented in Rust
```

### Python-to-Rust module mapping guidance
- `qrcode.main` -> `src/qr/mod.rs`, `matrix.rs`, `mask.rs`, `cache.rs`
- `qrcode.util` -> `src/qr/encode.rs` plus some items in `mask.rs`
- `qrcode.base` + `qrcode/LUT.py` -> `src/qr/rs.rs`
- `qrcode.constants`, `qrcode.exceptions` -> `src/constants.rs`, `src/errors.rs`
- `qrcode.image.base` -> `src/image/mod.rs`
- `qrcode.image.pil` / `pure` / `svg` / `styledpil` -> corresponding files under `src/image/`
- `qrcode.console_scripts` -> keep as Python wrapper initially or map to `src/cli.rs` with a thin Python entry layer to preserve `optparse`-level behavior

## Assumptions / gaps
- `get_api_signatures` indexes style submodules (`qrcode.image.styles.*`), but those source files were not listed by `find` output and were not inspected directly. This plan only makes claims grounded in files read here; style-module behavior is inferred only where referenced by `image/base.py`, `styledpil.py`, `svg.py`, and tests.
- Release helper `qrcode/release.py` is likely not needed for runtime migration unless packaging parity is required.
