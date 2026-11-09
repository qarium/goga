# Quality gates for workflow stages (`gates`)

## Current State

goga authors run customization in workflow-files (`.goga/workflows/*.yml`): the
`goga/pipeline/workflow` cell parses them into `WorkflowDocument` instructions and
the `goga/pipeline/compiler` cell compiles pipelines into afm flow-files, applying
the workflow instructions (per-stage overrides, extend-stages, memory, repeat,
collaboration) along the way.

None of this reaches the engine's stage-completion gate mechanism (the flow-file
`verify` field — shell check steps, AI-review steps, a bounded correction budget,
stalemate acceptance; documented at https://akopichin.github.io/afm/verify/):

- the workflow-file grammar has no `gates:` settings block and no per-stage
  `gates:` instruction — both are unknown keys, strict parser errors today;
- the compiler never emits `verify` into a flow-file;
- worse, a raw `verify` key authored in a pipeline-file stage body passes through
  to the compiled flow verbatim (an accident of the unknown-key passthrough rule)
  — it would bypass every structural check goga applies to its own vocabulary.

As a result, a stage in a goga run completes on the agent's word alone: enforcing
quality (tests pass, an independent agent reviews the result) requires manual
verification after the run, and the engine's correction-loop capability — the
mechanism that returns failed work to the stage agent for fixing — stays
unreachable. Confirmed as a platform feature of goga, not a one-off configuration
of a single workflow.

## Description

Deliver stage-completion quality gates, authored in the goga workflow vocabulary
and compiled one-directionally into the engine's `verify` field, exactly per the
ADR in this topic directory (the decision source; the PRD is the requirements
source). Every execution semantic — step ordering, fail-fast, full-list re-runs
after a correction, retry budgets, verdict parsing, human waiver — stays with the
engine; goga's product behavior is author, validate, compile.

1. **Authoring (workflow-file only).** An optional top-level `gates:` settings
   block with the optional keys `patience` (integer >= 0), `max_iterations`
   (integer >= 0), `fresh_correction` (bool); a boolean is not an integer for
   these checks. An optional per-stage `gates:` instruction in
   `workflow.stages.<name>` — a list of check steps; each step is a mapping
   carrying a REQUIRED `name` (the dashboard label; a missing `name` is a strict
   parser error — a deliberate narrowing of the PRD decided in discovery) and
   EXACTLY ONE of `script` (non-empty string — a shell check step) or `agent`
   (non-empty string — an AI-review step, the same agent-name vocabulary as the
   per-stage agent override); `timeout` (string) and `prompt` (string) are
   optional (`prompt` belongs to AI steps in the engine contract; goga's check is
   form-level — `script` xor `agent` — while value grammar stays engine-owned).
   A `gates` key in an extend-entry is a strict structural error (the
   notes/assistants pattern: a new stage's checks are authored in the stages
   block by its name). Empty block or empty list equals absence; the settings
   block counts as workflow content for the empty-workflow rule (a workflow
   consisting of the block alone is valid).
2. **Compilation (flow-file).** A stage with check steps compiles a stage-level
   `verify` gate: steps in authored order, each shell step carrying `run` (from
   `script`) and each AI step carrying `command` composed from the authored agent
   name into the in-container wrapper path `/home/goga/bin/<agent>-as-claude.sh`
   — composed directly by the compiler, no host-side resolution, no agent-name
   existence checks (the per-stage agent override composition is the known-good
   shape). `name`, `prompt`, and authored `timeout` values pass verbatim. Timeout
   default: a shell step without an authored `timeout` carries the materialized
   `1h`; an AI step materializes no default (a goga-side product default, not an
   engine contract). When the top-level settings block authors ANY key, every
   gated stage's `verify` takes the container form (a `steps` list plus the
   authored settings under the engine vocabulary — `patience` →
   `review_patience`, `max_iterations` → `max_failures`, `fresh_correction`
   unchanged; authored keys only, goga materializes no settings defaults); with
   no settings block authored, a gated stage carries the steps alone (the engine
   list form; engine-default settings apply). The settings block without
   per-stage steps is inert (the memory shape): ungated stages, the engine config
   layers, and the engine environment defaults are never touched. Gates ride
   uniformly on every loop-expanded copy; a skipped stage's gates drop silently
   (skip removal runs first).
