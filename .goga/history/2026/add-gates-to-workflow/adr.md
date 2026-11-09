# Quality gates: workflow `gates` authoring compiled to the engine stage `verify`

goga gains quality gates for workflow stages by exposing, in its own vocabulary, the
stage-completion gate the AFM engine already provides — the flow-file `verify` field
(shell check steps, AI-review steps, a bounded correction budget, stalemate
acceptance). goga authors `gates` in the workflow-file only (a top-level settings
block plus a per-stage check-step list), strictly validates the authoring structure
pre-run, and compiles it one-directionally into the engine vocabulary; every
execution semantic (step ordering, fail-fast, full-list re-runs, retry budgets,
verdict parsing, human waiver) stays with the engine. The flow-file is the single
delivery channel — goga writes no engine config for gates.

## Decision map

1. **Single authoring surface: the workflow-file.** Steps are authored as
   `workflow.stages.<name>.gates` (a list of check steps); retry tuning as the
   top-level `gates:` block (`patience`, `max_iterations`, `fresh_correction`).
   The vocabulary translates one-directionally to the engine's: `script`→`run`,
   `agent`→`command`, `patience`→`review_patience`, `max_iterations`→`max_failures`,
   `fresh_correction` unchanged, `timeout`/`prompt`/`name` pass through (the
   `communication`→`interactive`, `notes`→`buttons` precedent). A `gates` key in an
   extend-entry and a `gates` key in a pipeline-file stage body are strict errors
   (the `notes`/`assistants`/`reflect`/`memory` pattern: a new stage's checks are
   authored in the stages block by its name). An empty block or list equals
   absence; a workflow consisting of the settings block alone is valid content
   under the empty-workflow rule.

2. **An AI step's command composes exactly like the per-stage agent override** —
   the authored `agent` name goes into the in-container wrapper path
   `/home/goga/bin/<agent>-as-claude.sh`, composed directly by the compiler with no
   host-side wrapper resolution (the engine resolves a verify `command` through the
   same mechanism as `stage.command`, so the per-stage override composition is the
   known-good shape). No extra agent-name existence checks.

3. **Settings ride only on gated stages.** When the top-level block authors any
   key, every gated stage's `verify` is the container form (`steps:` plus the
   authored settings under the engine vocabulary — authored keys only, goga
   materializes no settings defaults); ungated stages and the engine config layers
   are untouched, so the settings block without steps is inert (the `memory`
   shape). With no settings block, a gated stage carries the steps alone (the
   engine list form; engine-default settings apply).

4. **Timeout defaults: `1h` materialized for shell steps only.** A shell step
   without an authored `timeout` carries the materialized `1h`; an AI step
   materializes no default (authored values pass verbatim). This is a goga-side
   product default, not an engine contract.

5. **A raw `verify` key in a stage body (pipeline-file stage or extend-stage body)
   is a strict compile error** — `verify key is forbidden in stage body; use gates
   in workflow.stages`. Today unknown stage-body keys pass through to the compiled
   flow verbatim, so a raw `verify` written in a pipeline-file currently reaches
   the engine unvalidated; that passthrough is an accident of the unknown-key
   rule, not a documented channel, and it would bypass the entire strict gates
   validation (including container settings). The compiled-only keys
   (`buttons`, `reflect`, `memory_use`, `auto_run`, `assistants`) are all
   forbidden in bodies for the same reason; `verify` joins them. Rejected:
   tolerating the passthrough (the `script_timeout` stance) — that stance is
   reserved for keys that mirror a pipeline-body authoring translation, and
   `verify` has none.

6. **`name` is required on every gate step** (narrowing the PRD, decided in
   discovery): its absence is a strict parser error
   (`gates step without name in workflow.stages.NAME[i]`), and every compiled
   step therefore carries a dashboard label — the engine's fallback numbering
   ("Verify step 1 · make test") is never relied upon for goga-authored gates.

