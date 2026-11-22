# collaboration-emission — compiling collaboration into the afm flow-file

The document describes how the compiler handles collaboration from both
authoring surfaces — the workflow-file (catalog, delegation, stage
entries) and the pipeline-file stage-body declarations — which top-level
blocks are emitted, which entries the stages receive, and which defaults
are materialized. The audience is compiler consumers and authors of
either surface checking the expected output.

## The always-emitted collaboration block

`collaboration: {mode: assistants}` is emitted into EVERY compiled flow —
the one deliberate byte-level difference from a collaboration-free
compilation. `max_depth` rides in the block only when the workflow's
`delegation:` block authors a depth. The block sits between `memory` and
`team`; its key order is `mode, max_depth`.

## The team list

The `team:` list is emitted from TWO sources in a fixed order — the
workflow catalog in authored order first (one member per entry), then
the pipeline-declared members in pipeline body stage order (each stage's
declarations in authored order; loop-expanded copies collapse to their
base stage's first occurrence; vetoed and stage-skipped declarations
never join; a name joins exactly once). The list is omitted entirely
when both sources are empty. Every member materializes every key:

| Key | Value |
|-----|-------|
| `id` | the authored name — the identity the engine recognizes on resume |
| `title` | the authored name — the dashboard handle derives from it |
| `profile` | `goga-<name>` — the binding to the generated profile |
| `instruction` | the effective prompt; the empty string when none |
| `skills` | the effective list; an empty list when none |

## Stage attachments

A stage of the compiled body emits an `assistants` list when it carries
at least one effective attachment — the canonical slot after
`memory_use`. Loop-expanded copies each carry the original stage's
attachments; a skipped stage attaches nothing. Within one stage's
compiled list, the pipeline declarations come first (pipeline authored
order), then the workflow entries (workflow authored order) — the same
pipeline-first rule as the prompt append and the skills expansion.

Every entry materializes every key:

| Key | Value |
|-----|-------|
| `profile` | `goga-<name>` |
| `title` | the assistant name |
| `instruction` | the effective prompt; the empty string when none |
| `mode` | `required` when the effective `gate` is true; `advisory` otherwise |
| `trigger` | `one_shot` / `checkpoints` / `on_completion` / `pre_completion` / `on_message` — mapped from the effective `when` (a gated `finish` maps to `pre_completion`) |

`trigger` is always written explicitly — the engine's own default is
`one_shot` and is never relied upon (a pipeline declaration authors
`when` on every entry; a workflow reference or inline declaration
carries its own). The stage entry carries NO `skills` key: the afm
engine strict-parses `stages[].assistants` and rejects unknown fields
(`unknown field "skills"; use "profile"`). Skills reach the engine ONLY
through a `team` member entry — and the team draws from the catalog and
the pipeline declarations, so a declaration from either source delivers
its skills while a workflow inline declaration's authored skills have no
channel: the compiler logs a WARNING naming the stage and the assistant
(once per name) instead of dropping them silently.

## Origin-aware resolution

The effective assistant namespace spans the workflow catalog, every full
inline declaration, and the pipeline declarations of the compiled body —
one global uniqueness domain; a name collision between any two sources
(including a tool-delivered contribution through the overlay) is a
structural error naming both authoring sites.

A workflow entry addressing a name declared by its own stage's
pipeline-file body resolves by origin:

- `{skip: true}` — the veto: no attachment, no team member, no generated
  profile for that name; the stage itself still runs.
- any other entry — the extension: `when`/`gate` override the pipeline
  values (omitted keys inherit; an explicit `gate: false` deliberately
  downgrades), `agent`/`env`/`delegate` configure delivery, `prompt`
  appends to the pipeline text (pipeline text first, one blank line,
  then the workflow text), `skills` expands the pipeline list (pipeline
  entries first, then workflow entries, deduplicated by value).

An entry naming no pipeline declaration of that stage keeps the existing
semantics — a catalog reference or a full inline declaration — and
requires its own `when`; a when-less entry is legal only as an extension
of a pipeline declaration of the same stage. A pipeline declaration is
visible only to its own stage's entry: addressing it from another stage
is an unknown-assistant-reference error.

## Compilation checks

Raised as structural errors naming the location:

- a name collision across the effective namespace (catalog, inline,
  pipeline declarations, overlay contributions)
- an attachment naming no namespace member — unknown assistant reference
  (including a pipeline-declared name addressed from another stage)
- a missing `when` on an entry naming no pipeline declaration of the
  stage (a reference or a full inline declaration)
- the same assistant name twice in one stage's effective attachment list
  of a programmatic contribution
- an attachment from any source on a stage whose translated body carries
  `script`
- an attachment from any source on a stage whose translated agents value
  is exactly `["planning"]`
- a workflow declaration (catalog or inline) resolving no effective
  prompt and no effective skills

The checks run over the working body after skip removal and loop
expansion — the attachments of a removed stage never count — with or
without a workflow document (pipeline declarations attach on every run).

## Invariants

- a collaboration-free compilation (no pipeline declarations, no
  workflow collaboration authoring) compiles byte-identically except the
  always-present collaboration mode key
- `PipelineDocument` is the exact mirror of the source pipeline-file —
  the collaboration block, the team list, and the stage attachments are
  output-side only; the workflow extension never mutates the parsed
  representation
- the `compile_flow`/`serialize_flow` signatures are unaffected by
  collaboration authoring
- the compiled flow is the single source of truth for the engine
  configuration: every profile id the flow references (`goga-<name>` of
  each member and each attachment) is materialized there exactly — no
  dead profiles remain for attachments removed by a veto or a stage skip

## Anti-patterns

- Do not author delivery keys in a pipeline declaration — `agent`, `env`,
  `delegate` belong to the workflow-file entry addressing the name.
- Do not expect a workflow-only attachment to inherit engagement — a
  reference or inline declaration carries its own `when`; only a
  pipeline declaration's extension may omit it.
- Do not re-check the authoring vocabulary on the compiler side — the
  parsers rejected non-conforming authoring before compilation.
- Do not rely on engine defaults for mode/trigger/instruction — every
  entry materializes them.
- Do not add a `skills` key to a stage attachment entry — the engine
  rejects unknown fields there; skills travel on the team member (catalog
  and pipeline declarations only; an inline declaration's skills warn,
  never emit).
