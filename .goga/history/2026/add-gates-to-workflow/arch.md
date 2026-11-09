# Architecture Plan: Quality gates for workflow stages (`gates` → engine `verify`)

## Topic

Quality gates for workflow stages — workflow-DSL `gates` authoring compiled
one-directionally into the engine's stage `verify` field.

- Plan path: `.goga/history/2026/add-gates-to-workflow/arch.md`
- Decision source: `adr.md` (same directory); requirements source: `task.md` + `prd.md`
- All behavioral decisions are pre-settled by the ADR; this plan designs contracts only
  (CODEMANIFEST + `.usages/`), no implementation code.

## Implementation Order

1. **`goga/pipeline/workflow`** (MODIFIED) — leaf cell, no Imports; provides the new
   authoring models (`WorkflowGates`, `WorkflowGateStep`) and the structural validation
   that every downstream consumer relies on. Designed first because its exports define
   the downstream Imports.
2. **`goga/pipeline/compiler`** (MODIFIED) — depends only on
   `goga/pipeline/workflow`; imports the two new types and the `gates` practice; owns
   the verify emission models and the cross-reference checks.
3. **`goga/pipeline/hooks`** (MODIFIED) — depends on `goga/pipeline/workflow`
   (`WorkflowDocument`); carries the gates values opaquely through the overlay merge;
   no new imports.
4. **`goga/pipeline`** (MODIFIED) — depends on `goga/pipeline/workflow`
   (`WorkflowDocument`); carries the gates settings block verbatim through the
   skip-driven rebuild; no new imports.

## Artifacts

---

### Cell 1: `goga/pipeline/workflow` (MODIFIED)

#### CODEMANIFEST diff

**Header — `Annotations`:** append the following paragraph to the existing block:

```yaml
gates is a declarative quality-gate instruction set — an optional top-level
settings block (patience, max_iterations, fresh_correction) plus an optional
per-stage check-step list in the stages block. This cell validates both
surfaces structurally (key sets, types, value bounds, step forms, the
script/agent exclusivity, the required step name) and extracts them into the
document model. The top-level block carries authored values only — an empty
block equals absence, and a workflow consisting of the block alone is valid.
A per-stage value is a list of check steps — an empty list equals absence;
every step carries a required name and exactly one of script (a shell check)
and agent (an AI review). A gates key in an extend-entry is a structural
error — the checks of a new stage are authored in the stages block by the
new stage's name. Value grammar is not validated here: timeout durations and
name text pass verbatim, and their format errors are surfaced downstream.
This cell performs NO gate logic — it composes no commands, materializes no
settings defaults, and decides no emission form; the consumers consume the
extracted values. The import graph stays one-directional.
```

**Body — ADD new type:**

```yaml
"WorkflowGates(patience: int | None = None, max_iterations: int | None = None, fresh_correction: bool | None = None)":
  location: workflow_gates.py
  annotations: |
    Data model of the workflow quality-gate settings — the authored retry
    tuning for stage completion checks. Constructed by `parse_workflow`;
    carried inside `WorkflowDocument`.

    `patience`: the authored tolerance for an unchanged correction
                stalemate, or None when not authored
    `max_iterations`: the authored bound of failed correction attempts, or
                      None when not authored
    `fresh_correction`: whether a correction session starts fresh, or None
                        when not authored

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - All fields default to None — the model carries authored values only
      and materializes no defaults; an authored zero is a value, not an
      omission, and stays distinguishable from None
    - Field order is fixed: patience, max_iterations, fresh_correction

    Constraints:
    - Do not validate types or bounds here — `parse_workflow` enforces
      them during parsing
    - Do not translate the field names into the engine vocabulary here —
      the consumer performs the translation
    - Do not interpret the settings — retry semantics belong to the
      consumer and the engine
  properties:
    "patience -> int | None": |
      The authored tolerance for an unchanged correction stalemate, or
      None when not authored.
    "max_iterations -> int | None": |
      The authored bound of failed correction attempts, or None when not
      authored.
    "fresh_correction -> bool | None": |
      Whether a correction session starts fresh; None when not authored.
```

**Body — ADD new type:**

