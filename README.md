# Agentic Py2Rust Migrator

An agentic terminal tool designed to autonomously migrate Python projects to Rust using a Test-Driven Development (TDD) approach, with human-in-the-loop review stages to ensure high-quality, verifiable translations.

This project is designed to be developed using Cursor, leveraging multi-agent orchestration to divide the complex task of codebase migration into manageable, verifiable steps.

## System Architecture

Based on the whiteboard design, the system relies on an **Orchestrator** managing specialized agents, which all interact with the system via an MCP (Model Context Protocol) or direct File/Command interface.



```mermaid
graph TD
    User((Human User)) <-->|Reviews & Prompts| Orkest

    Orkest[Orchestrator Agent]
    Orkest -->|Coordinates| Analyzer[Analyzer Agent]
    Orkest -->|Coordinates| Tester[Tester Agent]
    Orkest -->|Coordinates| Translator[Translator Agent]
    Orkest -->|Coordinates| Executor[Test Executor Agent]

    Analyzer --> MCP[File System / MCP]
    Tester --> MCP
    Translator --> MCP
    Executor -->|cmd / read / write / results| MCP

```

### Agent Roles

1. **Orchestrator Agent (`Orkest`)**: The master controller. Manages state, prompts the user for reviews at specific checkpoints, and delegates tasks to the sub-agents.
2. **Analyzer Agent**: Reads the provided Python files/project to understand the structure, dependencies, and core logic.
3. **Tester Agent**: Responsible for writing unit tests. It first writes tests for the original Python code, and later translates those tests into Rust.
4. **Translator Agent**: Converts the Python source code into Rust source code, ensuring it aligns with the generated Rust tests.
5. **Test Executor Agent**: Interacts with the terminal to run test commands (e.g., `pytest`, `cargo test`) and handles file reading/writing (the MCP layer).

---

## Migration Workflow (Human-in-the-Loop)

The migration process follows a strict 6-step pipeline ensuring the generated Rust code behaves exactly like the Python code.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant O as Orchestrator
    participant A as Agents (Tester/Translator)
    participant E as Executor (MCP)

    O->>A: Analyze Python Code
    O->>A: CREATE TEST (Python)
    A->>E: Write Python Tests
    O->>U: REVIEW (Human) - Plan & Py Tests
    U-->>O: Approve or Modify
    
    O->>A: TRANSLATE TEST (to Rust)
    A->>E: Write Rust Tests
    O->>U: REVIEW (Human) - Rust Tests
    U-->>O: Approve or Prompt Changes
    
    O->>A: TRANSLATE CODE (to Rust)
    A->>E: Write Rust Source
    O->>U: REVIEW (Human) - Rust Code
    U-->>O: Approve or Prompt Changes
    
    O->>E: TEST (Run Rust Tests)
    E-->>O: Return execution results
    O->>U: Display Final Results

```

### Step-by-Step Breakdown:

1. **CREATE TEST (PY)**: The Analyzer and Tester agents read the Python project and generate comprehensive Python test cases to establish a baseline of the current behavior.
2. **REVIEW (HUMAN)**: The Orchestrator pauses execution. The user reviews the migration plan and the generated Python tests.
3. **TRANSLATE TEST**: The Tester agent converts the approved Python tests into equivalent Rust tests (e.g., using `#[test]`).
4. **REVIEW**: The user reviews the generated Rust tests. The user can prompt the agent to make adjustments or add edge cases.
5. **TRANSLATE CODE**: The Translator agent converts the actual Python implementation into Rust.
6. **TEST**: The Executor agent runs `cargo test`. The Orchestrator evaluates the results. If tests fail, it can loop back to the Translator to fix the code, or present the results to the user.

---

## Cursor Development Guide

This `README.md` is designed to be the foundational context for Cursor. When building this project:

1. **Phase 1: The Executor (MCP)**: Start by building the file read/write and command execution utilities. These are the tools all agents will need.
2. **Phase 2: The Orchestrator CLI**: Build the basic terminal interface that can pause for user input (the Human-in-the-loop mechanism).
3. **Phase 3: LLM Integration & Prompts**: Define the system prompts for each specific agent role (Tester, Translator, Analyzer).
4. **Phase 4: Workflow Implementation**: Tie the agents together using the Orchestrator following the exact 6-step numbered list above.

*Tip for Cursor: Reference the mermaid diagrams above when asking Cursor to structure the agent classes. E.g., "@README.md Create the Orchestrator class that implements the 6 steps outlined in the sequence diagram."*
"""