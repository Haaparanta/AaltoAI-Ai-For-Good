---
marp: true
theme: default
paginate: true
title: Agentic Code Migration for Good
description: Hackathon judge pitch deck for the Agentic Py2Rust Migrator
---

<style>
section {
  background: #f7faf8;
  color: #11221b;
  font-family: "Inter", "Aptos", "Segoe UI", sans-serif;
  letter-spacing: -0.01em;
  padding: 64px 76px;
}

h1 {
  color: #0f3d2e;
  font-size: 44px;
  line-height: 1.05;
  margin-bottom: 24px;
}

h2 {
  color: #1f7a55;
  font-size: 28px;
  margin-top: 0;
}

p, li {
  font-size: 23px;
  line-height: 1.35;
}

strong {
  color: #b75521;
}

code {
  background: #e8f2ed;
  color: #0f3d2e;
  border-radius: 6px;
  padding: 2px 6px;
}

table {
  font-size: 19px;
  border-collapse: collapse;
}

th {
  background: #dcebe4;
  color: #0f3d2e;
}

td, th {
  border: 1px solid #bdd4c7;
  padding: 10px 12px;
}

section::after {
  color: #6f8579;
  font-size: 15px;
}

section.title,
section.section,
section.closing {
  background: #0f241d;
  color: #f7faf8;
}

section.title h1,
section.section h1,
section.closing h1 {
  color: #f7faf8;
  font-size: 58px;
  max-width: 900px;
}

section.title h2,
section.section h2,
section.closing h2 {
  color: #7bd6a3;
}

section.title strong,
section.section strong,
section.closing strong {
  color: #ffb078;
}

section.title::before,
section.section::before,
section.closing::before {
  content: "";
  position: absolute;
  right: 72px;
  top: 64px;
  width: 150px;
  height: 150px;
  border: 3px solid #7bd6a3;
  border-radius: 999px;
}

section.title::after,
section.section::after,
section.closing::after {
  color: #9fb8ac;
}

.pill {
  display: inline-block;
  border: 1px solid #7bd6a3;
  border-radius: 999px;
  color: #7bd6a3;
  font-size: 18px;
  font-weight: 700;
  margin-right: 10px;
  padding: 6px 12px;
}

.callout {
  background: #e8f2ed;
  border-left: 8px solid #1f7a55;
  border-radius: 14px;
  color: #11221b;
  margin-top: 28px;
  padding: 20px 24px;
}

.callout strong {
  color: #0f3d2e;
}

.metric-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(3, 1fr);
  margin-top: 26px;
}

.metric {
  background: #e8f2ed;
  border: 1px solid #bdd4c7;
  border-radius: 16px;
  color: #11221b;
  padding: 18px;
}

.metric strong {
  color: #b75521;
  display: block;
  font-size: 24px;
  margin-bottom: 8px;
}

.flow {
  align-items: center;
  display: flex;
  gap: 14px;
  justify-content: center;
  margin: 30px 0;
}

.flow-column {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.node {
  background: #e8f2ed;
  border: 1px solid #bdd4c7;
  border-radius: 16px;
  color: #11221b;
  font-size: 19px;
  font-weight: 700;
  min-width: 150px;
  padding: 14px 16px;
  text-align: center;
}

.node.dark {
  background: #0f3d2e;
  border-color: #0f3d2e;
  color: #f7faf8;
}

.node.accent {
  background: #fff0e7;
  border-color: #e0ad8f;
  color: #7a3513;
}

.arrow {
  color: #1f7a55;
  font-size: 30px;
  font-weight: 800;
}

.workflow {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, 1fr);
  margin-top: 24px;
}

.step {
  background: #e8f2ed;
  border: 1px solid #bdd4c7;
  border-radius: 16px;
  color: #11221b;
  font-size: 18px;
  padding: 14px;
}

.step strong {
  color: #b75521;
  display: block;
  font-size: 17px;
  margin-bottom: 6px;
  text-transform: uppercase;
}

.pattern-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: 1fr 1fr 1fr;
  margin: 22px 0;
}

.pattern-head,
.pattern-cell {
  border-radius: 12px;
  padding: 12px 14px;
}

.pattern-head {
  background: #0f3d2e;
  color: #f7faf8;
  font-size: 17px;
  font-weight: 800;
}

