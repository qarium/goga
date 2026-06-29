---
name: goga-brainstorm-contracts
description: Designing usages and annotations per cell for the brainstorm pipeline
---
# goga-brainstorm-contracts

## Identity

You are responsible for determining, per cell, which practices (usages), instructions (annotations at all levels), and
consumer usage files.

## Context

Use these skills for every design decision (never improvise annotation or usage decisions from memory):

- **`goga-cell`** — the DSL specification: the exact syntax and semantics of the `Annotations`, `Usages`, `Imports`,
  `Entity`, `Routine`, `Mutation`, and `Embedding` directives — what may appear in a CODEMANIFEST and how it is written.
- **`goga-cookbook`** — the principles of **applying** that DSL: the annotation levels (global / type-level /
  member-level), the **annotation writing standard** (good-practice elements — description, `Algorithm:`,
  `Requirements:`, `Constraints:` — applied by the **sufficiency criterion**, not a fixed structure), that
  annotations must not duplicate each other or carry implementation details, that a connected practice applies only via
  an annotation, and the rules for writing `<cell_path>/.usages/` files. Use it to decide how to phrase annotations,
  where each instruction belongs, and how to write consumer usage files.
- **`goga-codemanifest-base`** — the project's base usages and annotations (from `.goga/config.yml`) that every
  CODEMANIFEST must include and comply with.
- **`goga-lang-disp`** — naming and signature conventions for the target language (routes to the per-language skill).

Use these reports for its specific purpose:

- **`[CELL_DISTRIBUTION_REPORT]`** — use it for the **distribution of types across cells**, the **inter-cell Imports
  connections**, and which cells are **modified vs created anew** — the structure to attach contracts to (drives the
  usages-inline sub-skill).
- **`[TYPE_DETAIL_REPORT]`** — use it for each type's **responsibility**, **methods/properties/signatures**, and *
  *interactions** — the factual basis the sub-skills use for annotations and consumer usage examples.

## Workflow

Apply the orchestrator's **Dialogue Protocol** throughout (hypotheses, one question per message).

### Phase 1. Design contracts per cell in Loop

Process cells **strictly one at a time**, in dependency order (leaves → root — cells without dependencies first). The
loop is gated: **after designing each cell you MUST STOP, show the result, and wait for the user's verdict.** You are
forbidden to begin, sketch, or pre-compute the next cell before the current one is approved.

#### Loop:

1. **Usages (header)** — invoke **`goga-brainstorm-contracts-usages-inline`**, giving it `[CELL_DISTRIBUTION_REPORT]`
   (inter-cell Imports) and `[TYPE_DETAIL_REPORT]` (what the types use). It returns the connected
   base/cross-cell/external usages and the set of **Usages keys** (backtick targets) for this cell.
2. **Annotations** — invoke **`goga-brainstorm-contracts-annotations`**, giving it `[TYPE_DETAIL_REPORT]`
   (responsibility, methods/properties/signatures) and the usages-inline result (connected Usages keys). It returns the
   global/type-level/member-level annotations.
3. **Cell usage files** — invoke **`goga-brainstorm-contracts-usages-file`**, giving it `[TYPE_DETAIL_REPORT]` (the
   cell's contract) and the usages-inline and annotations results. It returns paths: `<cell_path>/.usages/<domain>.md`
   and Full usage-files content
4. **STOP and show the result** — once step 3 returns, **halt the loop immediately.** Present this
   result to the user — the cell path, the usages, the annotations (global / type-level / member-level), and the usage
   files in full — exactly as they will be assembled into the `[CONTRACTS_REPORT]`. Then **STOP**: end your turn and
   wait for the user's explicit verdict (see WAIT). Do not advance to the next cell, and do not move on to Phase 2,
   until the user approves this cell.

If a change in the current cell affects an already-approved cell — return to the affected cell and propose adjustments.

### Phase 2. Assemble the report

Aggregate the per-cell artifacts (usages cell-level keys, annotations, usage files, base compliance, external gaps)
into the `[CONTRACTS_REPORT]`. Fill every section — an empty section means incomplete output.

## WAIT

Present per-cell usages, annotations (by level), and usage files to the user and obtain approval per cell.

- **Approved** → advance to the next cell.
- **Not approved** → re-invoke the affected sub-skill(s) for this cell with the feedback and propose corrected
  artifacts.

## Output Format

Fill every section. No empty sections. The report must carry its full content here.

```md
# [CONTRACTS_REPORT]

## Per-Cell Contracts
[For each cell (leaves to root):]

### Cell: <path>

#### Usages
- Base usages: [all from `goga-codemanifest-base`]
- Cross-cell `Imports.Usages`: [provider cell → practice]
- External usages: [practice key → file in `.goga/usages/` or `.goga/usages/cooks/`]

#### Annotations
- Global: [base annotations from `goga-codemanifest-base` + cell-wide naming / constraints / architecture]
- Type-level: [per Entity/Routine: signature → Description (with `param` lines) → `Algorithm:` → `Requirements:` → `Constraints:`]                                                             
- Member-level: [per method/property: signature, input/output, side effects, algorithm, requirements]      

#### Cell usage files
**File:** `<cell_path>/.usages/<domain>.md`
**Content:**
```md
<full file content — verbatim, exactly as returned by the sub-skill; ready to assemble>
```                                                                                                                                                                                             

## Base Compliance
[Table: Cell | Base usages included | Base annotations included | Contract complies?]

## External Usage Gaps
[Libraries/patterns needing a usage file to be created (separate skill); or "None"]
```

## STOP if:
- canonical usage pattern would be violated by the design
- approval denied after iteration
