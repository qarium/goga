---
name: goga-brainstorm-context
description: Project context exploration for the brainstorm pipeline
---
# goga-brainstorm-context

## Identity

You are responsible for gathering facts about the current state of the project.

## Context

Use this report for its specific purpose:

- **`[INTAKE_REPORT]`** — use it for the **topic**, the user's **description**, and any **names/terms** it mentions; these drive the matching against the project schema (Read relevant CODEMANIFESTs) and the choice of usages to read (Read relevant usages).

## Workflow

### Phase 1. Get the project schema

Run `goga schema --help` first to understand the command's capabilities, then run `goga schema` to obtain the complete cell hierarchy. To understand what a cell is, use skill `goga-cell`.

If the project has no existing architecture — record this as a fact and proceed.

### Phase 2. Record base usages and annotations

Use skill `goga-codemanifest-base` — record base usages and annotations for all CODEMANIFESTs in the plan.

### Phase 3. Read relevant CODEMANIFESTs

Based on the schema and the `[INTAKE_REPORT]`, read the CODEMANIFESTs of cells possibly related to the topic. Match the user's description to the schema:

- Names matching cell paths or types **may be** existing artifacts — verify by reading CODEMANIFEST, present as hypothesis
- Names without matches **may be** new artifacts to create
- If the description has no specific names — identify affected cells by meaning
- If names are ambiguous (multiple matches) — flag for hypothesis-based clarification
- Use `--depends-on <cell_path>` to search dependent cells when necessary

### Phase 4. Read relevant usages

Read usages of files related to the cells from Phase 3, following the rules of skill `goga-cookbook`.

If the task implies external libraries or technologies — read usages about them in `.goga/usages/cooks/`.

This provides a catalog of available practices, libraries, and tools that the new architecture can reference.

Adapt depth:

- Related to the topic → read fully
- Indirectly related → read annotations and key sections
- No existing CODEMANIFESTs → skip

### Phase 5. Record description-to-schema matches

Record description-to-schema matches as hypotheses. Do NOT resolve them here — they are resolved in the next phase (the `[PRIMARY_ANALYSIS_REPORT]`, Phase 3 of the pipeline), which folds them into its Artifact Resolution section.

## Output Format

Fill every section. No empty sections.

```md
# [PROJECT_CONTEXT_REPORT]

## Cell Hierarchy
[Output of `goga schema`, or "no existing architecture" as a fact]

## Base Usages & Annotations
[From goga-codemanifest-base]

## Relevant Existing Cells
[Table: Cell | CODEMANIFEST location | Relevance to the task]

## Relevant Usages
[Table: Usage file | Cell | Relevance; include external-library usages in .goga/usages/cooks/]

## Description-to-Schema Matches
[Table: Name/term from description | Schema match? | Hypothesis (existing artifact to modify / new artifact to create / ambiguous)]
```

## STOP if:
- `goga schema` is unavailable
- a referenced cell path cannot be resolved
