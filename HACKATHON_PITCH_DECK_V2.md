---
marp: true
theme: default
paginate: true
title: Trustworthy AI Software Modernization
description: Revised hackathon pitch deck for the Agentic Py2Rust Migrator
---

<style>
section {
  background: #f7faf8;
  color: #11221b;
  font-family: "Inter", "Aptos", "Segoe UI", sans-serif;
  letter-spacing: -0.01em;
  padding: 62px 74px;
}

h1 {
  color: #0f3d2e;
  font-size: 44px;
  line-height: 1.05;
  margin-bottom: 22px;
}

h2 {
  color: #1f7a55;
  font-size: 28px;
  margin-top: 0;
}

p,
li {
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
  font-size: 56px;
  max-width: 920px;
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

.pill {
  display: inline-block;
  border: 1px solid #7bd6a3;
  border-radius: 999px;
  color: #7bd6a3;
  font-size: 18px;
  font-weight: 700;
  margin: 4px 10px 4px 0;
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

.grid-2,
.grid-3,
.grid-4 {
  display: grid;
  gap: 16px;
  margin-top: 24px;
}

.grid-2 {
  grid-template-columns: repeat(2, 1fr);
}

.grid-3 {
  grid-template-columns: repeat(3, 1fr);
}

.grid-4 {
  grid-template-columns: repeat(4, 1fr);
}

.card,
.step,
.node {
  background: #e8f2ed;
  border: 1px solid #bdd4c7;
  border-radius: 16px;
  color: #11221b;
  padding: 16px;
}

.card strong,
.step strong,
.node strong {
  color: #b75521;
  display: block;
  font-size: 21px;
  margin-bottom: 8px;
}

.step {
  font-size: 17px;
}

.step strong {
  font-size: 15px;
  text-transform: uppercase;
}

.node {
  font-size: 18px;
  font-weight: 700;
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

.flow {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: center;
  margin: 28px 0;
}

.flow-column {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.arrow {
  color: #1f7a55;
  font-size: 30px;
  font-weight: 800;
}

.small {
  font-size: 18px;
}

.quote {
  color: #0f3d2e;
  font-size: 34px;
  font-weight: 800;
  line-height: 1.15;
  margin-top: 32px;
  max-width: 960px;
}
</style>

<!-- _class: title -->

# Trustworthy AI Software Modernization

## Turning risky rewrites into measured migration workflows

<span class="pill">Demo: Python to Rust with PyO3</span>
<span class="pill">Vision: language-agnostic modernization</span>
<span class="pill">Proof: tests + benchmarks</span>

**AI should help valuable software survive technological change.**

---

<!-- _class: section -->

# The Problem

Important software often survives longer than the technology stack it was built on.

- Rewrites are expensive, slow, and risky
- Behavior is hidden in edge cases, not documented
- Small organizations often lack the time or specialists to modernize systems
- AI can write code, but unvalidated AI rewrites are hard to trust

<div class="callout">
<strong>The modernization gap:</strong> AI can accelerate migration, but only transparent, tested, and measurable workflows can make it safe and accessible for everyone.
</div>

---

# Why Modernize Code?

Migration is not about chasing a newer language. It is about making useful software cheaper, safer, and easier to keep alive.

<div class="grid-2">
<div class="card"><strong>Price</strong>Moving from expensive proprietary ecosystems, such as MATLAB, to open ecosystems like Python can lower licensing barriers for students, researchers, nonprofits, and small companies.</div>
<div class="card"><strong>Sustainability</strong>Moving performance-critical Python code to Rust can reduce CPU time, which can lower energy use and cloud cost for repeated workloads.</div>
<div class="card"><strong>Longevity</strong>Updating older code to newer languages, runtimes, and package formats extends its useful lifetime and keeps it accessible to future maintainers.</div>
<div class="card"><strong>Security</strong>Modernizing can remove risky dependencies and use safer defaults, for example replacing memory-unsafe native extensions with Rust code that prevents many buffer and use-after-free bugs at compile time.</div>
</div>

<div class="callout">
<strong>Modernization makes software more accessible:</strong> cheaper to adopt, cheaper to run, easier to maintain, and safer to depend on.
</div>

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
<div class="node">Py Tester</div>
<div class="node">Reviewer</div>
<div class="node">Scaffolder</div>
</div>
<div class="flow-column">
<div class="node">Translator</div>
<div class="node">Executor</div>
<div class="node">Benchmarker</div>
<div class="node">Agent pool</div>
</div>
<div class="arrow">&rarr;</div>
<div class="flow-column">
<div class="node">Read-only source</div>
<div class="node">PyO3 Rust wheel</div>
<div class="node">pytest validation</div>
<div class="node">benchmark reports</div>
</div>
</div>

**Why this matters:** agents work through constrained tools, scoped outputs, quality gates, and human checkpoints.

---

# Migration Workflow

<div class="grid-3">
<div class="step"><strong>1. Capture behavior</strong>Analyze the Python project and generate pytest that documents the current behavior.</div>
<div class="step"><strong>2. Human review</strong>Reviewer summarizes coverage, risk, and suggested focus before approval.</div>
<div class="step"><strong>3. Scaffold Rust</strong>Create a PyO3/maturin project that preserves the Python import surface.</div>
<div class="step"><strong>4. Translate behavior</strong>Implement Rust code behind the same Python-facing API.</div>
<div class="step"><strong>5. Validate wheel</strong>Build with maturin, install the wheel, and run the same pytest suite.</div>
<div class="step"><strong>6. Measure impact</strong>Discover benchmark cases, compare isolated Python vs Rust wheels, and produce CSV, text, metadata, and graph artifacts.</div>
</div>

---

<!-- _class: section -->

# Why Python to Rust?

Python is accessible and widely used. Rust is fast, memory-safe, and efficient.

That makes Python-to-Rust a strong first case study:

- Keep the Python API that users already know
- Move performance-critical internals to Rust
- Build a distributable wheel with PyO3 and maturin
- Validate that behavior still matches the original package
- Measure whether the migration actually improves performance

**The point is not only Rust. The point is trustworthy modernization.**

---

# Our Approach

We built an agentic migration pipeline that treats translation as an engineering process, not a one-shot prompt.

<div class="grid-2">
<div class="card"><strong>Preserve behavior first</strong>Generate pytest suites against the original Python project before changing the implementation.</div>
<div class="card"><strong>Reimplement with guardrails</strong>Translate into a Rust PyO3 extension while preserving the Python-facing API.</div>
<div class="card"><strong>Validate with real tools</strong>Run linting, Rust quality gates, maturin builds, installed-wheel pytest, and fix loops.</div>
<div class="card"><strong>Measure the result</strong>Benchmark isolated Python and Rust wheel installs and write performance reports to measurement artifacts.</div>
</div>

<div class="callout">
<strong>Safety rule:</strong> the original source project is read-only. Generated tests, Rust code, and measurements go to separate output folders.
</div>

---

# Why Judges Should Care

Most AI coding demos show generation. This project shows preservation.

<div class="grid-2">
<div class="card"><strong>Trust</strong>Behavior is encoded as tests before implementation is replaced.</div>
<div class="card"><strong>Transparency</strong>Human reviewers see plans, generated artifacts, risks, and summaries.</div>
<div class="card"><strong>Accountability</strong>Migration success is checked by compilers, test runners, and benchmark reports.</div>
<div class="card"><strong>Access</strong>Small teams get a guided modernization workflow normally reserved for large engineering organizations.</div>
</div>

---

# Demo Story

In the demo, we can show:

1. Start from an existing Python project
2. Generate a migration plan and behavior-preserving pytest suite
3. Review the plan and tests before translating implementation
4. Scaffold and implement a Rust PyO3 package
5. Build and install the Rust wheel with maturin
6. Run the same pytest suite against the migrated wheel
7. Produce Python vs Rust benchmark measurements from isolated wheel installs

<div class="callout">
<strong>Narrative:</strong> the user stays in control while agents do the repetitive migration, validation, and repair work.
</div>

---

# Benchmarking Proof

The latest workflow does not just claim the Rust migration is faster. It measures it.

<div class="grid-2">
<div class="card"><strong>Auto-discovery</strong>Benchmark cases can come from custom suites, known generators, API signatures, or pytest call patterns.</div>
<div class="card"><strong>LLM fallback</strong>If automatic discovery is not enough, the Benchmarker can inspect the project and write a benchmark suite.</div>
<div class="card"><strong>Fair comparison</strong>Python source and Rust PyO3 wheels are installed into isolated targets before timing.</div>
<div class="card"><strong>Real outputs</strong>Reports include raw runs, summaries, metadata, and graphs for latency, variance, resources, and speedup.</div>
</div>

---

<!-- _class: section -->

# Beyond Python to Rust

Python to Rust is the first proof point, not the limit.

<div class="grid-3">
<div class="card"><strong>What stays the same</strong>Analyze, test, review, translate, validate, repair, measure.</div>
<div class="card"><strong>What changes</strong>Language prompts, project scaffold, package tools, test runner, and benchmark adapter.</div>
<div class="card"><strong>What this enables</strong>Language-agnostic migration profiles for different modernization goals.</div>
</div>

Examples:

- JavaScript to TypeScript for safer maintainability
- Python to Go for deployment simplicity
- Java to Kotlin for JVM modernization
- R or MATLAB to Python for scientific software longevity

---

# Current State

Implemented in the repo today:

<div class="grid-2">
<div class="card"><strong>Workflow</strong>Six-step pipeline: tests, review, PyO3 translation, review, wheel validation, benchmarking.</div>
<div class="card"><strong>Agents</strong>Specialized roles for analysis, pytest generation, review, scaffolding, translation, execution, and measurement.</div>
<div class="card"><strong>Quality gates</strong>flake8, mypy, baseline pytest, cargo fmt, cargo clippy, maturin build, installed-wheel pytest.</div>
<div class="card"><strong>Measurement</strong>Benchmarks compare isolated Python and Rust wheel installs across input tiers and write reports to measurements.</div>
</div>

Next step: formalize language profiles so source language, target language, packaging, validation, and measurement become configurable.

---

<!-- _class: section -->

# Impact

Remember why modernization matters:

<div class="grid-2">
<div class="card"><strong>Price</strong>Open and efficient ecosystems reduce licensing, infrastructure, and operational costs.</div>
<div class="card"><strong>Sustainability</strong>Faster code can use less CPU, lowering energy use for repeated workloads.</div>
<div class="card"><strong>Longevity</strong>Updating old code keeps important systems usable for future teams.</div>
<div class="card"><strong>Access</strong>Smaller organizations can modernize without needing a large rewrite budget.</div>
</div>

**Goal:** make trustworthy modernization available to the teams that need it most.

---

# Ask / Next Steps

We are looking for feedback on:

- Which language pairs would create the most social impact?
- What evidence would make users trust an AI-assisted migration?
- Which benchmark metrics matter most: latency, cost, energy, memory, or package size?
- How should human review be designed for non-expert maintainers?

<div class="callout">
<strong>Hackathon goal:</strong> prove trustworthy Python-to-Rust modernization, then generalize the pattern into migration profiles for many language pairs.
</div>

---

<!-- _class: closing -->

# Closing

## AI should help software survive technological change.

Not just generate new code, but preserve behavior, reduce migration risk, and extend the life of important systems.

**Agentic Code Migration for Good**  
Test-driven. Human-reviewed. Benchmarked. Built for trustworthy modernization.
