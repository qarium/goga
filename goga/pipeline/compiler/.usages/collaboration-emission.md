# collaboration-emission — compiling collaboration into the afm flow-file

The document describes how the compiler handles workflow collaboration:
which top-level blocks are emitted, which entries the stages receive, and
which defaults are materialized. The audience is compiler consumers and
workflow-file authors checking the expected output.

## The always-emitted collaboration block

`collaboration: {mode: assistants}` is emitted into EVERY compiled flow —
the one deliberate byte-level difference from a collaboration-free
compilation. `max_depth` rides in the block only when the workflow's
`delegation:` block authors a depth. The block sits between `memory` and
`team`; its key order is `mode, max_depth`.

## The team list

The `team:` list is emitted from the workflow catalog in authored order —
one member per entry — and is omitted entirely when the catalog is empty.
Every member materializes every key:

| Key | Value |
|-----|-------|
| `id` | the authored name — the identity the engine recognizes on resume |
| `title` | the authored name — the dashboard handle derives from it |
| `profile` | `goga-<name>` — the binding to the generated profile |
| `instruction` | the authored prompt; the empty string when none |
| `skills` | the authored list; an empty list when none |

## Stage attachments

A stage of the compiled body emits an `assistants` list when it carries at
least one effective attachment — the canonical slot after `memory_use`.
Loop-expanded copies each carry the original stage's attachments; a
skipped stage attaches nothing. References resolve against the assistant
namespace (the catalog plus every full inline declaration): the
declaration fields come from the named entry, the `gate`/`when` overrides
are the attachment's own. The authoring source is a name-keyed map
(`stages.<name>.assistants` keyed by assistant name) and the compiled
order follows the authored key order. Every entry materializes every key:

| Key | Value |
|-----|-------|
| `profile` | `goga-<name>` |
| `title` | the assistant name |
| `instruction` | the authored prompt; the empty string when none |
| `mode` | `required` when `gate: true`; `advisory` otherwise |
| `trigger` | `one_shot` / `checkpoints` / `on_completion` — mapped from `when` |

`trigger` is always written explicitly — the engine's own
default is `one_shot` and is never relied upon (`when` is authored on every
attachment; there is no compiler-side engagement default). The stage entry carries
NO `skills` key: the afm engine (verified on v2.0.9) strict-parses
`stages[].assistants` and rejects unknown fields
(`unknown field "skills"; use "profile"`). Skills reach the engine ONLY
through a `team` member entry — and the team draws from the catalog
alone, so a CATALOG declaration's skills are delivered while an inline
declaration's authored skills have no channel: the compiler logs a
WARNING naming the stage and the assistant (once per name) instead of
dropping them silently. The catalog is the delivery form for skills.

## Compilation checks

Raised as structural errors naming the workflow location:

- an attachment naming no namespace member — unknown assistant reference
- the same assistant name twice in one stage's effective attachment list
  of a programmatic contribution (an authored attachment map cannot repeat
  a key)
- an attachment on a stage whose translated body carries `script`
- an attachment on a stage whose translated agents value is exactly
  `["planning"]`

The checks run over the working body after skip removal and loop
expansion — the attachments of a removed stage never count. An authored
`assistants` key in a stage body is likewise a structural error: the
single authoring source is the workflow stages block.

## Invariants

- a collaboration-free workflow compiles byte-identically except the
  always-present collaboration mode key
- `PipelineDocument` is the exact mirror of the source pipeline-file —
  the collaboration block, the team list, and the stage attachments are
  output-side only
- the `compile_flow`/`serialize_flow` signatures are unaffected by
  collaboration authoring
- the compiled flow is the single source of truth for the engine
  configuration: every profile id the flow references (`goga-<name>` of
  each member and each attachment) is materialized there exactly — no dead
  profiles remain for attachments removed by stage skips

## Anti-patterns

- Do not author `assistants` in a stage body or an extend-entry — the
  single authoring point is the workflow stages block.
- Do not re-check the authoring vocabulary on the compiler side — the
  workflow parser rejects it before compilation.
- Do not rely on engine defaults for mode/trigger/instruction — every
  entry materializes them.
- Do not add a `skills` key to a stage attachment entry — the engine
  rejects unknown fields there; skills travel on the team member, and
  only catalog entries become team members (an inline declaration's
  skills warn, never emit).