```yaml
"WorkflowGateStep(name: str, script: str | None = None, agent: str | None = None, timeout: str | None = None, prompt: str | None = None)":
  location: workflow_gate_step.py
  annotations: |
    Data model of one authored check step — a single stage-completion
    check, shell or AI-review. Constructed by `parse_workflow`; carried
    inside `WorkflowStage`.

    `name`: the check's dashboard label — required on every step
    `script`: the shell command of a shell check step, or None
    `agent`: the agent name of an AI-review step, or None — the same name
             vocabulary as the per-stage agent override
    `timeout`: the authored timeout value, carried verbatim, or None when
               not authored
    `prompt`: the review instruction of an AI step, carried verbatim, or
              None when not authored

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - `name` is required (no default); every other field defaults to None
    - Exactly one of `script`/`agent` is not None on every constructed
      instance — `parse_workflow` enforces the exclusivity before
      construction
    - Field order is fixed: name, script, agent, timeout, prompt

    Constraints:
    - Do not validate the step form here — `parse_workflow` enforces it
      during parsing
    - Do not compose `agent` into a launch command here — the consumer
      composes it
    - Do not validate the `timeout` duration grammar or the `name` text
      here — values pass verbatim; value-format errors belong to the
      engine
  properties:
    "name -> str": |
      The check's dashboard label; required on every authored step.
    "script -> str | None": |
      The shell command of a shell check step, or None.
    "agent -> str | None": |
      The agent name of an AI-review step, or None.
    "timeout -> str | None": |
      The authored timeout value, carried verbatim, or None when not
      authored.
    "prompt -> str | None": |
      The review instruction of an AI step, carried verbatim, or None
      when not authored.
```

**Body — MODIFY `WorkflowStage`:**

- Signature: append the last parameter —
  `"WorkflowStage(agent: str | None = None, env: dict[str, str] | None = None, prompt: str | None = None, loop: int | None = None, skills: list[str] | None = None, skip: bool = False, approve: str | None = None, manual: bool | None = None, notes: dict[str, str] | None = None, reflect: WorkflowReflect | None = None, memory: bool | None = None, assistants: dict[str, WorkflowAssistant] | None = None, gates: list[WorkflowGateStep] | None = None)"`
- Annotations: add the parameter description —
  `` `gates`: the stage's check steps — a list of `WorkflowGateStep` in authored order, or None when not specified (an empty list equals absence — normalized by `parse_workflow`). Declarative — extracted here, consumed by the compiler to emit the stage's completion gate ``
- Requirements: extend the fixed field order with `gates` (after `assistants`);
  add «gates defaults to None; an empty list equals absence — normalized by
  `parse_workflow`».
- Constraints: add — «Do not act on `gates` here — it is declarative; the
  compiler emits the completion gate when applying the workflow».
- Properties: add — `"gates -> list[WorkflowGateStep] | None": The stage's check steps in authored order, or None when not specified (an empty list equals absence).`

**Body — MODIFY `WorkflowDocument`:**

- Signature: append the last parameter `gates: WorkflowGates | None = None`.
- Annotations: add the parameter description —
  `` `gates`: the quality-gate settings block, or None when the workflow-file carries no block or authors an empty block. A workflow consisting of the block alone is valid ``
- Requirements: extend the fixed field order with `gates` (after `repeat`);
  extend the empty-workflow rule — «a workflow is empty only when … AND gates
  is None — the gates block counts as content»; extend the
  at-least-one-must-be-present rule with the gates block.
- Properties: add — `"gates -> WorkflowGates | None": The quality-gate settings block, or None when the workflow-file carries no block or authors an empty block.`

**Body — MODIFY `parse_workflow`:**

- Algorithm step 4 (top-level extraction): add —
  `gates: if present, must be a dict; otherwise raise a structural error "non-mapping gates block in workflow"`.
- Algorithm: ADD step 6.10 (settings block validation):
  - an unknown key raises "unknown key in workflow.gates: KEY; valid keys:
    patience, max_iterations, fresh_correction"
  - `patience`/`max_iterations` must be an int >= 0 and not a bool;
    otherwise raise "non-int value in workflow.gates.KEY" (non-int, a
    boolean included) or "KEY must be >= 0 in workflow.gates" (negative)
  - `fresh_correction` must be a bool; otherwise raise "non-bool value in
    workflow.gates.fresh_correction"
  - an empty block equals absence — carry gates=None; otherwise build a
    `WorkflowGates` from the authored keys only
- Algorithm: ADD step 6.1.15 (per-stage gates, after 6.1.13):
  - a non-list value raises "non-list gates in workflow.stages.NAME"; an
    empty list equals absence (None)
  - a non-mapping step raises "non-mapping gate step in
    workflow.stages.NAME.gates[i]"
  - the step key set is {name, script, agent, timeout, prompt}; an unknown
    key raises "unknown key in workflow.stages.NAME.gates[i]: KEY; valid
    keys: name, script, agent, timeout, prompt"
  - `name` is required: a missing name raises "gates step without name in
    workflow.stages.NAME.gates[i]"; a non-str value raises "non-str value in
    workflow.stages.NAME.gates[i].name"
  - exactly one of `script`/`agent` is required: both or neither raises
    "gates step must carry exactly one of script/agent in
    workflow.stages.NAME.gates[i]"
  - `script`/`agent` must be a non-empty string; otherwise raise "script
    must be a non-empty string in workflow.stages.NAME.gates[i]" (and the
    agent counterpart)
  - `timeout`/`prompt` (when present) must be a str; otherwise raise
    "non-str value in workflow.stages.NAME.gates[i].timeout" / ".prompt"
  - build a `WorkflowGateStep` list in authored order and thread it into
    the `WorkflowStage` construction of 6.1.14
