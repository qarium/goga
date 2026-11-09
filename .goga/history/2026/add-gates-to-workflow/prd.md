# Quality Gates for Workflow Stages (`gates`)

## Problem

Engineers who configure goga pipeline runs through project workflow-files
(`<project>/.goga/workflows/<name>.yml`) cannot declare automated
stage-completion quality checks. The AFM engine that executes goga-compiled
flows already provides a stage-completion gate — the `verify` field with shell
check steps, AI-review steps, and bounded correction retries (documented at
https://akopichin.github.io/afm/verify/) — but the goga workflow DSL has no
way to author it: a `gates` key is rejected as an unknown key by the
workflow parser, and the compiler never emits `verify` into the flow-file.

As a result, a stage in a goga run completes on the agent's word alone.
Enforcing quality (tests pass, an independent agent reviews the result)
requires manual verification after the run or bespoke per-project review
stages, and the engine's correction-loop capability — the mechanism that
returns failed work to the stage agent for fixing — stays unreachable.
This was confirmed as a platform feature of goga (not a one-off
configuration of a single workflow).

## Users

- **Workflow author (primary)** — the project engineer who writes
  `.goga/workflows/*.yml` to layer project behavior onto compiled pipelines.
  They want quality checks to be a declared, versioned part of the project
  methodology that every run enforces automatically, instead of a manual
  habit. They know the existing workflow DSL vocabulary and expect the same
  strict, readable validation style.
- **Run overseer (secondary)** — the human watching a goga run (typically in
  the AFM dashboard) while gates execute. They see gate progress and
  outcomes, and may waive a failed required AI verdict. This interaction is
  owned entirely by the engine; goga must deliver authored gates faithfully
  and must not obstruct it.

## Goals

1. **Declarative stage checks.** A workflow author can declare, at project
   level and for any pipeline, which checks a stage must pass before it
   counts as done — shell commands and/or AI-review agents — so quality
   enforcement becomes part of the reusable workflow rather than manual
   verification.
2. **Trusted completion.** A stage with declared checks is considered
   complete only when the checks pass; a failed check sends the work back to
   the stage agent for correction within a bounded retry budget, instead of
   passing silently.
3. **Tunable quality/iteration balance.** The retry behavior — failure
   budget, tolerance for an unchanged stalemate, and the correction-session
   mode — is configured declaratively in the same workflow-file, with
   project settings overriding the engine environment defaults.

## User Experience

### Entry point

The workflow author edits `.goga/workflows/<name>.yml` and adds an optional
top-level `gates:` settings block and/or a per-stage `gates:` instruction,
then runs the pipeline with that workflow as usual. No other artifact
changes: gates are authored in the workflow-file only.

### Authoring form

```yaml
gates:                        # optional workflow-level settings block
  patience: 1                 # engine: review_patience
  max_iterations: 5           # engine: max_failures
  fresh_correction: false     # engine: fresh_correction

stages:
  implement:
    prompt: |
      Example prompt
    gates:                    # optional per-stage list of check steps
      - name: Unit tests      # optional dashboard label
        script: pytest ./     # shell check step
        timeout: 30m          # optional; 1h materialized when omitted
      - name: Code review
        agent: codex          # AI-review step (agent vocabulary identical
                              # to the per-stage agent override)
        prompt: |             # optional review instruction
          Example review prompt
```

goga authors its own vocabulary and translates it to the engine's
(`script` → `run`, `agent` → `command`, `patience` → `review_patience`,
`max_iterations` → `max_failures`, `fresh_correction` keeps its name,
`timeout`/`prompt`/`name` pass through) — the established pattern of the
workflow DSL (as `communication` → `interactive`, `notes` → `buttons`).

### Primary scenario

1. The author saves the workflow and starts the pipeline run.
2. goga loads and strictly validates the workflow; authoring mistakes stop
   the run before it starts with a one-line structural error naming the
   location (e.g. `unknown key in workflow.gates: KEY`).
3. The run proceeds; when a gated stage's agent finishes its work, the check
   steps run in authored order.
4. All checks pass → the stage completes and the run continues.
5. A check fails → the stage agent is sent back to correct its work
   (correction session semantics per `fresh_correction`); after a fix the
   whole check list re-runs from the beginning; the loop is bounded by the
   effective retry settings; when the budget is exhausted the stage fails.
   Progress, outputs, and the failing check are visible to the overseer in
   the engine dashboard; a human may waive a failed required AI verdict.

All execution semantics in step 4–5 belong to the engine. goga's product
behavior is: author, validate, compile — never interpret or duplicate the
runtime semantics.

### Alternative scenarios

- **No gates anywhere** — the workflow compiles exactly as before the
  feature; the compiled flow carries no gate field anywhere.
- **Settings block without any per-stage checks** — valid authoring, but
  inert: settings travel only with stages that declare check steps, so
  nothing is emitted and no error is raised (same shape as the `memory`
  block, which emits nothing without participation).
- **Check steps without the settings block** — checks run under the engine
  environment defaults for retry behavior.
- **Gates on a stage also carrying other workflow instructions**
  (`approve`, `manual`, `notes`, `assistants`, `reflect`, …) — instructions
  are independent channels and combine without interference.
- **Gates on a skipped stage** — the stage is removed and its checks drop
  silently (skip removal runs first, as for `assistants`).
- **Gates on a loop-expanded stage** — every copy carries the same checks.
- **Gates naming an extend-stage** — allowed: the stages-block `gates`
  instruction applies to new stages added via `extend` by their name.

### Failure scenarios (validation, all pre-run)

- Unknown key in the settings block or a step entry, wrong value types,
  a step carrying both `script` and `agent`, or neither — strict structural
  error naming the workflow location.
- `gates` in an `extend` entry, or a `gates` key authored in a
  pipeline-file stage body — strict structural error (single authoring
  surface: the workflow-file stages block).
- Gates on a stage name that exists in neither the pipeline nor the
  extend-stages — the existing strict "unknown stage name" error.
- Gates on a stage that compiles to a pure script stage (its body carries
  `script`) — strict error naming the stage: the engine rejects gates on
  script stages, and goga surfaces this pre-run with its own message.
- Gates on a planning-only stage (translated agents exactly
  `["planning"]`) — strict error naming the stage, same reasoning.
- A malformed `timeout` duration is **not** a goga error: the value passes
  through verbatim and the engine reports it at preflight/run time (the
  established `timeout`/`script_timeout` precedent).

## Requirements

### Authoring (workflow-file DSL)

1. Accept an optional top-level `gates:` mapping with the optional keys
   `patience` (integer ≥ 0), `max_iterations` (integer ≥ 0),
   `fresh_correction` (bool). Any other key, a non-mapping block, or a value
   of the wrong type is a strict structural error naming the location. An
   empty block equals absence.
2. Accept an optional per-stage `gates:` instruction in
   `workflow.stages.<name>`: a list of check steps. Each step is a mapping
   with either:
   - `script` (non-empty string, required) — a shell check step, plus
     optional `timeout` (string), optional `name` (string label); or
   - `agent` (non-empty string, required) — an AI-review step, plus
     optional `prompt` (string), optional `timeout` (string), optional
     `name` (string label).

   `script` and `agent` are mutually exclusive and exactly one is required
   per step. Non-list `gates`, non-mapping step values, unknown step keys,
   and non-string values are strict structural errors naming the stage and
   location. An empty list equals absence.
3. A `gates` key in an extend-entry is a strict structural error
   ("`gates` is forbidden in workflow.extend.NAME") — checks of a new stage
   are authored in the stages block by its name (the `notes`/`assistants`
   pattern).
4. An authoring `gates` key in a pipeline-file stage body (including an
   embedded extend-stage body) is a strict structural error directing the
   author to `workflow.stages` (the `buttons`/`assistants` pattern).
5. The gates blocks count as workflow content for the empty-workflow rule:
   a workflow consisting of the gates settings block alone is valid.

### Compilation (observable in the compiled flow-file)

6. A stage with check steps compiles a stage-level verify gate: the steps in
   authored order, each shell step carrying its command and each AI step
   carrying the command composed from the authored agent name — the same
   agent-name vocabulary and composition as the per-stage `agent` override —
   with `prompt`, `name`, and authored `timeout` values carried verbatim.
7. Timeout defaults: a shell step without an authored `timeout` carries the
   materialized default `1h`. AI steps materialize no default timeout
   (authored values pass verbatim).
8. When the workflow-level gates settings block authors any key, every
   gated stage's verify gate carries the authored settings under the engine
   vocabulary (`patience` → `review_patience`, `max_iterations` →
   `max_failures`, `fresh_correction` unchanged), authored keys only — goga
   materializes no settings defaults; the engine defaults and the engine
   config layer stay in effect for unauthored keys and ungated stages.
   With no settings block authored, gated stages carry the steps alone
   (engine default settings apply).
9. Gates apply uniformly to every loop-expanded copy of the stage; a
   skipped stage emits nothing.
10. A workflow without gates compiles byte-identically to the same workflow
    before the feature — no gate field anywhere, no other key affected.
11. Gates live in the workflow-file only: the pipeline-file and the parsed
    pipeline representation are never modified by gates authoring.
12. Gates instructions survive the workflow amendment overlay merge — an
    amended workflow keeps its gates (the overlay preserves the full
    workflow model).

### Product rules (cross-instruction)

13. Gates on an unknown stage name produce the existing strict
    "unknown stage name" error (gates add no special-casing).
14. Gates on a stage compiling to a script stage, or on a planning-only
    stage, are strict pre-run errors naming the stage (the engine rejects
    both; goga surfaces them with its own messages).
15. goga performs **no** cross-field validation of engine interplay
    constraints (e.g. the engine's requirement that the failure budget be
    at least the patience value) — the engine owns and reports these.
16. goga never interprets, counts, or re-implements gate execution:
    sequencing, fail-fast, full-list re-runs after a correction, retry
    budgets, stalemate acceptance, verdict parsing, and waiver are engine
    behavior.

### Documentation

17. The user-facing workflow documentation gains a "Quality gates
    (`gates`)" section covering the authoring vocabulary, the
    engine-vocabulary mapping, the timeout default, the combination and
    exclusion rules, and a worked example equivalent to the one above.

## Constraints

1. **Engine contract boundary.** goga may only author what the AFM engine's
   verify contract accepts: the documented step fields (`run`/`command`,
   `name`, `prompt`, `timeout`), the step list and container forms, and the
   container settings (`max_failures`, `review_patience`,
   `fresh_correction`) — no step fields beside settings at the container
   level. goga cannot extend the engine vocabulary.
2. **Engine restrictions.** The engine forbids gates on script stages and
   planning-only stages; AI check agents must return strict JSON verdicts;
   text-only recipes and cursor verifiers are rejected at engine preflight;
   check agents do not inherit the author's skills.
3. **Engine-owned semantics.** Execution behavior (ordering, retries,
   stalemate handling, resume counter reset, human waiver) belongs to the
   engine and must not be duplicated or reinterpreted by goga.
4. **Workflow DSL conventions.** Strict structural validation with
   one-line readable errors naming the location; the goga authoring
   vocabulary is translated one-directionally to the engine vocabulary;
   workflow-only instructions are forbidden as authoring keys in pipeline
   stage bodies and extend-entries; instructions apply after skip removal
   and uniformly across loop copies; feature-free workflows compile
   byte-identically; the whole workflow-file (gates included) is rendered
   as a template with the active profile before parsing.
5. **Flow-file is the single delivery source.** Gates travel in the compiled
   flow-file only; goga writes no engine config for gates (the established
   collaboration stance).
6. **Engine version.** The feature assumes an engine version whose verify
   contract matches the published documentation; on older engines a gated
   flow is rejected by the engine at load/preflight.

## Scope

### In Scope

- Workflow DSL authoring: the top-level `gates` settings block and the
  per-stage `gates` check-step list, with strict structural validation.
- Compilation to the engine verify gate: step translation, agent-name
  composition, the 1h shell-step timeout default, settings translation for
  gated stages, uniform application across loop copies and skip removal.
- Product rules: script-stage/planning-only exclusions, extend-entry and
  stage-body prohibitions, unknown-stage strictness, inert settings block,
  byte-identical gate-free output.
- Overlay merge preservation of gates instructions in the workflow
  amendment path.
- User-facing documentation of the feature in the workflow documentation.

### Out of Scope

- Any change to the AFM engine or its verify semantics, dashboards, or
  verdict protocols.
- Delivering gates settings through the engine config files (`.afm/config.yaml`)
  — the flow-file is the only delivery channel.
- Authoring gates in pipeline-file stage bodies or in extend-entries.
- Any goga-side execution of checks, verdict parsing, retry logic, or
  run-state UI.
- Changes to existing instructions (`script`/`timeout`, `assistants`,
  `memory`, `repeat`, `approve`, `manual`, `notes`) or their semantics.
- Adding gates to the shipped reference pipelines — projects opt in via
  their own workflow-files.
- Validation of the timeout duration grammar and of engine interplay
  constraints (engine-owned).

## Success Criteria

1. A workflow-file authored like the example above loads, validates, and
   compiles; the compiled flow carries, on the gated stage, a verify gate
   with the steps in authored order: the shell step with its command and
   the materialized `1h` timeout (or the authored one), and the AI step
   with the command composed from the authored agent name and its prompt
   and label.
2. With the settings block authored, every gated stage's verify gate
   carries the authored settings under the engine vocabulary; without it,
   gated stages carry the steps alone.
3. A gate-free workflow compiles byte-identically to the same workflow
   before the change.
4. Each invalid authoring case from the failure scenarios is rejected
   before the run with a one-line strict error naming the workflow
   location: unknown keys, wrong types, both/neither `script` and `agent`,
   gates in an extend-entry, gates in a stage body, gates on a script or
   planning-only stage, gates on an unknown stage name.
5. Gates on a skipped stage drop silently; every loop-expanded copy carries
   the same verify gate.
6. A workflow amended through the overlay keeps its gates instructions.
7. The workflow documentation contains the gates section, and its worked
   example compiles as documented.
8. In a real run of a gated stage, the stage does not complete until its
   checks pass, and a failing shell check sends the stage agent into the
   engine's correction loop bounded by the authored settings.
