# Repeating pipeline cycles and map-form assistants authoring

## Current State

- goga compiles the pipeline DSL plus the project workflow-file into an afm
  flow-file. afm v2.0.9 already implements the repeating-run mechanics: a
  top-level flow-file `repeat` directive (scalar `true` or a map with
  `max_cycles` and `keep_runs`), `flow_repeated` events, stop on a failed
  cycle, and run-directory pruning — verified against the installed binary.
  goga authors and compiles none of it today: the pipeline header carries only
  `name`/`description`/`roles`; the workflow-file carries
  `prompt`/`stages`/`extend`/`memory`/`profile`/`build`/`assistants`/`delegation`;
  the compiled flow-file top-level key order is `prompt, root_dir, name,
  description, memory, collaboration, team, stages`.
- Assistants are authored as a list of mappings in both the top-level catalog
  and stage attachments; a stage attachment may also be a bare string; `when`
  defaults to a materialized `checkpoints`. The single authored consumer of the
  form is `.goga/workflows/refinement.yml` (list form). The cell usage
  `goga/pipeline/workflow/.usages/assistants.md` documents the list form.
- The workflow-file and the pipeline-file are parsed independently; only the
  compiler sees both documents at once.

## Description

Two authoring-surface changes that ride the existing compile path, decided in
`.goga/history/2026/recycle-pipeline/adr.md` (the ADR decision map is
normative for this task):

1. **Repeating run cycle.** The pipeline DSL gains a capability flag
   `repeatable: true` (pipeline header, next to `name`/`description`). The
   workflow-file gains a tuning block `repeat` that accepts only the map form
   with optional `max_cycles` and `keep_runs` keys — afm's vocabulary, verbatim
   (goga materializes no defaults); an empty block equals absence; scalar forms
   in the workflow are rejected; structure is validated at parse time
   (non-mapping block, unknown key, non-int value, negative value). One
   compilation rule, no exceptions: a repeatable pipeline always compiles with
   a `repeat` key — the workflow block emits the authored keys only, while a
   missing block, a missing workflow, or `--no-workflow` compiles the scalar
   `repeat: true`. A workflow `repeat` block on a non-repeatable pipeline is a
   compile-time structural error (the cross-reference check lives in the
   compiler — the workflow parser never sees the pipeline). The compiled
   `repeat` is emitted immediately after `description`, before `memory` (new
   top-level order: `prompt, root_dir, name, description, repeat, memory,
   collaboration, team, stages`). `run_pipeline` stays a single `afm run`
   invocation; afm owns all cycle semantics.

2. **Map-form assistants.** The assistants catalog and the stage attachments
   become name-keyed maps: the assistant name moves into the map key; an inner
   `name` key is an unknown key (error); `gate`/`when` stay forbidden in the
   catalog. A stage attachment takes a map value only — a reference (value
   keys within `gate`/`when`) or a full inline declaration (any further key),
   discriminated exactly as before; the bare-string form has no map rendering
   and disappears. `when` is required in every stage attachment
   (`start`/`checkpoints`/`finish`): the materialized `checkpoints` default is
   removed from authoring and a missing `when` is a structural error. `gate`
   remains optional (default `false`). The compiled flow-file output is
   unchanged — the engine's list-form `stages[].assistants` and `team`
   contracts stay as they are, with `trigger` still written explicitly on
   every entry.

The transition is hard, not dual-accepting: the list form is rejected with an
error naming the map form (project precedent: `agents` → `roles` in the
header).

## Scope

**In scope:**

- Pipeline DSL: the `repeatable` header flag — parsing and structural
  validation.
- Workflow-file: the `repeat` block — map-form-only parsing with structural
  validation (unknown keys, non-int or negative values, non-mapping block,
  scalar forms).
- Compiler: the always-emit rule for repeatable pipelines (workflow block
  emits authored keys only; defaults compile to the scalar `repeat: true`),
  the non-repeatable + workflow-`repeat` cross-check error, and the emission
  position immediately after `description`, before `memory`.
- Workflow-document rebuilders: the parsed `repeat` field survives both
  in-memory rebuilds losslessly — `apply_skip_stages` (the `--skip` path)
  carries it verbatim, and the hooks workflow overlay carries it with an
  authored-wins rule for the block (like memory/delegation).
- Workflow-file: name-keyed map assistants (catalog and stage attachments),
  required `when` on every stage attachment, removal of the list and
  bare-string forms with a hard-transition error naming the map form.
- Tests for the parser and compiler: new authoring forms, every new structural
  error, compilation outputs (block form, scalar form, cross-check failure),
  reference-vs-declaration discrimination, and unchanged engine-facing output
  for equivalent authoring.
- Update of the cell usage `goga/pipeline/workflow/.usages/assistants.md` to
  the map-form authoring (catalog, attachments, required `when`, the complete
  structural-error list).

**Out of scope:**

- Adding `repeatable` to any existing pipeline YAML — the six shipped assets
  and the project pipelines stay untouched; adopting repeat is a deliberate
  per-pipeline decision for later.
- Converting `.goga/workflows/refinement.yml` to the map form (user decision,
  recorded twice): the file remains in the list form and will be rejected by
  the workflow parser after this change until a separate conversion.
- Profiles (`language`, `stages`) carrying repeat; `goga pipeline card` /
  `describe_pipeline` surfacing repeat (a card change can be its own decision
  later).
- Any goga-side cycle awareness beyond compilation — history statuses, run
  coordination, hooks events, and memory are unchanged (the hooks overlay and
  the skip merge only carry the new workflow-level `repeat` field through
  their rebuilds); afm owns the cycle.
- `run_pipeline` stays a single `afm run` call — no run-mechanics changes.