- Algorithm: ADD step 6.11 — a `gates` key in an extend-entry raises a
  structural error "gates is forbidden in workflow.extend.NAME" — checks of
  a new stage are authored in the stages block by the new stage's name.
- Algorithm steps 5 and 7: extend the valid top-level key list and the
  unknown-key message with `gates`; extend the empty-workflow rule and its
  message with "the gates block".
- Algorithm step 8: extend the return construction enumeration with gates
  (the built `WorkflowGates`, or None).
- Requirements: add —
  - top-level unknown keys: only prompt, stages, extend, memory, profile,
    build, assistants, delegation, repeat, gates are accepted
  - per-stage unknown keys: gates joins the accepted per-stage key set
  - a workflow consisting of the gates block alone is valid
  - gates is forbidden in an extend-entry — a structural error
  - a malformed `timeout` value and the `name` text content are NOT
    validated — passed through verbatim (value grammar is engine-owned)

**Footer — `Description`:** extend the existing text with «…and the stage
quality-gate instructions (the retry settings block and the per-stage check
steps).» in the enumeration of extracted instruction sets.

#### `.usages/` files

**File: `goga/pipeline/workflow/.usages/gates.md` (CREATED):**

````md
# gates — authoring stage quality gates in the workflow-file

`gates` declares automated stage-completion checks: a per-stage list of check
steps a stage must pass before it counts as done, plus an optional
workflow-level settings block tuning the correction retries. The document
addresses workflow-file authors: everything described here is validated
structurally at parse time — typos and type or value mismatches are rejected
with a one-line error naming the workflow location. goga never runs the
checks: the engine executes the compiled gate and owns every retry semantic.

## The top-level `gates:` settings block

| Key | Type | Default | Note |
|-----|------|---------|------|
| `patience` | int >= 0 | not authored | tolerance for an unchanged correction stalemate |
| `max_iterations` | int >= 0 | not authored | bound of failed correction attempts |
| `fresh_correction` | bool | not authored | whether a correction session starts fresh |

- Authored keys only — no defaults are materialized; the engine defaults
  apply for unauthored keys.
- An empty block (`gates: {}`) equals absence. A workflow consisting of the
  block alone is valid.
- A boolean is not an integer for these checks.
- The settings travel only with stages that declare check steps — the block
  alone is inert: nothing is emitted, no error is raised.

## Per-stage check steps (`stages.<name>.gates`)

A list of check steps; an empty list equals absence. Each step is a mapping:

| Key | Type | Required | Note |
|-----|------|----------|------|
| `name` | str | yes | the dashboard label; required — the step numbering fallback is never relied on |
| `script` | str, non-empty | xor `agent` | a shell check step |
| `agent` | str, non-empty | xor `script` | an AI-review step; the same agent-name vocabulary as the per-stage agent override |
| `timeout` | str | no | carried verbatim; the duration grammar is engine-owned |
| `prompt` | str | no | the review instruction of an AI step |

Exactly one of `script`/`agent` per step — both or neither is a structural
error. The steps compile in authored order.

## Minimal examples

Settings plus a shell step and an AI-review step:

```yaml
gates:
  max_iterations: 2
  fresh_correction: true
stages:
  implementation:
    gates:
      - name: tests
        script: pytest -q
      - name: review
        agent: reviewer
        prompt: Review the diff for correctness.
```

Without the settings block the gated stages carry the steps alone (the
engine list form); an authored `timeout` overrides the materialized shell
default:

```yaml
stages:
  build:
    gates:
      - name: compile
        script: make all
        timeout: 30m
```

## Structural errors (parse time)

- "non-mapping gates block in workflow" — a scalar/list settings value
- "unknown key in workflow.gates: KEY; valid keys: patience, max_iterations, fresh_correction"
- "non-int value in workflow.gates.KEY" / "KEY must be >= 0 in workflow.gates" (a boolean is not an integer)
- "non-bool value in workflow.gates.fresh_correction"
- "non-list gates in workflow.stages.NAME"
- "non-mapping gate step in workflow.stages.NAME.gates[i]"
- "unknown key in workflow.stages.NAME.gates[i]: KEY; valid keys: name, script, agent, timeout, prompt"
- "gates step without name in workflow.stages.NAME.gates[i]"
- "gates step must carry exactly one of script/agent in workflow.stages.NAME.gates[i]"
- "script must be a non-empty string in workflow.stages.NAME.gates[i]" (and the agent counterpart)
- "gates is forbidden in workflow.extend.NAME" — checks of a new stage are
  authored in the stages block by the new stage's name

