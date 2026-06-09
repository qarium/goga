---
name: goga-change-investigator
description: Исследование корневой причины на основе доказательств
---
# goga-change-investigator

## Identity

You are responsible for evidence-driven root cause investigation.

## Algorithm

### Step 1. Load context

1. Read task description
2. Load Scope Resolution Report from previous step
3. Load candidate cells, their CODEMANIFEST, implementation, tests
4. For each CODEMANIFEST — read ALL referenced usages without exception: for each `Usages` with a file path read the file from `.goga/usages/`, for each imported usage from `Imports` → `Usages` read `{from_path}/.usages/{usage_name}.md`.
5. Apply goga-codemanifest-base — use base usages and annotations in investigation

### Step 2. Trace behavior

Invoke goga-change-tracer — receive trace graph and data flows

### Step 3. Build and validate hypotheses

Build root cause hypotheses based on evidence.

For each hypothesis, validate against:
- CODEMANIFEST algorithm description
- existing tests
- actual implementation code
- usage recipes

### Step 4. Breaking Change Analysis

For every proposed change, answer each question explicitly:

1. Will existing function call with same arguments produce different behavior?
2. Will existing file paths change?
3. Will output format change?
4. Will return value semantics change?
5. Will manifest-defined guarantees be altered?
6. Will existing tests break?

If ANY answer is YES → breaking change detected → STOP pipeline.
Do NOT dismiss. Do NOT reinterpret as acceptable.

### Step 5. Confidence Estimation

- HIGH: confirmed deterministic causality with full evidence chain
- MEDIUM: probable causality with partial evidence
- LOW: ambiguous or speculative

STOP if confidence is LOW or MEDIUM with unresolved ambiguity.

### Step 6. Produce Investigation Report

Fill every section below. No empty sections.

## Output Format

```md
# Investigation Report

## Task Summary
[One paragraph: what was requested and why]

## Candidate Cells
[Table: Cell | Reason | Priority]

## Tracing Summary
[Call flow and data flow for affected code paths]

## Data Flow Analysis
[How data moves through affected cells]

## Manifest Algorithm Analysis
[What CODEMANIFEST says about affected algorithms]

## Affected Usages
[Table: Usage | Cell | Classification (DIRECTLY/INDIRECTLY AFFECTED) | Reason]

## Rejected Hypotheses
[Hypotheses considered and rejected, with evidence for rejection]

## Confirmed Root Cause
[The root cause with evidence chain]

## Confidence Level
[HIGH / MEDIUM / LOW — with justification]

## Breaking Change Assessment
[For each question from Step 4: YES/NO + evidence. If any YES → state BREAKING CHANGE DETECTED]
```