3. **Validation boundary and split.** Structure is goga's, value grammar is the
   engine's: malformed `timeout` durations and whitespace-only `name` values pass
   verbatim and are reported by the engine at flow load/preflight (the
   `script_timeout` precedent). Structural checks live in the workflow parser
   (settings-block keys and types, step forms, unknown step keys, the
   `script`/`agent` exclusivity, missing `name`, `gates` in an extend-entry).
   Cross-reference checks live in the compiler, over the working body after skip
   removal: the existing unknown-stage-name error; gates on a stage compiling to
   a script stage (its body carries `script`); gates on a planning-only stage
   (translated agents exactly `["planning"]`); and the forbidden authoring keys —
   a `gates` key and a raw `verify` key in a stage body (pipeline-file stage or
   embedded extend-stage body) are strict compile errors directing the author to
   `workflow.stages` (closing today's accidental `verify` passthrough; `verify`
   joins `buttons`/`reflect`/`memory_use`/`auto_run`/`assistants` as
   compiled-only keys). Loop copies are never revalidated — the checks run once
   on the original.
4. **Canonical emission order.** In the FlowStage key order, `verify` sits after
   `assistants` (a gate runs after execution, so it follows the execution
   instructions). Inside the emitted block: `steps`, then settings in the
   engine-documented order `max_failures`, `review_patience`,
   `fresh_correction`. Inside a step: `name`, then `run`/`command`, then
   `timeout`, `prompt`.
5. **Lifecycle invariants.** A gate-free workflow compiles byte-identically to
   the same workflow before the feature (no `verify` key anywhere, no other key
   affected). The pipeline-file and the parsed pipeline representation
   (`PipelineDocument`) are never modified by gates authoring. Gates survive the
   workflow amendment overlay merge (the overlay preserves the full workflow
   model) and the CLI skip-driven rebuild (`apply_skip_stages`) — the new
   top-level block and the new stage field must be carried explicitly by both
   rebuilds, which enumerate document fields by name. Gates combine with the
   other per-stage instructions (`approve`, `manual`, `notes`, `assistants`,
   `reflect`, …) as independent channels.
6. **No engine-interplay validation.** goga performs no cross-field checks of
   engine constraints (the engine's `max_failures >= review_patience` stalemate
   requirement, the effective ceiling `min(max_failures, 15)`) and never
   interprets, counts, or re-implements gate execution. The flow-file is the
   single delivery channel — goga writes no engine config for gates.
7. **Documentation and fact base (ride with the task).** A user-facing "Quality
   gates (`gates`)" section lands in `docs/features/pipelines/workflows.md`
   (authoring vocabulary, engine-vocabulary mapping, the timeout default,
   combination and exclusion rules, a worked example that compiles as
   documented). The engine verify fact base is added to
   `.goga/usages/cooks/afm.md` (the assistants ADR precedent): both engine
   authoring forms, the step fields, the container settings, engine-owned
   interpretation, the script/planning-only exclusions, strict JSON verdicts,
   the stalemate/ceiling rules, and the engine-version assumption.

## Scope

**In scope:**

- Workflow DSL authoring: the top-level `gates` settings block and the per-stage
  `gates` check-step list, with full strict structural validation and one-line
  readable errors naming the workflow location.
- Compilation to the engine `verify` gate: step translation (`script` → `run`,
  `agent` → `command` wrapper composition), the `1h` shell-step timeout default,
  verbatim carriage of `name`/`prompt`/authored `timeout`, settings translation
  for gated stages (authored keys only), the container and list emission forms,
  the canonical key order, uniform application across loop copies and skip
  removal.
- Product rules: script-stage and planning-only exclusions surfaced pre-run with
  goga's own messages; `gates` forbidden in extend-entries; `gates`/`verify`
  forbidden in stage bodies; the inert settings block; byte-identical gate-free
  output.
- Overlay merge preservation of gates instructions (the settings block and the
  per-stage field) and the skip-rebuild carry.