## What is NOT validated here

- The `timeout` duration grammar and the `name` text content — values pass
  verbatim; the engine reports malformed values at flow load/preflight.
- Stage names — the compiler's strict unknown-stage check covers them.
- Engine interplay constraints (the failure budget vs the patience value,
  the effective ceiling) — the engine owns and reports these.

## Anti-patterns

- Do not author `gates` in an extend-entry or in a stage body — both are
  strict structural errors; the checks of any stage are authored in the
  stages block by the stage's name.

This cell does NOT act on gates — no command composition, no emission
decisions, no retry interpretation. The compiler translates the authored
vocabulary one-directionally into the engine's and emits the stage gate;
the engine runs it.
````

**File: `goga/pipeline/workflow/.usages/parse-workflow.md` (MODIFIED):**

- Add `gates` to the accepted top-level key list at the top of the file.
- Add a row to the "Per-stage override keys" table:

```md
| gates | list | the stage's check steps — a required `name`, exactly one of `script`/`agent`, optional `timeout`/`prompt`; an empty list equals absence; compiled into the stage's `verify` gate; stages block only; declarative |
```

- Add a short section after the repeat-block section:

```md
## The gates blocks (settings + per-stage steps)

`gates` is the stage quality-gate instruction set: an optional top-level
settings block (`patience`, `max_iterations`, `fresh_correction` — authored
keys only, an empty block equals absence, a workflow consisting of the block
alone is valid) and an optional per-stage list of check steps in the stages
block (an empty list equals absence). Each step carries a required `name`
(the dashboard label), exactly one of `script` (a shell check) / `agent`
(an AI review), and optional `timeout`/`prompt`; value grammar (durations,
name text) is engine-owned. Every structural violation raises a one-line
error naming the workflow location.
```

---

### Cell 2: `goga/pipeline/compiler` (MODIFIED)

#### CODEMANIFEST diff

**Header — `Imports`:** extend the existing entry — add `WorkflowGates` and
`WorkflowGateStep` to `Types`; add `gates` to `Usages`:

```yaml
Imports:
  - Types:
      - WorkflowDocument
      - WorkflowStage
      - WorkflowExtendStage
      - WorkflowMemory
      - WorkflowReflect
      - WorkflowAssistant
      - WorkflowDelegation
      - WorkflowRepeat
      - WorkflowGates
      - WorkflowGateStep
    Usages:
      - parse-workflow
      - memory
      - assistants
      - gates
    From: goga/pipeline/workflow
```

**Header — `Annotations`:** append the following paragraphs:

```yaml
Gates compilation: the cell compiles a stage's authored check steps into the
engine's stage-completion gate — the verify field of the flow-file. The
translation is one-directional into the engine vocabulary: script → run,
agent → command (the authored agent name composed into the in-container
wrapper path /home/goga/bin/<agent>-as-claude.sh — composed directly, no
host-side resolution, no agent-name existence checks), patience →
review_patience, max_iterations → max_failures, fresh_correction unchanged;
name, prompt, and an authored timeout pass verbatim. A shell step without an
authored timeout carries the materialized "1h"; an AI step materializes no
timeout default — a goga-side product default, not an engine contract. When
the workflow-level gates settings block authored any key, every gated
stage's verify is the container form (the steps plus the authored settings,
authored keys only — no materialized settings); with no settings block
authored, a gated stage carries the steps alone (the list form). The
settings ride only on gated stages: ungated stages and the engine
configuration layers are never touched, and the settings block without
per-stage steps is inert. The verify key occupies the canonical fields slot
after assistants; inside the emitted block: steps, then the settings in the
fixed order max_failures, review_patience, fresh_correction; inside a step:
name, then run/command, then timeout, prompt. Use `afm` for the emitted
verify contract; use `gates` for the authoring vocabulary of the consumed
instructions.

Gates cross-reference checks run here, over the working body after skip
removal: gates on a stage compiling to a script stage (its body carries
script) and gates on a planning-only stage (translated agents exactly
["planning"]) are strict pre-run errors naming the stage — the engine
rejects both, and this cell surfaces them with its own messages. An
authoring gates key and a raw verify key in a stage body (pipeline-file
stage or embedded extend-stage body) are strict compile errors directing
the author to workflow.stages — verify is a compiled-only key, authored
exclusively through the workflow stages block. The checks run once on the
original — every loop-expanded copy carries the same gate without
revalidation; the gates of a skipped stage drop silently (skip removal runs
first).

This cell performs NO engine-interplay validation — no cross-field checks
of engine constraints (the failure budget vs the patience value, the
effective ceiling) — and never interprets, counts, or re-implements gate
execution: sequencing, fail-fast, full-list re-runs, retry budgets, verdict
parsing, and waiver are engine behavior. The flow-file is the single
delivery channel — this cell writes no engine configuration for gates. A
gate-free workflow compiles byte-identically: no verify key anywhere, no
other key affected; the pipeline-file and the input representation are
never modified by gates authoring.
```

