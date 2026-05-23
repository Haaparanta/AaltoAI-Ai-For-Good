---
marp: true
theme: default
paginate: true
title: Trustworthy AI Software Modernization
description: Visual hackathon pitch deck using screenshots and benchmark outputs
---

<style>
section {
  background: #f7faf8;
  color: #11221b;
  font-family: "Inter", "Aptos", "Segoe UI", sans-serif;
  letter-spacing: -0.01em;
  padding: 58px 70px;
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
section.demo,
section.closing {
  background: #0f241d;
  color: #f7faf8;
}

section.title h1,
section.section h1,
section.demo h1,
section.closing h1 {
  color: #f7faf8;
  font-size: 56px;
  max-width: 930px;
}

section.title h2,
section.section h2,
section.demo h2,
section.closing h2 {
  color: #7bd6a3;
}

section.title strong,
section.section strong,
section.demo strong,
section.closing strong {
  color: #ffb078;
}

section.title::before,
section.section::before,
section.demo::before,
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

.grid-2,
.grid-3 {
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

.card,
.step,
.node,
.stat {
  background: #e8f2ed;
  border: 1px solid #bdd4c7;
  border-radius: 16px;
  color: #11221b;
  padding: 16px;
}

.card strong,
.step strong,
.node strong,
.stat strong {
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

.flow {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: center;
  margin: 26px 0;
}

.flow-column {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.node {
  font-size: 18px;
  font-weight: 700;
  min-width: 135px;
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

.quote {
  color: #0f3d2e;
  font-size: 34px;
  font-weight: 800;
  line-height: 1.15;
  margin-top: 32px;
  max-width: 980px;
}

.screenshot {
  border: 2px solid #bdd4c7;
  border-radius: 18px;
  display: block;
  margin: 18px auto 0;
  max-height: 470px;
  max-width: 100%;
}

.graph {
  background: white;
  border: 2px solid #bdd4c7;
  border-radius: 18px;
  display: block;
  margin: 10px auto 0;
  max-height: 410px;
  max-width: 100%;
}

.image-grid {
  align-items: center;
  display: grid;
  gap: 18px;
  grid-template-columns: 1fr 1fr;
}

.caption {
  color: #536b5f;
  font-size: 16px;
  margin-top: 8px;
  text-align: center;
}

.demo .caption {
  color: #c3d7cd;
}

.summary-quote {
  color: #f7faf8;
  font-size: 30px;
  font-weight: 800;
  line-height: 1.12;
  margin: 18px 0 12px;
  max-width: 900px;
}

.summary-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, 1fr);
  margin-top: 14px;
}

.summary-card {
  background: #e8f2ed;
  border: 1px solid #bdd4c7;
  border-radius: 14px;
  color: #11221b;
  font-size: 18px;
  line-height: 1.25;
  padding: 12px 14px;
}

.summary-card strong {
  color: #b75521;
  display: block;
  font-size: 19px;
  margin-bottom: 4px;
}
</style>

<!-- _class: title -->

# Trustworthy AI Software Modernization

## From risky rewrites to tested, measured migration

<span class="pill">Demo: Python to Rust with PyO3</span>
<span class="pill">Evidence: screenshots + benchmarks</span>
<span class="pill">Vision: language-agnostic modernization</span>

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
<div class="card"><strong>Price</strong>Moving from expensive proprietary ecosystems, can lower licensing barriers.</div>
<div class="card"><strong>Sustainability</strong>Moving code to more efficient languages can reduce CPU time, lowering energy use and cloud cost for repeated workloads.</div>
<div class="card"><strong>Longevity</strong>Updating older code to newer languages, runtimes, and package formats extends its useful lifetime.</div>
<div class="card"><strong>Security</strong>Updating the language can reduce runtime errors in performance-critical code.</div>
</div>

---
# Our Approach

We turn code migration into an engineering workflow instead of a one-shot prompt.

<div class="grid-2">
<div class="card"><strong>Preserve behavior first</strong>Generate pytest suites against the original project before replacing implementation.</div>
<div class="card"><strong>Reimplement with guardrails</strong>Translate into a Rust PyO3 extension while preserving the Python-facing API.</div>
<div class="card"><strong>Validate with real tools</strong>Run linting, Rust quality gates, maturin builds, installed-wheel pytest, and fix loops.</div>
<div class="card"><strong>Measure the result</strong>Benchmark isolated Python and Rust wheel installs and produce graph/report artifacts.</div>
</div>

---

# Architecture

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

<div class="callout">
<strong>Safety rule:</strong> the original source project is read-only. Generated tests, code, and measurements go to separate output folders.
</div>

---

# Migration Workflow

<div class="grid-3">
<div class="step"><strong>1. Capture behavior</strong>Analyze the Python project and generate pytest that documents current behavior.</div>
<div class="step"><strong>2. Human review</strong>Reviewer summarizes coverage, risks, and suggested focus before approval.</div>
<div class="step"><strong>3. Scaffold Rust</strong>Create a PyO3/maturin project that preserves the Python import surface.</div>
<div class="step"><strong>4. Translate behavior</strong>Implement Rust behind the same Python-facing API.</div>
<div class="step"><strong>5. Validate wheel</strong>Build with maturin, install the wheel, and run the same pytest suite.</div>
<div class="step"><strong>6. Measure impact</strong>Compare isolated Python and Rust wheels and produce reports and graphs.</div>
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

**The point is not only Rust. The point is trustworthy modernization and measurable improvements.**

---

<!-- _class: section -->

# Beyond Python to Rust

Python to Rust is the first proof point, not the limit.

<div class="grid-3">
<div class="card"><strong>What stays the same</strong>Analyze, test, review, translate, validate, repair, measure.</div>
<div class="card"><strong>What changes</strong>Language prompts, project scaffold, package tools, test runner, and benchmark adapter.</div>
<div class="card"><strong>What this enables</strong>Language-agnostic migration profiles for different modernization goals.</div>
</div>

Examples: MATLAB to Python for cost, Python to Rust for efficiency, JavaScript to TypeScript for maintainability.

---

# Current State

Implemented in the repo today:

<div class="grid-2">
<div class="card"><strong>Workflow</strong>Six-step pipeline: tests, review, PyO3 translation, review, wheel validation, benchmarking.</div>
<div class="card"><strong>Agents</strong>Specialized roles for analysis, testing, review, scaffolding, translation, execution, and measurement.</div>
<div class="card"><strong>Quality gates</strong>flake8, mypy, baseline pytest, cargo fmt, cargo clippy, maturin build, installed-wheel pytest.</div>
<div class="card"><strong>Proof artifacts</strong>Screenshots, benchmark reports, CSV files, metadata, and generated graphs.</div>
</div>

---

<!-- _class: demo -->

# Demo Evidence

## The system runs end-to-end inside the TUI

<span class="pill">Human review</span>
<span class="pill">Agent logs</span>
<span class="pill">Benchmark completion</span>

The next slides show actual demo artifacts from this repo.

---

# Demo: Human Review Gate

<img class="screenshot" src="Screenshot%202026-05-23%20at%2014.29.52.png" alt="TUI screenshot showing Rust source review gate">

<p class="caption">The reviewer summarizes generated Rust/PyO3 source before the user approves or sends feedback.</p>

---

# Demo: Migration Complete

<img class="screenshot" src="Screenshot%202026-05-23%20at%2014.34.20.png" alt="TUI screenshot showing benchmark and migration completion">

<p class="caption">After validation, the benchmarker runs and the migration pipeline completes with report artifacts written to disk.</p>

---

# Demo: Measured Speedup

<img class="graph" src="slop/combined_graphs/speedup_heatmap.png" alt="Heatmap of Rust speedup by project and input size">

<p class="caption">Combined benchmark heatmap across six demo projects. Green means Rust is faster; red means Python is faster.</p>

---

# Demo: Speedup Varies By Workload

<div class="image-grid">
<div>
<img class="graph" src="slop/combined_graphs/speedup_by_project.png" alt="Grouped bar chart of Rust speedup by project and input size">
<p class="caption">Manual sorter shows the biggest win, reaching 94.68x on large inputs and 65.79x on xlarge inputs.</p>
</div>
<div>
<img class="graph" src="slop/combined_graphs/latency_large_tier.png" alt="Large-tier latency comparison across projects">
<p class="caption">Large-tier latency shows where migration clearly helps and where the result is closer to parity.</p>
</div>
</div>

---

# Demo: Resource Evidence

<div class="image-grid">
<div>
<img class="graph" src="slop/combined_graphs/peak_rss_large_tier.png" alt="Large-tier peak memory usage across projects">
<p class="caption">Peak memory comparison keeps the pitch honest: performance wins may come with resource tradeoffs.</p>
</div>
<div>
<img class="graph" src="slop/manual_sorter_measurements/graphs/artifact_sizes.png" alt="Manual sorter artifact size graph">
<p class="caption">Single-project artifact sizes show package tradeoffs alongside runtime improvements.</p>
</div>
</div>

---

<!-- _class: section -->

# Presentation Summary

The pitch in one sentence:

<p class="summary-quote">Modernization should be accessible, trustworthy, and measurable.</p>

<div class="summary-grid">
<div class="summary-card"><strong>Why it matters</strong>Lower cost, less compute, longer software lifetime, safer systems.</div>
<div class="summary-card"><strong>What we built</strong>Agentic migration with tests, review gates, validation, and benchmarks.</div>
<div class="summary-card"><strong>What the demo proves</strong>Python libraries can be translated and made into a wheel that are measurably more efficient and we proved we can translate real world examples.</div>
<div class="summary-card"><strong>Where it goes next</strong>The same workflow can become language-agnostic modernization and apply to even more complex environments</div>
</div>

---

# Ask / Next Steps

Important questions for next steps:

- Which language pairs create the most social impact?
- What evidence makes users trust an AI-assisted migration?
- Which benchmark metrics matter most: latency, cost, energy, memory, or package size?
- How should human review work for non-expert maintainers?

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