7. **Validation boundary: structure is goga's, value grammar is the engine's.**
   goga strictly checks types, unknown keys, step-form mutual exclusion
   (`script` xor `agent`), forbidden locations, and `name` presence. The grammar
   of *values* passes verbatim and is reported by the engine at flow load/preflight:
   a malformed `timeout` duration (the established `script_timeout` precedent) and
   an empty or whitespace-only `name` (the engine parses `name` as a string with
   at least one non-space character).

8. **Validation splits across the two layers** (the `assistants`/`repeat`
   pattern). Structural checks live in the workflow parser, which sees only the
   workflow text: settings-block keys/types, step forms and unknown step keys,
   `script`/`agent` exclusivity, missing `name`, `gates` in an extend-entry.
   Cross-reference checks live in the compiler, which sees both documents and
   runs them over the working body after skip removal: the existing
   unknown-stage-name error, gates on a stage compiling to a script stage (its
   body carries `script`), gates on a planning-only stage (translated agents
   exactly `["planning"]`), and the forbidden `gates`/`verify` keys in stage
   bodies. Consequences: gates on a skipped stage drop silently (never reaching
   the cross-reference checks), and the checks run once on the original — every
   loop-expanded copy carries the same gate without revalidation.

9. **Canonical emission order.** In the FlowStage key order, `verify` sits after
   `assistants` (the tail of the known keys — a gate runs after execution, so it
   follows the execution instructions): `…, script_timeout, reflect, memory_use,
   assistants, verify`. Inside the emitted block: `steps`, then settings in the
   engine-documented order `max_failures, review_patience, fresh_correction`.
   Inside a step: `name`, then `run`|`command`, then `timeout`, `prompt`.

10. **No goga-side engine-interplay validation.** goga performs no cross-field
    checks of engine constraints (e.g. the engine's `max_failures >=
    review_patience` requirement for stalemate engagement, or the effective
    ceiling `min(max_failures, 15)`); the engine owns and reports these. goga
    likewise never interprets, counts, or re-implements gate execution.

11. **Lifecycle invariants.** A gate-free workflow compiles byte-identically to
    the same workflow before the feature (no `verify` key anywhere, no other key
    affected); the pipeline-file and the parsed pipeline representation are never
    modified by gates authoring; the workflow amendment overlay merge preserves
    gates instructions (the overlay preserves the full workflow model); gates
    combine with the other per-stage instructions (`approve`, `manual`, `notes`,
    `assistants`, `reflect`, …) as independent channels.

## Engine assumptions to verify during implementation

- The engine's verify contract accepts the container form with exactly `steps`
  plus the three settings keys (`max_failures`, `review_patience`,
  `fresh_correction`) and rejects step fields at the container top level; a
  step-level `timeout` is valid on both shell and AI steps; `prompt` is valid on
  AI steps only (a goga shell step never carries `prompt`).
- A wrapper-path value (`/home/goga/bin/<agent>-as-claude.sh`) works as an AI
  step's `command` — the engine resolves it through the same mechanism as the
  per-stage `command:` override.
- The engine forbids `verify` on script stages and planning-only stages, which is
  why goga surfaces both pre-run with its own messages.
- The feature assumes an engine version whose verify contract matches the
  published documentation; older engines reject a gated flow at load/preflight
  (the documented downgrade behavior — not silent).

## Out of scope (recorded, not silently assumed)

- Cell/CODEMANIFEST architecture — the next stage's work, not part of this
  decision.
- Any change to the AFM engine or its verify semantics, dashboards, or verdict
  protocols; delivering gates through engine config files; authoring gates in
  pipeline-file stage bodies or extend-entries; any goga-side execution of
  checks, verdict parsing, retry logic, or run-state UI; changes to existing
  instructions; gates in the shipped reference pipelines.
- Documentation updates ride with the task: the user-facing section lands in
  `docs/features/pipelines/workflows.md`, and the engine verify fact base is
  added to `.goga/usages/cooks/afm.md` alongside this ADR (the assistants ADR
  precedent).
