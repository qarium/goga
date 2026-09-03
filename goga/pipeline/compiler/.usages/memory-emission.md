# memory-emission — compiling memory into the afm flow-file

The document describes how the compiler handles workflow memory: when the
global `memory` block is emitted, which keys the stages receive, and which
defaults are materialized. The audience is compiler consumers and
workflow-file authors checking the expected output.

## The emission condition

The global `memory` block is emitted **if and only if at least one stage
participates in memory**. Participation: a `reflect` instruction under the
reflect method; `memory: true` under the alignment method. The `memory:`
block of a workflow is configuration, not a switch.

| # | `memory:` block | Stage instructions | Block in the output? |
|---|----------------|--------------------|----------------------|
| 1 | absent | absent | no |
| 2 | absent | `reflect` present | yes |
| 3 | present (configuration only) | absent | no — a silent no-op |
| 4 | present, alignment | `memory: true` present | yes |
| 5 | present, alignment | absent (including all `false`) | no — a silent no-op |
| 6 | present, reflect | `reflect` present | yes |

When the block is absent — **nothing** is written on the stages, including
the opting-out key.

## Block content (per method)

The block sits between `description` and `stages`; the key order is `path,
mode, memory_use, max_rules, commit`:

| Key | reflect | alignment |
|-----|---------|-----------|
| `path` | the joined memory root | the joined memory root |
| `mode` | `r` (fixed) | the materialized authored value (`rw` by default) |
| `memory_use` | `false` | `false` |
| `max_rules` | from the configuration | from the configuration |
| `commit` | from the configuration | from the configuration |

The global `memory_use: false` is an opting-out default: participation in
memory is strictly per-stage (afm computes `UseFor(stage) =
stage.memory_use ?? memory.memory_use`, so the global opt-out does not
enable memory on stages without an explicit key). Under reflect a stage
participates through the `reflect` key (`mode: r` gives read-only access to
the project memory); under alignment — through the stage-level
`memory_use: true`.

`path` = `.goga/memory` (no suffix) or `.goga/memory/<suffix>`.

When the `memory:` block is not authored in the workflow (case 2 — only
`reflect` instructions present), the values come from the materialized
defaults: `path` — the bare root `.goga/memory`, `max_rules: 25`,
`commit: false`. The single source of the defaults is the field defaults of
the `WorkflowMemory` model.

## Stage keys

The canonical position is after `script_timeout` (the tail of the known
keys):

- reflect method: a stage with a `reflect` instruction gets the `reflect`
  key — `file` verbatim, `mode` materialized (`rw` when not authored)
- alignment method (with the block emitted): a marked stage —
  `memory_use: true`; **every** unmarked one — an explicit `memory_use: false`
- loop copies carry the same keys as the original; skipped stages never
  reach the application

The goga method selector never reaches the output.

## Invariants

- a workflow without memory participation compiles byte-identically — no
  block, no stage keys
- `PipelineDocument` is the exact mirror of the source pipeline-file: the
  memory block and the memory stage keys are output-side only
- the `compile_flow`/`serialize_flow` signatures are unaffected by memory
  participation

## Anti-patterns

- Do not author `reflect`/`memory_use` in a stage body — a structural
  error; the single source is the workflow instructions
- Do not assume an unset stage key is safe: the inheritance of the global
  default is the reason for the explicit `memory_use: false` on unmarked
  stages
- Do not re-check the authoring vocabulary on the compiler side — the
  workflow parser rejects it before compilation
