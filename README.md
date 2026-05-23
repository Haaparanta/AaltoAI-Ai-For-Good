# Agentic Py2Rust Migrator

Migrates Python projects to Rust with test-driven workflow and human review. The **source project is never modified** — outputs go to sibling folders. A [Textual](https://textual.textualize.io/) TUI runs the pipeline; at startup you pick an **LLM provider and model**.

## Architecture

```mermaid
flowchart TB
    User((User)) --> TUI[Textual TUI]
    TUI --> LLM[LLM API]
    TUI <--> Orch[Orchestrator]

    Orch --> Analyzer
    Orch --> PyTester[Py Tester]
    Orch --> Scaffolder
    Orch --> Translator
    Orch --> Reviewer
    Orch --> Exec[Executor]

    Analyzer --> LLM
    PyTester --> LLM
    Scaffolder --> LLM
    Translator --> LLM
    Reviewer --> LLM

    Analyzer --> ME[Migration Executor]
    PyTester --> ME
    Scaffolder --> ME
    Translator --> ME
    Reviewer --> ME
    Exec --> ME

    ME --> Source[source/ read-only]
    ME --> Py[py_tests/]
    ME --> Ru[rust/ PyO3]
```

**Agents:** see [Agents](#agents) below for roles, tools, and when each runs.

**On disk** (for `myproject/` at `/path/to/`):

```text
myproject/                      # read-only
myproject_migration_py_tests/   # migration_plan.md, pytest
myproject_migration_rust/       # Cargo.toml, pyproject.toml, PyO3 src/
```

Tool paths: `source/`, `py_tests/`, `rust/` (writes to `source/` are blocked).

## Workflow

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant A as Agents
    participant E as Executor

    U->>O: Select LLM, then start (r)
    O->>A: 1 Create Python tests → py_tests/
    A->>E: pytest against source
    O->>U: 2 Review
    U-->>O: Approve / feedback
    O->>A: 3 Translate code → PyO3 rust/
    O->>U: 4 Review
    U-->>O: Approve / feedback
    O->>E: 5 maturin build, pip install, pytest
    alt failure
        O->>A: Fix (Translator)
        E->>O: Retry
    end
    O->>U: Done or pause for review
```

| Key | Action |
|-----|--------|
| **r** | Start |
| **a** | Approve review |
| **s** | Feedback (re-run prior step) |
| **m** | Change model |
| **↑ / ↓** | Select active agent run |
| **f** | Cycle activity log filter (all / selected run / role) |
| **c** | Toggle compact layout |
| **x** | Cancel active agent runs |
| **q** | Quit |

## Concurrent agents

Multiple agent instances can run in parallel when their write scopes do not overlap (for example, Py Tester shards per test file, or Translator shards per Rust source file).

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAX_AGENT_CONCURRENCY` | `4` (OpenAI), `2` (Cursor bridge) | Max simultaneous agent LLM turns |

The TUI shows an **Active runs** table, a **pipeline strip**, concurrency slots (`▶ N/M slots`), and per-run detail when you select a row.

## Agents

The pipeline uses **eight coordinated roles**. Six are LLM-backed specialists; two are non-LLM infrastructure roles. The **Orchestrator** drives step order, human-review pauses, quality gates, and fix loops. The **Executor** runs shell commands (`pytest`, `cargo`, `maturin`) without an LLM.

| Agent | LLM | Write scope | Pipeline role |
|-------|-----|-------------|---------------|
| **Orchestrator** | No | — | Advances the 5-step workflow, pauses for human review, dispatches fix loops after lint/pytest/clippy/wheel failures |
| **Analyzer** | Yes | `py_tests/` | Step 1 — reads the Python project and writes `migration_plan.md` |
| **Py Tester** | Yes | `py_tests/` | Step 1 — writes pytest that captures current Python behavior (can fan out per test file) |
| **Reviewer** | Yes | read-only | After steps 1 and 3 — produces a brief for the human before each review gate |
| **Scaffolder** | Yes | `rust/` | Step 3 — creates a compilable PyO3/maturin skeleton (`Cargo.toml`, `pyproject.toml`, `src/`) |
| **Translator** | Yes | `rust/` | Step 3 — implements PyO3 bindings; fixes failures after wheel pytest or clippy (can fan out per `.rs` file) |
| **Executor** | No | — | Runs `pytest`, `cargo fmt/clippy`, and `maturin build` + install; shown in the TUI during gates |

### Orchestrator

**Intended function:** Workflow controller — not an LLM agent. Tracks the current step, resets agent status between stages, runs quality gates (flake8/mypy, baseline pytest, `cargo fmt/clippy`, maturin wheel + migration pytest), and pauses for human approve/feedback. Dispatches **Py Tester** or **Translator** fix agents when automated gates fail.

### Analyzer

**Intended function:** Discover and document the Python codebase before any tests or Rust work.

- Reads `source/` (read-only) via `read_file`, `get_api_signatures`, and `execute_command`
- Writes **`py_tests/migration_plan.md`**: module inventory, dependencies, migration risks, proposed test focus, proposed Rust/PyO3 layout
- Runs first in step 1, before Py Tester
- Does **not** write pytest or Rust code

### Py Tester

**Intended function:** Encode the Python project's public behavior as pytest — the contract for the migration.

- Uses API signatures and the migration plan to write tests under **`py_tests/tests/`**
- Python files are auto-formatted and linted (flake8/mypy) on write
- Runs baseline **`pytest`** against the original Python project (`PYTHONPATH=source`)
- On lint or pytest failure, re-invoked in a **fix loop** to repair tests
- Can run **multiple instances in parallel**, one per test file, when several modules exist

### Reviewer

**Intended function:** Prepare the human for approve/feedback decisions — read-only advisory agent.

- Invoked automatically after step 1 and step 3 complete successfully
- Reads artifacts in `source/`, `py_tests/`, and `rust/`; **never writes files**
- Returns a structured markdown brief: what changed, coverage vs plan, risks, suggested review focus
- Brief is appended to the TUI summary before the human review gate

### Scaffolder

**Intended function:** Bootstrap the PyO3 extension crate before implementation.

- Reads migration plan, approved pytest, and Python sources
- Writes **`rust/Cargo.toml`**, **`rust/pyproject.toml`**, and **`rust/src/`** stub modules with `#[pymodule]` and `todo!()` bodies
- Runs **`cargo check`** to ensure the skeleton compiles
- Runs **before** Translator in step 3; does **not** implement full logic or modify pytest

### Translator

**Intended function:** Implement the Python-to-PyO3 migration so the **same pytest suite** passes against the built wheel.

- Builds on Scaffolder output; writes only under **`rust/`**
- Must preserve the public Python API that pytest imports
- After step 3, **`cargo fmt --check`** and **`cargo clippy`** run as a quality gate; Translator fixes failures
- In step 5, if migration pytest fails after wheel install, Translator is dispatched to fix Rust/PyO3 code
- Can run **multiple instances in parallel**, one per `rust/src/*.rs` file (excluding `lib.rs`), when several modules exist

### Executor

**Intended function:** Deterministic command runner — not an LLM agent.

- **`pytest`** — baseline (against source) and migration (against installed wheel)
- **`cargo fmt --check`** / **`cargo clippy`** — Rust quality gate after translation
- **`maturin build`** + pip install — step 5 wheel build before migration pytest
- Status shown in the TUI agents table during command execution

### Agent execution order (happy path)

```text
1. Analyzer → Py Tester → [lint + baseline pytest gates]
   → Reviewer → human review
2. Scaffolder → Translator → [fmt/clippy gate]
   → Reviewer → human review
3. Executor (maturin + migration pytest)
   → done, or Translator fix loop on failure
```

## Setup

**Requires:** [uv](https://docs.astral.sh/uv/), `pytest`, `cargo`, `maturin`, and at least one LLM provider.

| Variable | When |
|----------|------|
| `OPENAI_API_KEY` | OpenAI (optional `OPENAI_BASE_URL`) |
| `CURSOR_BRIDGE_BASE_URL` | Optional override (default `http://127.0.0.1:8765/v1`) for [cursor-api-proxy](https://github.com/anyrobert/cursor-api-proxy) |
| `CURSOR_API_KEY` | **Required for chat** via the bridge (see below). Passed to the proxy’s spawned `agent` process. |
| `MAX_AGENT_CONCURRENCY` | Optional cap on parallel agent runs (provider-aware default) |

Providers are checked at startup (`/v1/models`). The app errors only if **none** work.

### Cursor bridge (cursor-api-proxy)

`agent login` alone is **not enough** for the proxy: by default it runs each request in an isolated temp workspace and overrides `HOME` / `CURSOR_CONFIG_DIR`, so the child `agent` cannot see your login from `~/.cursor`.

1. Install the Cursor agent CLI and add it to `PATH` (`~/.local/bin`).
2. Create an API key: [Cursor Dashboard → Integrations](https://cursor.com/dashboard/integrations) → API Keys.
3. Start the proxy **in the same terminal** with the key exported:

```bash
export PATH="$HOME/.local/bin:$PATH"
export CURSOR_API_KEY="cursor_..."   # your key from the dashboard
npx cursor-api-proxy
```

4. Verify chat works:

```bash
curl http://127.0.0.1:8765/v1/models
curl http://127.0.0.1:8765/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"composer-2-fast","messages":[{"role":"user","content":"Say OK"}],"max_tokens":16}'
```

5. Run the migrator in another terminal: `uv run orchestrator -w /path/to/project`

Optional: `CURSOR_BRIDGE_API_KEY` if you want the HTTP API itself to require `Authorization: Bearer …` (separate from `CURSOR_API_KEY` for the agent).

**“cursor-user is missing from keychain”** — The CLI normally stores login in the macOS Keychain. That fails or is invisible when:

- the proxy spawns `agent` with a fake `HOME` (default for cursor-api-proxy), or
- you use SSH / a non-GUI terminal where Keychain access is blocked.

Use **`CURSOR_API_KEY`** (above) instead of relying on `agent login` for the bridge. To fix Keychain for direct `agent` use, run `agent logout` then `agent login` in **Terminal.app** on the Mac itself (not over SSH), and allow Keychain access when prompted.

```bash
uv sync
export OPENAI_API_KEY=sk-...
uv run orchestrator -w /path/to/python/project
```

## Executor MCP

Optional stdio MCP for Cursor: `uv run executor-mcp` (see [`.cursor/mcp.json`](.cursor/mcp.json)). The TUI uses the same tools in-process via [`orchestrator/migration_executor.py`](orchestrator/migration_executor.py).

Main code: [`orchestrator/`](orchestrator/), [`agents/`](agents/), [`llm/`](llm/), [`executor_mcp/`](executor_mcp/).