**Body — ADD new type:**

```yaml
"FlowVerifyStep(name: str, run: str | None = None, command: str | None = None, timeout: str | None = None, prompt: str | None = None)":
  location: flow_verify_step.py
  annotations: |
    Emitted verify step — one check of a stage's completion gate. Built by
    `compile_flow` from one authored check step; consumed by
    `serialize_flow`.

    `name`: the check's dashboard label — the authored name verbatim
    `run`: the shell command of a shell step (from the authored script),
           or None
    `command`: the launch command of an AI step — the authored agent name
               composed into the in-container wrapper path
               /home/goga/bin/<agent>-as-claude.sh, or None
    `timeout`: the step timeout — the authored value verbatim, or the
               materialized "1h" on a shell step without an authored
               timeout; None on an AI step without an authored timeout
    `prompt`: the AI step's review instruction, carried verbatim, or None

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - Exactly one of `run`/`command` is not None — the step form mirrors
      the authored exclusivity
    - Field order is fixed: name, run, command, timeout, prompt — the
      emission order of the step keys

    Constraints:
    - Do not decide here whether the timeout is materialized —
      `compile_flow` applies the shell-step rule when building
    - Do not interpret the step — execution semantics belong to the
      engine (per `afm`)
  properties:
    "name -> str": |
      The check's dashboard label; the authored name verbatim.
    "run -> str | None": |
      The shell command of a shell step, or None.
    "command -> str | None": |
      The AI step's launch command — the authored agent name composed
      into the in-container wrapper path, or None.
    "timeout -> str | None": |
      The authored timeout verbatim, the materialized "1h" on a shell
      step without one, or None on an AI step without one.
    "prompt -> str | None": |
      The AI step's review instruction, carried verbatim, or None.
```

**Body — ADD new type:**

```yaml
"FlowVerify(steps: list[FlowVerifyStep], max_failures: int | None = None, review_patience: int | None = None, fresh_correction: bool | None = None)":
  location: flow_verify.py
  annotations: |
    Emitted stage completion gate — the compiled form of a stage's
    authored check steps and, when the workflow-level settings block
    authored any key, the authored retry settings under the engine
    vocabulary. Built by `compile_flow`; carried in the stage fields;
    consumed by `serialize_flow`.

    `steps`: the compiled check steps in authored order
    `max_failures`: the authored iteration bound (from max_iterations),
                    or None when not authored
    `review_patience`: the authored stalemate tolerance (from patience),
                       or None when not authored
    `fresh_correction`: the authored correction-session mode, or None
                        when not authored

    An instance carrying no authored setting IS the list emission form —
    the serialization writes the steps alone; any authored setting
    switches to the container form. This cell materializes no settings
    defaults.

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - `steps` is required (no default); every setting defaults to None —
      an authored zero is a value, not an omission
    - Field order is fixed: steps, max_failures, review_patience,
      fresh_correction — the emission order of the block keys

    Constraints:
    - Do not decide here whether the gate is emitted — `compile_flow`
      decides on the authored check steps
    - Do not interpret the settings or the steps — execution semantics
      belong to the engine (per `afm`)
  properties:
    "steps -> list[FlowVerifyStep]": |
      The compiled check steps in authored order.
    "max_failures -> int | None": |
      The authored iteration bound, or None when not authored.
    "review_patience -> int | None": |
      The authored stalemate tolerance, or None when not authored.
    "fresh_correction -> bool | None": |
      The authored correction-session mode, or None when not authored.
```

**Body — MODIFY `FlowStage`:**

- Extend the canonical fields key order in the type annotations and in the
  `fields` property description: `interactive, auto_approve, auto_run,
  command, prompt, description, buttons, agents, supervisor,
  supervisor_prompt, skills, script_before, script, script_after,
  script_timeout, reflect, memory_use, assistants, verify, then
  alphabetically-sorted unknown keys`.
- Add to the `fields` description — «verify (a `FlowVerify` gate) is
  present only when the stage carries authored check steps — uniform
  across every loop-expanded copy; a skipped stage carries none».

**Body — MODIFY `compile_flow`:**