- User-facing documentation and the afm fact-base update.
- Unit tests per project conventions (structure mirroring, edge cases,
  parametrized boundaries) across the parser, the compiler, the overlay merge,
  and the skip merge; the full test suite and lint pass.

**Out of scope:**

- Any change to the AFM engine or its verify semantics, dashboards, or verdict
  protocols.
- Delivering gates settings through the engine config files — the flow-file is
  the only delivery channel.
- Authoring gates in pipeline-file stage bodies or in extend-entries.
- Any goga-side execution of checks, verdict parsing, retry logic, or run-state
  UI.
- Changes to existing instructions (`script`/`timeout`, `assistants`, `memory`,
  `repeat`, `approve`, `manual`, `notes`) or their semantics.
- Adding gates to the shipped reference pipelines — projects opt in via their
  own workflow-files.
- Validation of the timeout duration grammar and of engine interplay constraints
  (engine-owned).
- Cell/CODEMANIFEST architecture design — the next stage's work; this task names
  affected cells but does not design their contracts.

## Acceptance Criteria

- The PRD's worked authoring example (settings block, a shell step, an AI-review
  step) loads, validates, and compiles: the gated stage carries a `verify` gate
  with the steps in authored order — the shell step with its command and the
  materialized `1h` (or authored) timeout, the AI step with the command composed
  from the authored agent name plus its prompt and label.
- With the settings block authored, every gated stage's `verify` carries the
  authored settings under the engine vocabulary; without it, gated stages carry
  the steps alone. The settings block alone compiles inert — no `verify` key
  anywhere, no error.
- Every compiled step carries a `name` (required at authoring); the engine's
  fallback step numbering is never relied upon.
- Each invalid authoring case is rejected before the run with a one-line strict
  error naming the workflow location: unknown keys in the settings block or a
  step; wrong value types; a step carrying both or neither `script` and `agent`;
  a missing step `name`; `gates` in an extend-entry; `gates` or a raw `verify`
  in a stage body; gates on a script stage or a planning-only stage; gates on an
  unknown stage name.
- Gates on a skipped stage drop silently; every loop-expanded copy carries the
  same `verify` gate; a workflow amended through the overlay keeps its gates; a
  skip-driven run keeps the settings block for its remaining gated stages.
- A gate-free workflow compiles byte-identically to the same workflow before the
  change; the pipeline-file and `PipelineDocument` are untouched.
- An empty top-level `gates:` block and an empty per-stage `gates:` list equal
  absence — the workflow compiles byte-identically to the same workflow without
  them.
- The workflow documentation contains the gates section and its worked example
  compiles as documented; `.goga/usages/cooks/afm.md` gains the verify fact
  base.
- A malformed `timeout` value is NOT a goga error — it passes verbatim
  (engine-reported at preflight), matching the `script_timeout` precedent.
- The full test suite and lint pass.

## Stack

- **Frameworks:** none new — Click CLI surface unchanged (no new commands or
  flags).
- **Libraries:** Python 3.10+ standard library (`dataclasses` with
  `kw_only=True` for the new models); pyyaml (existing) for workflow parsing and
  flow serialization; pytest + ruff as test/lint tooling.
- **Infrastructure:** none — the task lives entirely inside the repository plus
  the contract of the external engine binary.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| afm (external engine, verify contract) | `.goga/usages/cooks/afm.md` | updated (verify fact base added in-task, per the ADR) |
| YAML serialization convention | `.goga/usages/cooks/beautiful_yaml.md` | existing (reference) |
| jinja2 (workflow rendering — untouched by gates) | `.goga/usages/cooks/jinja2.md` | existing (reference) |

Synced usage files are managed by `goga usages sync` — reference them read-only,
never create or update them in the task.

## Risks and Constraints

- **Engine assumptions to verify during implementation** (recorded in the ADR;
  update the afm cook in-task if contradicted): the container form accepts
  exactly `steps` plus the three settings keys and rejects step fields at the
  container top level; a step-level `timeout` is valid on both shell and AI
  steps and `prompt` on AI steps only; a wrapper-path `command` resolves through
  the same mechanism as the per-stage `command` override; the engine forbids
  `verify` on script and planning-only stages (hence goga's own pre-run
  messages); an engine version matching the published verify documentation is
  assumed — older engines reject a gated flow at load/preflight (the documented
  downgrade behavior, not silent).
