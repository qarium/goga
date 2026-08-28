---
name: goga-brainstorm-primary-analysis
description: Primary analysis of concepts, dark zones, and risks for the brainstorm pipeline
---

# goga-brainstorm-primary-analysis

## Identity

You are responsible for the first analytic pass of the brainstorm cycle and for producing the **canonical context
snapshot**. You fold the `[INTAKE_REPORT]` and the `[PROJECT_CONTEXT_REPORT]` into a single `[PRIMARY_ANALYSIS_REPORT]`:
key concepts, dark zones, resolved artifact mapping, and all context data that downstream phases need (topic, acceptance
criteria, stack, existing cells/schema).

## Context

Use these reports for its specific purpose:

- **`[INTAKE_REPORT]`** — use it for the **request and its boundaries**, the **acceptance criteria**, the **stack**, and
  the **Description Type** (which sets the expected analysis depth); this phase folds them into the canonical context
  snapshot carried by the `[PRIMARY_ANALYSIS_REPORT]`.
- **`[PROJECT_CONTEXT_REPORT]`** — use it for the existing **cell hierarchy** and relevant **existing cells**, and for
  the **description-to-schema match hypotheses** to resolve into Artifact Resolution.

## Workflow

Apply the orchestrator's **Dialogue Protocol** throughout (hypotheses, one question per message, structured responses,
ASCII diagrams).

### Phase 1. Determine the analysis dimensions

From the description and gathered facts, determine. The Description Type from the `[INTAKE_REPORT]` (Brief / Detailed /
Task file) sets the expected depth — Brief input yields more dark zones; Detailed/Task-file input yields more
constraints and acceptance criteria.

- **Topic** — a short topic name derived from the `[INTAKE_REPORT]` task summary (used by plan-assembly for
  the `arch.md` path printed by `goga history path -f arch.md`)
- **Acceptance criteria** — if task-file input, folded verbatim/condensed from the `[INTAKE_REPORT]` "Acceptance
  Criteria" section; otherwise N/A
- **Stack & external dependencies** — if task-file input, folded from the `[INTAKE_REPORT]` "Stack and Dependencies"
  section; otherwise the detected/inferred stack; or N/A
- **Existing cells & schema** — the cell hierarchy and the relevant existing cells, folded from the
  `[PROJECT_CONTEXT_REPORT]` (or "no existing architecture")
- **Artifact resolution** — resolve every description-to-schema match hypothesis from the `[PROJECT_CONTEXT_REPORT]`
  into `modify <existing cell>` / `create new <artifact>` / `new artifact`, through the Dialogue Protocol (hypothesis →
  one question → confirmation). Ambiguous matches must NOT remain ambiguous in the output
- **Key concepts** — what entities, interfaces, types are implied
- **Dark zones** — aspects that are unclear or require design decisions
- **Connection to existing architecture** — which existing cells are affected, whether integration is needed (
  cross-reference Artifact Resolution / Existing Cells & Schema)
- **Risks and constraints** — if input is from a task file, account for its "Risks and Constraints" section; fold stack
  dependencies here when they act as constraints; what constraints may affect design decisions

### Phase 2. Check scope

If the description covers several independent subsystems — propose splitting into subsystems and brainstorming one at a
time.

### Phase 3. Present the analysis

Present the primary analysis to the user and obtain approval (see WAIT).

## WAIT

Present the `[PRIMARY_ANALYSIS_REPORT]` to the user and obtain approval before proceeding.

- **Approved** → proceed to the next phase
- **Not approved** → incorporate feedback, re-analyze, present again

## Output Format

Fill every section. No empty sections.

```md
# [PRIMARY_ANALYSIS_REPORT]

## Topic
[Short topic name derived from the [INTAKE_REPORT] task summary.

## Acceptance Criteria
[If task-file input: verbatim/condensed list from the [INTAKE_REPORT] "Acceptance Criteria" section. Otherwise: N/A.
Canonical source for the cell-assembly acceptance check.]

## Stack & External Dependencies
[If task-file input: from the [INTAKE_REPORT] "Stack and Dependencies" section. Otherwise: detected/inferred stack; or
N/A. Used by contracts/type-detail to account for technologies.]

## Existing Cells & Schema
[Cell hierarchy from the [PROJECT_CONTEXT_REPORT] (or "no existing architecture") + relevant existing cells table (
Cell | CODEMANIFEST location | Relevance). Canonical source for cell-distribution extend-vs-create decisions and
plan-assembly project structure.]

## Artifact Resolution
[Table: Name/term from the description | Resolution: modify <existing cell> / create new <artifact> / new artifact |
Justification. Resolves the [PROJECT_CONTEXT_REPORT] description-to-schema matches using goga-cell + goga-cookbook.
Ambiguous cases resolved through the Dialogue Protocol before this section is finalized. If there are no name-level
matches: "No name-level matches; resolution deferred to cell-distribution by responsibility zone" (not empty). Canonical
source for cell-distribution modify-vs-create and plan-assembly modified-vs-created marking.]

## Key Concepts
[List of entities, interfaces, types implied by the description]

## Dark Zones
[Aspects that are unclear or require design decisions]

## Connection to Existing Architecture
[Which existing cells are affected; whether integration is needed. Cross-reference Artifact Resolution / Existing Cells & Schema.]

## Risks and Constraints
[From the task file "Risks and Constraints" section, if present, plus detected constraints. Include stack dependencies that act as constraints.]

## Scope Decision
[Single subsystem → proceed; multiple subsystems → recommendation to split and which one to brainstorm first]

## Notes
[Any additional observations]
```

## STOP if:
- approval denied after iteration
- scope split unresolved