- Algorithm: ADD step 4.11 (after 4.10, over the working body after skip
  removal and loop expansion):
  - authoring-key prohibitions (the same pass as the existing
    authoring-key checks, pipeline-file stage OR embedded extend-stage
    body): a `gates` key in a stage body raises a structural error "gates
    key is forbidden in stage body; use gates in workflow.stages"; a raw
    `verify` key in a stage body raises a structural error "verify key is
    forbidden in stage body; use gates in workflow.stages"
  - for each stage of the working body whose effective gates list is not
    None: a stage whose translated body carries `script` raises a strict
    error naming the stage; a stage whose translated agents value is
    exactly `["planning"]` raises a strict error naming the stage
  - the checks run once per stage name on the original — loop-expanded
    copies inherit the gate without revalidation; the gates of a removed
    stage never reach the checks
- Algorithm step 5: add the gates assembly — when a stage's effective
  gates list is not None, build a `FlowVerify`:
  - one `FlowVerifyStep` per authored `WorkflowGateStep` of the stage's
    effective gates list, in authored order: `script` →
    `run` with the timeout materialized to "1h" when not authored;
    `agent` → `command` composed as /home/goga/bin/<agent>-as-claude.sh
    (composed directly — no host-side resolution, no agent-name existence
    check); `name`, `prompt`, and an authored `timeout` carried verbatim;
    an AI step materializes no timeout default
  - the settings: when the `WorkflowGates` block of the workflow document
    authored any
    key, carry the authored keys only, translated (patience →
    review_patience, max_iterations → max_failures, fresh_correction
    unchanged); with no settings block authored, every setting stays None
    (the list form)
  - assemble into the `FlowStage` fields canonical slot after
    `assistants`; uniform across every loop-expanded copy; output-side
    only — the source bodies and `PipelineDocument` stay untouched
- Requirements: add —
  - gates on a stage compiling to a script stage and on a planning-only
    stage are strict pre-run errors naming the stage; the checks run over
    the working body after skip removal, once on the original
  - an authoring `gates` key and a raw `verify` key in a stage body
    (pipeline-file stage or embedded extend-stage body) are strict compile
    errors — `verify` is a compiled-only key; the accidental raw
    passthrough is closed
  - a shell step without an authored timeout materializes "1h"; an AI step
    materializes no timeout default — a goga-side product default, not an
    engine contract
  - the settings ride only on gated stages and only when the top-level
    block authored any key — authored keys only, no materialized settings;
    the settings block without per-stage steps is inert (no verify key
    anywhere, no error)
  - every loop-expanded copy carries the same gate; the gates of a skipped
    stage drop silently
  - the effective-override merge (step 4.5) passes the stages-block gates
    explicitly — gates is a stages-block-only field (an extend-entry carries
    none, and the extend-seeded virtual override carries None); a merge that
    omitted it would silently drop the gate of a stage carrying BOTH an
    extend-entry and a stages-block entry
  - a gate-free workflow compiles byte-identically — no verify key
    anywhere, no other key affected; the pipeline-file and
    `PipelineDocument` stay untouched
  - an AI step's command composition mirrors the per-stage agent override
    composition — direct, no host-side resolution, no agent-name existence
    checks
  - a malformed `timeout` value and the `name` text pass verbatim
    (engine-owned grammar)
  - no cross-field validation of engine interplay constraints; no
    interpretation of gate execution
- Constraints: add —
  - Do not validate the timeout duration grammar or the name text — the
    engine reports value-format errors at load/preflight
  - Do not cross-check engine constraints (the failure budget vs the
    patience value, the effective ceiling) — the engine owns these
  - Do not interpret, count, or re-implement gate execution — sequencing,
    fail-fast, re-runs, retry budgets, verdict parsing, and waiver are
    engine behavior
  - Do not write any engine configuration for gates — the flow-file is the
    single delivery channel
  - Do not re-validate the gates authoring vocabulary — the workflow
    parser rejected non-conforming authoring before compilation (per
    `gates`)
  - Do not leak the verify gate into `PipelineDocument` — output-side only

**Body — MODIFY `serialize_flow`:**

- Algorithm step 2: add the verify emission — when the stage fields carry
  the verify gate:
  - an instance with no authored setting serializes as the list form (the
    steps list is the verify value)
  - an instance with any authored setting serializes as the container
    form: a block-style mapping with `steps` first, then the authored
    settings in the fixed order max_failures, review_patience,
    fresh_correction (present keys only, plain scalars)
  - each step is a block-style mapping, key order name, run|command,
    timeout, prompt; run/command/timeout/prompt are plain scalars when
    single-line and block-literal scalars when multi-line (the
    script-family pattern)