.pattern-cell {
  background: #e8f2ed;
  border: 1px solid #bdd4c7;
  color: #11221b;
  font-size: 17px;
}

.pattern-cell.stage {
  background: #fff0e7;
  border-color: #e0ad8f;
  color: #7a3513;
  font-weight: 800;
}
</style>

<!-- _class: title -->

# Agentic Code Migration for Good

## Safer AI-assisted software migration

<span class="pill">Demo today: Python to Rust</span>
<span class="pill">Vision: many language pairs</span>

**A safer way to modernize important software with AI**

---

<!-- _class: section -->

# The Problem

Critical software often gets trapped in legacy code.

- Rewrites are expensive, slow, and risky
- Behavior is hidden in edge cases, not documented
- Small organizations often lack the time or specialists to modernize systems
- AI can write code, but unvalidated AI rewrites are hard to trust

This creates a gap between what is technically possible and what is safely usable: AI can accelerate migration, but only with transparency, testing, and measurable correctness can it become accessible to everyone.

<div class="callout">
<strong>For AI for Good:</strong> safer modernization helps civic tech, research tools, NGO systems, and public-interest software stay useful for the long term.
</div>

---

# Our Solution

An agentic migration pipeline that treats translation as an engineering workflow, not a one-shot prompt.

1. Understand the source project
2. Capture behavior as tests
3. Translate tests into the target ecosystem
4. Translate implementation
5. Run real tooling and repair failures
6. Keep a human in the loop at key decisions

<div class="callout">
<strong>Core promise:</strong> migrate with guardrails: tests, review, isolation, and feedback loops.
</div>

---

<!-- _class: section -->
# Software outlives the environments it was built for

As systems grow and age, organizations face pressure from:

<div class="metric-grid"> <div class="metric"><strong>Performance</strong>Reduce compute cost, latency, and infrastructure overhead.</div> <div class="metric"><strong>Accessibility</strong>Run reliably on older hardware, edge devices, and constrained environments.</div> <div class="metric"><strong>Maintainability</strong>Move aging codebases into ecosystems with stronger tooling and long-term support.</div> </div> <div class="metric-grid"> <div class="metric"><strong>Security</strong>Adopt safer languages and modern dependency ecosystems.</div> <div class="metric"><strong>Scalability</strong>Support larger workloads without proportional infrastructure growth.</div> <div class="metric"><strong>Longevity</strong>Preserve valuable software instead of rewriting from scratch.</div> </div>

**Sustainability is not only environmental. It is also making good software maintainable, affordable, and accessible over time.**

---

# What We Built

**Agentic Py2Rust Migrator**

- Textual terminal UI for running and monitoring the migration
- LLM-backed Analyzer, Tester, and Translator agents
- Executor tools for reading, writing, and running commands safely
- Human approval checkpoints before moving to the next stage
- Validation through `pytest`, `cargo test`, linting, and retry loops

The original source project is never modified.

---

# System Architecture

<div class="flow">
<div class="node accent">Human reviewer</div>
<div class="arrow">&rarr;</div>
<div class="node dark">Textual TUI</div>
<div class="arrow">&rarr;</div>
<div class="node dark">Orchestrator</div>
<div class="arrow">&rarr;</div>
<div class="flow-column">
<div class="node">Analyzer</div>
<div class="node">Tester</div>
<div class="node">Translator</div>
<div class="node">Executor</div>
</div>
<div class="arrow">&rarr;</div>
<div class="flow-column">
<div class="node">OpenAI-compatible LLM</div>
<div class="node">Sandboxed tools</div>
<div class="node">Read-only source</div>
<div class="node">Generated outputs</div>
</div>
</div>

**Why this matters:** the AI agents do not freely mutate the original project. They work through constrained tools and reviewable artifacts.

---

# Migration Workflow

<div class="workflow">
<div class="step"><strong>1. Start</strong>Select model and source project</div>
<div class="step"><strong>2. Analyze</strong>Create migration plan and baseline tests</div>
<div class="step"><strong>3. Verify</strong>Run Python tests against original behavior</div>
<div class="step"><strong>4. Review</strong>Human approves or gives feedback</div>
<div class="step"><strong>5. Translate tests</strong>Create target-language test suite</div>
<div class="step"><strong>6. Translate code</strong>Generate implementation in Rust</div>
<div class="step"><strong>7. Validate</strong>Run target compiler and tests</div>
<div class="step"><strong>8. Repair</strong>Failures become targeted agent tasks</div>
</div>