- **Backward compatibility:** serialization changes must preserve byte-level
  output for gate-free workflows — no `verify` key anywhere, no other key
  affected.
- **Cell discipline:** the workflow parser cell stays dependency-free; the
  compiler imports only from `goga/pipeline/workflow` — no imports back into
  `goga/pipeline` or `goga/pipeline/hooks` (no cycles); the forced design order
  is workflow → compiler → hooks → pipeline.
- **Rebuild enumeration:** `merge_workflow_overlay` (the hooks cell) and
  `apply_skip_stages` (the pipeline cell) enumerate
  `WorkflowDocument`/`WorkflowStage` fields by name — the new fields MUST be
  carried there, or overlay-amended and skip-driven runs silently lose gates.
- **Strict grammar:** the engine does not reject unknown stage keys in a flow
  (unknown fields pass through silently), so goga's own validation is the only
  guard against silent typos in the workflow-file; the verify structures
  themselves are engine-strict (misplaced step fields at the container top
  level are a parse error), which is a load-time backstop, never a substitute.
- **Validation boundary:** value grammar (durations, name text) is engine-owned
  — goga must not grow a duration parser or a name-content check beyond
  structural presence and type.

## Scope Estimate

Single task — no decomposition. One vertical feature through the
`workflow → compiler → hooks → pipeline` chain (~4 affected cells, ~3 new
models, moderate complexity, all design decisions pre-settled by the ADR; the
`support-afm-assistants` precedent); candidate split points would not deliver
independent value (parsing without emission silently drops authoring; emission
without validation leaks authoring mistakes to the engine). No additional topics
created.

## Existing Architecture

Affected cells and integration requirements (contract design belongs to the next
stage):

- `goga/pipeline/workflow` — leaf cell (no dependencies): owns
  `WorkflowDocument`, `WorkflowStage`, `parse_workflow`. Gains the gates
  settings-block and check-step models, the `gates` fields on the document and
  stage models, and the structural validation (including `gates` forbidden in
  extend-entries and the empty-workflow rule). Must remain dependency-free.
- `goga/pipeline/compiler` — depends only on `goga/pipeline/workflow`: owns
  `FlowDocument`, `FlowStage`, `compile_flow`, `serialize_flow`. Gains the
  emitted verify model(s), the `verify` slot in the FlowStage canonical key
  order (after `assistants`), the step/settings translation with the `1h` shell
  default and the wrapper-path command composition, the serialization, and the
  cross-reference checks (script stage, planning-only, unknown stage, forbidden
  `gates`/`verify` body keys) over the working body after skip removal.
- `goga/pipeline/hooks` — owns `merge_workflow_overlay` and the amendment view.
  Gains the explicit carriage of the gates settings block (authored-wins, the
  delegation/repeat pattern) and the new stage field in the per-stage merge; the
  empty-contribution rule of `WorkflowAmendment.contribute` counts the new
  block.
- `goga/pipeline` — owns the run coordination and `apply_skip_stages`. Gains the
  verbatim carry of the gates settings block through the skip-driven rebuild.
- `goga/afm` — untouched (subprocess launch only).
- `WorkflowDocument` has type-level consumers beyond the compiler (hooks,
  pipeline, build, commands) — all must keep compiling unchanged; the CLI-facing
  surface does not change.

## Notes

- Input artifacts: `adr.md` (decision source) and `prd.md` (requirements source)
  in this topic directory.
- Stage constraints honored: no code examples in this task (the code-example
  step of the formulation interview was deliberately skipped — the PRD carries
  the authoring-form example); no architecture design — cells/CODEMANIFEST
  contracts are the next stage's work.
- Fixed decisions (settled in the ADR, do not revisit): `name` required on
  every gate step (a deliberate narrowing of the PRD); a raw `verify` key in a
  stage body is a strict error (closing the accidental passthrough); settings
  ride only on gated stages, authored keys only; the `1h` timeout default is
  materialized for shell steps only; the two-layer validation split (parser =
  structure, compiler = cross-references after skip removal); the canonical
  emission order; validation of value grammar stays with the engine.