- Requirements: add — a stage without a gate serializes without the verify
  key (byte-identical output for gate-free workflows); the container form
  is emitted only when a setting is authored; step scalar style follows
  the script-family pattern.
- Constraints: add — Do not reorder (canonical order fixed at assembly);
  do not interpret the gate.

**Footer — `Description`:** extend the existing text with «…and compiles
the stage quality gates into the engine verify field.»

#### `.usages/` files

**File: `goga/pipeline/compiler/.usages/compile-flow.md` (MODIFIED):** add
the following section:

```md
## Gates compilation (`verify`)

A stage carrying authored check steps compiles a stage-level completion
gate — the engine `verify` field, in the canonical slot after `assistants`.

Translation (authored → engine):

| Authored | Emitted | Note |
|----------|---------|------|
| `script` | `run` | shell step; timeout materializes `1h` when not authored |
| `agent` | `command` | `/home/goga/bin/<agent>-as-claude.sh` — composed directly, no existence checks |
| `patience` | `review_patience` | settings, authored keys only |
| `max_iterations` | `max_failures` | settings, authored keys only |
| `fresh_correction` | `fresh_correction` | unchanged |
| `name`/`prompt`/authored `timeout` | same | verbatim |

- No workflow-level settings block → the gate is the steps alone (list
  form); any authored setting key → the container form (steps + settings).
  The settings block without per-stage steps is inert.
- Steps compile in authored order; every loop-expanded copy carries the
  same gate; a skipped stage emits nothing.
- Pre-run strict errors (naming the stage): gates on a stage whose body
  carries `script`; gates on a planning-only stage (translated agents
  exactly `["planning"]`); an authoring `gates` or raw `verify` key in a
  stage body — `verify` is compiled-only, authored through
  `workflow.stages`.
- Value grammar (durations, name text) passes verbatim — the engine
  reports malformed values at preflight. goga performs no cross-field
  checks of engine constraints and never executes or interprets the gate.
- A gate-free workflow compiles byte-identically.
```

**File: `goga/pipeline/compiler/.usages/serialize-flow.md` (MODIFIED):** add
the following section:

```md
## Stage `verify` emission

- List form (no authored settings): the verify value IS the steps list.
- Container form (any authored setting): a block mapping — `steps` first,
  then the authored settings in the fixed order `max_failures`,
  `review_patience`, `fresh_correction` (present keys only, plain scalars).
- Each step: key order `name`, `run`|`command`, `timeout`, `prompt`;
  single-line values as plain scalars, multi-line as block-literal
  (script-family pattern).
- A stage without a gate carries no `verify` key — byte-identical output
  for gate-free workflows.
```

---

### Cell 3: `goga/pipeline/hooks` (MODIFIED)

#### CODEMANIFEST diff

**Body — MODIFY `WorkflowAmendment` (method `contribute`):**

- Extend the `document` parameter description: «a `WorkflowDocument`-shaped
  set of instructions (prompt, stages, extend, memory, assistants,
  delegation, repeat, gates) using the same vocabulary an authored
  workflow-file uses».
- Requirements: replace the empty-contribution bullet with — «A document
  with no prompt, no stages, no extend, no memory, no assistants, no
  delegation, no repeat, and no gates block is an empty contribution — the
  delivery discards it with a warning».

**Body — MODIFY `merge_workflow_overlay`:**

- Algorithm: ADD step 4d — «gates (settings block): keep the authored
  block when present — it is unbeatable; otherwise the block of the later
  contributing tool wins; no field-level merging».
- Algorithm: ADD step 5b — «stage gates: an ordinary stage field of the
  field-set-complete stage merge — an authored check-step list is never
  overwritten; a field the author left unset takes the value of the later
  contributing tool that sets it».
- Algorithm step 8: extend the final assembly with — «…the effective gates
  settings block rides the rebuilt document verbatim».
- Requirements: add — «The rebuilt `WorkflowDocument` preserves the gates
  instructions — the settings block whole and every stage's authored
  check-step list; a rebuild that drops them would silently strip stage
  quality checks from tool-amended runs».
- Constraints: add — «Do not interpret, validate, or rebuild the gates
  values — the block and the per-stage lists are carried whole; the merge
  unit is the field/block».

Header and Footer: no changes (the existing Description already states the
overlay preserves the full workflow model).

#### `.usages/` files

No changes.

---

### Cell 4: `goga/pipeline` (MODIFIED)

#### CODEMANIFEST diff

**Body — MODIFY `apply_skip_stages`:**

- Algorithm step 3: add — «The replacement carries NO gates — the compiler
  removes the skipped stage before the gates walk, and gates declare no
  document-wide namespace other stages reference» (the assistants carry
  rule stands unchanged).