---

# Why Judges Should Care

Most AI coding demos show code generation.  
This system shows **code migration with accountability**.

- Test-first: behavior is captured before implementation translation
- Human-centered: reviewers approve plans, tests, and code
- Tool-grounded: agents run real project commands, not just reasoning
- Safe by design: source is read-only; outputs are isolated
- Iterative: failures trigger targeted agent repair loops

---

# Demo Story

In the demo, we can show:

1. Select an LLM provider and model
2. Start migration on a Python project
3. Watch agents create a migration plan and Python tests
4. Approve or correct generated artifacts
5. Generate Rust tests and Rust implementation
6. Run `cargo test`
7. Show failed tests becoming concrete repair tasks

**Narrative:** the user stays in control while the system does the repetitive migration work.

---

<!-- _class: section -->

# Beyond Python to Rust

Python to Rust is the first proof point, not the limit.

The reusable pattern is:

<div class="pattern-grid">
<div class="pattern-head">Migration stage</div>
<div class="pattern-head">Python to Rust today</div>
<div class="pattern-head">Other languages tomorrow</div>
<div class="pattern-cell stage">Analyze source</div>
<div class="pattern-cell">Python project analysis</div>
<div class="pattern-cell">Source-language profile</div>
<div class="pattern-cell stage">Capture behavior</div>
<div class="pattern-cell">pytest tests</div>
<div class="pattern-cell">Source test runner</div>
<div class="pattern-cell stage">Translate tests</div>
<div class="pattern-cell">Rust integration tests</div>
<div class="pattern-cell">Target test framework</div>
<div class="pattern-cell stage">Translate code</div>
<div class="pattern-cell">Rust crate</div>
<div class="pattern-cell">Target project scaffold</div>
<div class="pattern-cell stage">Validate</div>
<div class="pattern-cell">cargo test</div>
<div class="pattern-cell">Target build/test command</div>
</div>

The same orchestration loop can support other pairs by swapping language profiles, prompts, layouts, and validators.

---

# Example Language Profiles

The system can be extended with language-specific adapters:

- **JavaScript to TypeScript:** infer behavior, generate typed implementation, validate with `npm test`
- **Python to Go:** capture Python behavior, generate Go tests, validate with `go test`
- **Java to Kotlin:** preserve JVM behavior, validate with Gradle or Maven
- **R to Python:** migrate data-science utilities, validate numerical outputs
- **MATLAB to Python:** modernize research scripts while preserving scientific results

**Key idea:** agents remain the same; the language profile changes.

---

<!-- _class: section -->

# Why This Is Better Than Direct Translation

A direct prompt asks: "Convert this code."

Our system asks:

- What behavior must be preserved?
- What tests prove the behavior?
- What should a human approve before moving forward?
- What does the target compiler or test runner say?
- Which agent should fix the failure?

This turns migration from a guessing problem into a controlled feedback loop.

---

# Current State

Built and working as a Python-to-Rust migration harness:

- Agent roles and workflow controller are implemented
- Sandboxed executor tools are implemented
- Read-only source and isolated output folders are implemented
- Human review gates are implemented
- LLM provider selection is implemented
- Test, lint, and repair loops are implemented

Next step for full multi-language support: formalize language profiles so prompts, folder layout, and validation commands become configuration.

---

<!-- _class: section -->

# Impact

This can help teams modernize important codebases without losing trust.

- Nonprofits can keep tools maintainable
- Researchers can migrate fragile scripts into production-ready languages
- Civic tech teams can reduce security and reliability risks
- Small teams can get expert-level migration scaffolding

**Vision:** make software modernization safer, cheaper, and accessible to teams that cannot afford large rewrite projects.

---

# Ask / Next Steps

We are looking for feedback on:

- Which language pairs matter most for real-world social impact?
- What validation guarantees would make users trust the migration?
- Which review experience would help non-experts supervise the process?

**Hackathon goal:** prove the migration workflow with Python to Rust, then generalize it into a language-agnostic migration platform.

---

<!-- _class: closing -->

# Closing

## AI should not just generate code.

It should help preserve behavior, reduce risk, and make software easier to maintain.

**Agentic Code Migration for Good**  
Test-driven, human-reviewed, extensible across languages.