## Acceptance Criteria

- A repeatable pipeline with a workflow `repeat` block compiles with `repeat`
  carrying exactly the authored keys (no materialized defaults).
- A repeatable pipeline without a workflow `repeat` block — including a
  missing workflow file and `--no-workflow` — compiles the scalar
  `repeat: true`.
- A non-repeatable pipeline with a workflow `repeat` block fails compilation
  with a structural error naming the conflict.
- Scalar `repeat` forms in the workflow-file are rejected at parse time with
  readable errors.
- Map-form catalog entries and stage attachments parse; an inner `name` key, a
  missing `when` on a stage attachment, and any list-form or bare-string
  assistants authoring are rejected with errors naming the map form.
- The compiled assistants output for map-form authoring equals the current
  engine list-form output for the equivalent old authoring (reference and
  declaration forms both).
- The cell usage `goga/pipeline/workflow/.usages/assistants.md` documents the
  map-form authoring (catalog, stage attachments, the required `when`) and the
  complete structural-error list, with no list-form examples left.
- The compiled flow-file emits `repeat` (when compiled) immediately after
  `description` and before `memory`.
- A repeatable pipeline with a workflow `repeat` block compiled through the
  skip path (`-s/--skip`) and through a hooks workflow overlay still carries
  the authored repeat keys.
- Compiled outputs for existing non-repeatable pipelines without assistants
  authoring are byte-identical to the current outputs.
- `pytest tests/ -x` and `ruff check goga/` pass.

## Stack

- **Frameworks:** none new — Python 3.10+ project on the existing stack.
- **Libraries:** existing PyYAML, Jinja2, and click usage (workflow rendering
  and CLI surfaces unchanged); no new third-party dependencies.
- **Infrastructure:** none.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| afm v2.0.9 | `.goga/usages/cooks/afm.md` | updated (the `repeat` section added at task formulation) |
| YAML handling | `.goga/usages/cooks/beautiful_yaml.md` | existing |
| Jinja2 rendering | `.goga/usages/cooks/jinja2.md` | existing |
| click CLI | `.goga/usages/cooks/click.md` | existing |
| Project conventions | `.goga/usages/conventions.md` | existing (mandatory) |

Synced usage files are managed by `goga usages sync` — reference them
read-only, never create or update them in the task.

## Risks and Constraints

- `.goga/workflows/refinement.yml` stays in the list form by decision: after
  this change its parse is rejected, so the refinement pipeline breaks on its
  next run until a separate conversion task lands — a known, accepted
  consequence, recorded here rather than silently assumed.
- Hard transition: any out-of-repo consumer of the list form breaks at parse
  with the new error; nothing has shipped in a release, so there is no
  compatibility surface to keep.
- afm strict-parses its flow-file `repeat` (a negative value and an unknown
  key are engine errors too) — goga's structural validation must be at least
  as strict so failures surface at authoring time, not at engine startup.
- The workflow parser and the pipeline parser never see each other's
  documents — the repeat/repeatable cross-check can live only in the compiler
  (same two-layer pattern as stage-name and attachment validation).
- Empty-map convention: an authored `repeat: {}` equals absence.
- afm owns cycle semantics (unlimited default cycles, `keep_runs: 2` default,
  stop-on-failed-cycle, pruning) — goga never duplicates or second-guesses
  them.

## Scope Estimate

Single task, no decomposition (user decision): both changes ride one compile
path and share one hard transition and one release; the two rebuilder touches
(the skip merge, the hooks overlay) are mechanical field-carries of the same
parsed `repeat` value, not separate concerns. No additional topics created.

## Existing Architecture

- `goga/pipeline/workflow` — the pure parser of workflow-files into declarative
  `WorkflowDocument` instructions; owns the assistants catalog, the delegation
  block, stage attachments, and the profile zone. Impacted by the `repeat`
  block parsing and the map-form assistants.
- `goga/pipeline/compiler` — parses the pipeline DSL (`PipelineHeader` today)
  and compiles/serializes the `FlowDocument`; owns structural errors and the
  cross-document checks. Impacted by `repeatable`, the repeat compilation rule,
  the cross-check, and the new emission position.
- `goga/pipeline` (run coordination) — `apply_skip_stages` rebuilds
  `WorkflowDocument` field by field; it must carry the new `repeat` field
  verbatim (a dropped field would silently compile an authored
  `repeat: {max_cycles: N}` as the scalar `repeat: true` on every `--skip`
  run). No other routine of the cell changes.
- `goga/pipeline/hooks` — `merge_workflow_overlay` rebuilds the effective
  workflow document; the `repeat` block needs an authored-wins merge rule
  (like memory/delegation), verbatim carry through the rebuild, and a
  decision whether `repeat` counts in the empty-contribution rule. No hooks
  event vocabulary or cycle-awareness changes.
- Consumers (`describe_pipeline`, `pipeline_card`, `run_pipeline`,
  `describe_pipelines`) read parsed/compiled models and are unchanged.

## Notes

- ADR: `.goga/history/2026/recycle-pipeline/adr.md` — the decision map
  (8 numbered decisions) is normative.
- The `repeat` section in `.goga/usages/cooks/afm.md` was added during task
  formulation (user-approved); implementation keeps it consistent with the
  final behavior.
- afm facts verified against the v2.0.9 binary via `afm validate`: the scalar
  and map forms validate; a negative `max_cycles` and an unknown block key are
  rejected by the engine.
- Formulation dialog record: questions q1–q6 in the stage dialog files
  (scope adjustments: refinement.yml conversion excluded — q2, reaffirmed q6;
  single task — q5; usage update done at formulation — q4).