- Algorithm step 4: extend the field enumeration with — «gates = the gates
  field of `workflow` when it is not None else None — carried verbatim».
- Requirements: add —
  - «The gates settings block of the input workflow survives the rebuild
    verbatim — a rebuild that drops it would strip the retry tuning from
    every remaining gated stage of a skip-driven run»
  - «The skip-replacement `WorkflowStage` carries no gates — the skipped
    stage's checks drop silently downstream»
  - «When `workflow` is None and `skip_stages` is non-empty — the
    constructed `WorkflowDocument` carries gates None»
- Constraints: add — «Do not interpret, validate, or rebuild the gates
  values — the block is carried as an opaque value, whole».

Header and Footer: no changes.

#### `.usages/` files

No changes.

---

## Dependency Map

```
goga/pipeline/workflow (leaf — no Imports; stays dependency-free)
  │
  │  Types → goga/pipeline/compiler:
  │    WorkflowDocument, WorkflowStage, WorkflowExtendStage,
  │    WorkflowMemory, WorkflowReflect, WorkflowAssistant,
  │    WorkflowDelegation, WorkflowRepeat (existing)
  │    + WorkflowGates, WorkflowGateStep          (NEW)
  │  Usages → goga/pipeline/compiler:
  │    parse-workflow, memory, assistants (existing) + gates (NEW)
  │
  ├──> goga/pipeline/compiler   (depends only on workflow; adds verify
  │                             emission + cross-reference checks)
  │
  ├──> goga/pipeline/hooks      (Types: WorkflowDocument — unchanged;
  │                             gates carried opaquely inside the document)
  │
  └──> goga/pipeline            (Types: WorkflowDocument — unchanged;
                                settings block carried verbatim)
```

No cycles: `workflow` is a leaf; `compiler` imports only from `workflow`;
`hooks` and `pipeline` import `WorkflowDocument` from `workflow`. The import
direction is unchanged — only the compiler's import set grows.

Implementation order: **workflow → compiler → hooks → pipeline**.

## Verification Checklist

After implementing each artifact, verify:

**`goga/pipeline/workflow`**

- `parse_workflow` accepts the top-level `gates` settings block and the
  per-stage `gates` list; every invalid authoring case from the plan
  (unknown keys, wrong types, bool-as-int, both/neither script/agent,
  a missing name field, empty script/agent, gates in an extend-entry)
  raises the exact one-line error naming the workflow location.
- An empty settings block and an empty per-stage list equal absence; a
  workflow consisting of the gates block alone is valid (not empty).
- `WorkflowDocument`/`WorkflowStage` carry the new fields in the fixed
  order; the cell stays dependency-free (no new imports).
- The facade exposes `WorkflowGates` and `WorkflowGateStep`.
- `gates.md` exists in `.usages/`; `parse-workflow.md` lists `gates`.

**`goga/pipeline/compiler`**

- A gated stage compiles a `verify` gate in the canonical slot after
  `assistants`: steps in authored order; shell step carries `run` + `1h`
  (or the authored timeout); AI step carries the composed wrapper
  `command` + prompt/label; authored settings translate
  (patience→review_patience, max_iterations→max_failures,
  fresh_correction unchanged) and ride only when the top-level block
  authored any key; without it the list form is emitted.
- The settings block alone compiles inert; a gate-free workflow compiles
  byte-identically (no `verify` key anywhere); `PipelineDocument` and the
  pipeline-file stay untouched.
- Cross-reference errors fire pre-run with goga's own messages: gates on a
  script stage, gates on a planning-only stage, `gates`/raw `verify` keys
  in a stage body, gates on an unknown stage name (existing error).
- Gates on a skipped stage drop silently; every loop-expanded copy carries
  the same gate.
- The facade exposes `FlowVerify` and `FlowVerifyStep`.
- `compile-flow.md` and `serialize-flow.md` carry the new sections.

**`goga/pipeline/hooks`**

- An overlay-amended workflow keeps its gates: the settings block and every
  stage's authored check-step list survive `merge_workflow_overlay`.
- A contribution consisting of the gates block alone is not discarded as
  empty by `WorkflowAmendment.contribute`.

**`goga/pipeline`**

- A skip-driven rebuild keeps the gates settings block for the remaining
  gated stages (`apply_skip_stages` carries it verbatim); the
  skip-replacement stage entry carries no gates.

**Project-wide**

- `goga lint` passes (DSL validity of all four modified CODEMANIFESTs).
- The full test suite and ruff pass (per `convention`).
- Riders of the implementation task (recorded, out of this plan's scope):
  the user-facing gates section in `docs/features/pipelines/workflows.md`
  and the engine verify fact base in `.goga/usages/cooks/afm.md`.
