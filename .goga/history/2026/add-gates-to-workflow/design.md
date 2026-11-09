# Design Document: `add-gates-to-workflow`

Topic: quality gates for workflow stages — workflow-DSL `gates` authoring
compiled one-directionally into the engine's stage `verify` field.

Sources (read-only inputs): `adr.md` (decisions), `prd.md` + `task.md`
(requirements), `arch.md` (materialized contract plan). This document designs
the implementation against the CODEMANIFEST changes materialized by
`apply-architecture` (working tree, branch `add-gates-to-workflow`) plus the
two user-approved contract fixes recorded under "Applied Fixes". No
implementation code is written here.

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/pipeline/workflow/CODEMANIFEST` — header Annotations gain the gates
  paragraph; new types `WorkflowGates` (`workflow_gates.py`) and
  `WorkflowGateStep` (`workflow_gate_step.py`); `WorkflowStage` gains
  `gates: list[WorkflowGateStep] | None`; `WorkflowDocument` gains
  `gates: WorkflowGates | None` (empty-workflow rule and at-least-one rule
  extended); `parse_workflow` gains steps 4/5/6.1.2/6.1.15/6.10/6.11/7/8 and
  Requirements bullets; Footer Description extended.
- `goga/pipeline/compiler/CODEMANIFEST` — Imports gain `WorkflowGates`,
  `WorkflowGateStep` (Types) and `gates` (Usages) from
  `goga/pipeline/workflow`; header Annotations gain three gates paragraphs and
  the canonical `FlowStage` fields order gains `verify` after `assistants`;
  new types `FlowVerifyStep` (`flow_verify_step.py`) and `FlowVerify`
  (`flow_verify.py`); `FlowStage` `fields` documentation gains the verify slot
  note; `compile_flow` gains step 4.11 (cross-reference checks), the step-5
  gates assembly, 10 Requirements and 6 Constraints; `serialize_flow` gains
  the step-2 verify emission, Requirements and Constraints; Footer Description
  extended.
- `goga/pipeline/hooks/CODEMANIFEST` — `WorkflowAmendment.contribute`
  (document description + empty-contribution rule counts the gates block);
  `PipelineHooks.amend_workflow` step-5 emptiness enumeration counts the gates
  block; `merge_workflow_overlay` gains steps 4d (settings block) and 5b
  (stage field), step-8 carriage, Requirements and Constraints.
- `goga/pipeline/CODEMANIFEST` — `apply_skip_stages`: step 3 (replacement
  carries NO gates), step 4 (`gates` carried verbatim in the document
  enumeration), 3 Requirements, 1 Constraint.

Cell-level `.usages/` changes (already materialized, verified current):
`goga/pipeline/workflow/.usages/gates.md` (created),
`parse-workflow.md` (modified), `goga/pipeline/compiler/.usages/compile-flow.md`
and `serialize-flow.md` (modified) — see "`.usages/` Update".

### New Entities

| Entity | Cell | Location | Kind |
|---|---|---|---|
| `WorkflowGates(patience, max_iterations, fresh_correction)` | workflow | `workflow_gates.py` | Entity (properties only) |
| `WorkflowGateStep(name, script, agent, timeout, prompt)` | workflow | `workflow_gate_step.py` | Entity (properties only) |
| `FlowVerifyStep(name, run, command, timeout, prompt)` | compiler | `flow_verify_step.py` | Entity (properties only) |
| `FlowVerify(steps, max_failures, review_patience, fresh_correction)` | compiler | `flow_verify.py` | Entity (properties only) |

### Changed Entities

- `WorkflowStage` — new trailing field `gates: list[WorkflowGateStep] | None =
  None` (fixed field order gains `gates` after `assistants`).
- `WorkflowDocument` — new trailing field `gates: WorkflowGates | None = None`
  (fixed field order gains `gates` after `repeat`).
- `parse_workflow` — new structural validation surfaces (settings block,
  per-stage check steps, extend-entry prohibition) and model threading.
- `FlowStage` — `fields` canonical key order gains `verify` after
  `assistants` (documentation-level; the dataclass shape `fields:
  dict[str, Any]` is unchanged).
- `compile_flow` — gates emission (checks + assembly) and the canonical slot.
- `serialize_flow` — verify emission (list and container forms).
- `WorkflowAmendment.contribute` / `PipelineHooks.amend_workflow` — the gates
  block counts as content.
- `merge_workflow_overlay` — settings-block merge (4d), stage-field merge
  (5b), rebuild carriage (8).
- `apply_skip_stages` — verbatim settings-block carriage; replacement carries
  no gates.

### Deleted Entities

None.

### Usages and Annotations Changes

- compiler `Imports` — `Types: +WorkflowGates, +WorkflowGateStep`;
  `Usages: +gates` (from `goga/pipeline/workflow`).
- workflow header `Annotations` — gates paragraph (validation surface,
  no gate logic, one-directional imports).
- compiler header `Annotations` — three gates paragraphs (compilation
  translation, cross-reference checks, no engine-interplay validation).
- All new/changed type and routine annotations per the diffs above.

## Applied Fixes

Two contract defects found during Phase-3 audit, both approved by the user
(decision `1A+2A`, question q1) and applied to the working tree; `goga lint`
passes (92 cells, 0 errors — re-run twice; one transient network flake
fetching an external usage URL in `goga/ast/factory` did not reproduce).

### Fixed CODEMANIFEST Defects

- `goga/pipeline/workflow/CODEMANIFEST` (step 6.1.14): the `WorkflowStage`
  construction enumeration did not list `gates` while step 6.1.15 threads the
  built list into that construction — a literal implementer would silently
  drop the instruction (reason: interface↔interface consistency; precedent:
  `assistants` appears in the enumeration). Before: `…(agent, env, prompt,
  loop, skills, skip, approve, manual, notes, reflect, memory, assistants)`.
  After: `…assistants, gates — the list built by 6.1.15)`.
- `goga/pipeline/workflow/CODEMANIFEST` (step 6.1.15 + Requirements + header
  Annotations), `gates.md`, `parse-workflow.md`: `prompt` authored on a
  `script` (shell) step was accepted by goga and compiled verbatim, but the
  engine parses `prompt` as AI-step-only and rejects the whole flow at load
  (verified against the published engine docs). The ADR asserts "a goga shell
  step never carries `prompt`" — now enforced: a structural parse error
  `prompt is forbidden on a script gate step in workflow.stages.NAME.gates[i]`
  (reason: validation-boundary consistency — field-to-form binding is
  structure, which is goga's; value grammar stays engine-owned).

## Entity Interaction and Data Flow

### Interaction Diagram

```
workflow-file text (rendered)
        |
        v
parse_workflow (workflow cell ── leaf, no Imports)
        |  WorkflowDocument{ gates: WorkflowGates|None,
        |                     stages[name].gates: list[WorkflowGateStep]|None }
        v
compile_flow (compiler cell; imports WorkflowGates/WorkflowGateStep + `gates` usage)
        |  4.11 checks  : gates on script stage / planning-only stage -> StructuralError
        |                gates|verify keys in a stage body      -> StructuralError
        |  step 5 build : WorkflowGateStep -> FlowVerifyStep (script->run, agent->command,
        |                wrapper path, "1h" shell default)
        |                WorkflowGates  -> FlowVerify settings (authored keys only)
        |  FlowStage.fields["verify"] = FlowVerify  (canonical slot after "assistants")
        v
serialize_flow (compiler cell)
        |  list form (no authored setting) | container form (steps + settings)
        v
flow-file YAML  ──────────────> afm engine (verify contract — external, see Usages)
        ^
        | overlay path (hooks cell; WorkflowDocument only)
merge_workflow_overlay ── settings block authored-wins (4d), stage gates
        │                 authored-wins field (5b), carriage (8)
        v
amended WorkflowDocument ──> compile_flow
        ^
        | skip path (pipeline cell)
apply_skip_stages ── settings block carried verbatim; replacement stage
        │             carries NO gates (compiler removes the stage first)
        v
skip-merged WorkflowDocument ──> compile_flow
```

### Data Flows

1. **Authoring → model** (workflow cell): `parse_workflow(text)` validates the
   top-level `gates:` settings block (keys/types/bounds; empty = absence) and
   each per-stage `gates:` list (step forms; empty list = absence) and builds
   `WorkflowGates` / `list[WorkflowGateStep]`, threaded into
   `WorkflowDocument` / `WorkflowStage`. `gates is not None` ⇔ at least one
   authored key (the parser normalizes emptiness to `None`) — every downstream
   "authored any key" decision reduces to an `is not None` check.
2. **Model → flow** (compiler cell): for every stage name of the working body
   (after skip removal and loop expansion) whose effective gates list is not
   `None`, one `FlowVerify` is built (steps in authored order; settings from
   the workflow-level block when it authored any key) and mapped onto every
   produced id of that base name; `_canonical_fields` places it in the
   `verify` slot; `serialize_flow` writes the list or container form.
3. **Amendment overlay** (hooks cell): a tool contribution's gates block and
   per-stage gates merge authored-wins (block/field whole, never rebuilt);
   the rebuilt document keeps them, so an amended run compiles with gates.
4. **Skip rebuild** (pipeline cell): the settings block rides the rebuilt
   document verbatim; a skipped stage's replacement entry carries no gates.

### Entity Dependencies

- `workflow` stays a leaf (stdlib + PyYAML only; no new imports).
- `compiler` imports the two new types and the `gates` usage from `workflow`
  (already the only dependency; direction unchanged).
- `hooks` and `pipeline` carry gates opaquely inside `WorkflowDocument` — no
  new imports.
- Implementation order: **workflow → compiler → hooks → pipeline** (matches
  dependency direction; downstream compiles only after the models exist).

## Code Stack Trace

All traces verified against the current sources
(`parse_workflow.py`, `compile_flow.py`, `serialize_flow.py`, `overlay.py`,
`events.py`, `amendments.py`, `apply_skip_stages.py`) and the facade files.
External calls verified against the published engine documentation
(<https://akopichin.github.io/afm/verify/>, fetched 2026-11-09) — see the
trace "Engine verify boundary".

### Trace: `parse_workflow` (workflow cell)

#### Chain

1. **Input**: rendered workflow-file text (caller owns reading/rendering).
2. `yaml.safe_load` → mapping or `WorkflowSyntaxError("invalid YAML in
   workflow-file")` → checkpoint: unchanged ✅.
3. `_extract_top_level(loaded)` — **extend to a 10-tuple**: new dispatch arm
   `elif key == "gates": gates_raw = _validate_top_level_mapping("non-mapping
   gates block in workflow", value)`; `_TOP_LEVEL_KEYS` gains `"gates"`
   (appended last — the unknown-key message enumerates `…, delegation,
   repeat, gates`) → checkpoint: message shape matches contract step 5 ✅.
4. `_build_gates(gates_raw)` (new; mirrors `_build_repeat`): unknown key →
   `"unknown key in workflow.gates: KEY; valid keys: patience,
   max_iterations, fresh_correction"`; `patience`/`max_iterations` int ≥ 0
   and not bool (`"non-int value in workflow.gates.KEY"` /
   `"KEY must be >= 0 in workflow.gates"`); `fresh_correction` bool
   (`"non-bool value in workflow.gates.fresh_correction"`); empty block →
   `None`; else `WorkflowGates` from authored keys only → checkpoint:
   authored-zero preserved (`0` is a value); empty = absence ✅.
5. `_build_stage(name, value)` → `_validate_stage_field`: new arm
   `elif key == "gates": return _build_stage_gates(name, field_value)`;
   `_STAGE_KEYS` gains `"gates"` (unknown-key message `…, memory, assistants,
   gates` per 6.1.2) → checkpoint: dispatch shape identical to
   `reflect`/`memory`/`assistants` arms ✅.
6. `_build_stage_gates(name, value)` (new): non-list → `"non-list gates in
   workflow.stages.NAME"`; empty list → `None`; per step `i` (authored
   order, first defect raises): non-mapping → `"non-mapping gate step in
   workflow.stages.NAME.gates[i]"`; unknown key → `"unknown key in
   workflow.stages.NAME.gates[i]: KEY; valid keys: name, script, agent,
   timeout, prompt"`; `name` required (`"gates step without name in
   workflow.stages.NAME.gates[i]"`) and str (`"non-str value in
   workflow.stages.NAME.gates[i].name"`); exactly one of `script`/`agent`
   (`"gates step must carry exactly one of script/agent in
   workflow.stages.NAME.gates[i]"`); non-empty str (`"script must be a
   non-empty string in workflow.stages.NAME.gates[i]"` and the `agent`
   counterpart); `timeout`/`prompt` str when present (`"non-str value in
   workflow.stages.NAME.gates[i].timeout"` / `".prompt"`); **prompt binding**
   (`"prompt is forbidden on a script gate step in
   workflow.stages.NAME.gates[i]"`); build the `WorkflowGateStep` list in
   authored order → checkpoint: check order follows contract 6.1.15
   (key set → name → exclusivity → non-empty → types → prompt binding) ✅.
7. `_build_stage` construction: `WorkflowStage(..., assistants=…,
   gates=fields.get("gates"))` → checkpoint: step 6.1.14 now enumerates
   `gates` (Applied Fixes) ✅.
8. `_reject_forbidden_extend_keys`: the forbidden tuple gains `"gates"` →
   message `"gates is forbidden in workflow.extend.NAME"` (matches contract
   6.11 and the existing `{key} is forbidden in workflow.extend.{name}`
   shape) → checkpoint ✅.
9. Empty-workflow rule: condition gains `and gates is None`; message ends
   `…, the repeat block, or the gates block` → checkpoint: a gates-only
   workflow is valid content ✅.
10. **Output**: `WorkflowDocument(..., repeat=repeat, gates=gates)`.

#### Checkpoint Summary

- Types: `WorkflowGates | None` and `list[WorkflowGateStep] | None` flow into
  the document/stage models exactly as declared — passed.
- Empty-equals-absence normalization happens entirely at parse (downstream
  `is not None` discipline) — passed.
- Value grammar (`timeout` durations, `name` text) passes verbatim — passed
  (no duration parser, no name-content check beyond str-ness).

### Trace: `compile_flow` (compiler cell)

#### Chain

1. **Input**: pipeline path, flow path, optional `WorkflowDocument`.
2. `parse_dsl` + empty-body guard + step 4.0 repeat check — unchanged.
3. `_reconstruct_body(fmt, body, workflow)` (workflow path):
   4a0-pre extend refs → 4a0 embed → 4pre stage names (existing
   unknown-stage error covers gates on unknown names — no new check) →
   4skip removal (a skipped stage's gates never reach the checks — silent
   drop) → `_effective_overrides(workflow)`:
   - extend-seeded entries: `WorkflowStage(agent=…, loop=…, approve=…)` —
     `gates` stays `None` (constructor default; gates is stages-block-only);
   - merged entries (extend + stages-block): **add `gates=stg.gates`** to
     the explicit per-field pass — omitting it would silently drop the gate
     of a stage carrying both entries → checkpoint: contract Requirement
     "the effective-override merge passes the stages-block gates
     explicitly" ✅;
   → `_apply_per_stage_overrides` → `_expand_loops` (+STAGES
   `depends_on` rewrite).
4. **`_gates_emission(workflow, effective, expanded, expanded_ids) ->
   dict[str, FlowVerify]`** (new companion, called after
   `_collaboration_emission` — numbering 4.9 → 4.10 → 4.11 keeps the
   attachment errors firing before the gates errors when both exist):
   - `workflow.gates is None` cannot reach here with gated stages (gates
     author only in the workflow); the settings source is `workflow.gates`.
   - `bodies = {step.name: step.body for step in expanded}`; for each
     `(base_name, produced_ids)`: `stage = effective.get(base_name)`;
     `gates = stage.gates if stage is not None else None`; skip when `None`.
   - Checks, once per base name on the original body (copies share shape —
     overrides apply before expansion, bodies are deep copies):
     `"script" in bodies[produced_ids[0]]` → `StructuralError("gates are
     forbidden on a script stage in workflow.stages.{base_name}")`;
     `_translate_body_agents(bodies[produced_ids[0]]) == ["planning"]` →
     `StructuralError("gates are forbidden on a planning-only stage in
     workflow.stages.{base_name}")` → checkpoint: the translated-agents
     comparison reuses the existing `_translate_body_agents` helper (the
     attachment-check precedent; authored `roles: [planner]` equals
     `roles: [planning]`) ✅; message texts are fixed by this design (the
     contract pins "a strict error naming the stage" only) and mirror the
     assistants wording minus the assistant name.
   - Build one `FlowVerifyStep` per authored `WorkflowGateStep` in authored
     order: `script` → `run` (timeout materialized to `"1h"` when not
     authored); `agent` → `command = _WRAPPER_PATH_TEMPLATE.format(agent=…)`
     (the existing `"/home/goga/bin/{agent}-as-claude.sh"` constant — the
     per-stage agent-override composition, direct, no resolution, no
     existence checks); `name`/`prompt`/authored `timeout` verbatim; an AI
     step materializes no timeout default → checkpoint: exclusivity mirrors
     the authored form (`run` xor `command`); the parser guarantees `prompt`
     is `None` on shell steps (Applied Fixes) ✅.
   - Settings: `workflow.gates is not None` (⇔ authored any key) →
     `FlowVerify(steps, max_failures=gates.max_iterations,
     review_patience=gates.patience,
     fresh_correction=gates.fresh_correction)` — authored keys only, no
     materialized defaults; else `FlowVerify(steps)` (the list form — every
     setting `None`) → checkpoint: translation matches `patience →
     review_patience`, `max_iterations → max_failures`, `fresh_correction`
     unchanged ✅.
   - Map the same `FlowVerify` onto every produced id
     (`verify_by_id[pid] = verify`) — uniform across loop copies; the
     canonical-order loop in `_canonical_fields` deep-copies it per stage
     (no aliasing), the assistants precedent.
5. Workflow-less path: `verify_by_id = {}` (mirror of `_MemoryEmission`
   default) — nothing assembles, byte-identical output.
6. `_canonical_fields(body, name, notes=…, memory_fields=…,
   assistants_fields=…, verify_fields=verify_by_id.get(step.name))` in BOTH
   the PHASES and STAGES branches; `_assemble_verify(source,
   verify_fields)` assigns `source["verify"]` when not `None` — before the
   canonical loop, which slots it after `assistants`
   (`_CANONICAL_KEY_ORDER` gains `"verify"` after `"assistants"`).
7. **Authoring-key prohibitions** — `_reject_authoring_output_keys` gains:
   `"gates" in body` → `StructuralError("gates key is forbidden in stage
   body; use gates in workflow.stages")`; `"verify" in body` →
   `StructuralError("verify key is forbidden in stage body; use gates in
   workflow.stages")` — the same pass as the existing
   `buttons`/`reflect`/`memory_use`/`assistants` prohibitions (runs from
   `_canonical_fields` on every produced copy; pipeline-file stage OR
   embedded extend-stage body) → checkpoint: closes today's accidental raw
   `verify` passthrough (unknown keys currently flow to the flow verbatim) ✅.
8. **Output**: `FlowStage.fields["verify"] = FlowVerify`;
   `PipelineDocument` and the pipeline-file stay untouched (output-side
   only).

#### Checkpoint Summary

- Type flow: `list[WorkflowGateStep]` → `FlowVerify.steps:
  list[FlowVerifyStep]` field-for-field — passed.
- Interface alignment: `FlowStage.fields` consumes the `FlowVerify` object;
  `serialize_flow` discriminates on it — passed.
- Byte-identical gate-free output: no parsed gates → no emission → no
  `verify` key anywhere; no other key affected — passed.
- Error precedence when several defects coexist: extend refs (4a0-pre) →
  stage names (4pre) → repeat (4.0, earlier still) → attachments (4.10) →
  gates script/planning (4.11) → body-key prohibitions (step 5 pass) — all
  pre-run; the contract fixes no precedence among the gates checks beyond
  this, and the design keeps the companions' call order.

### Trace: `serialize_flow` (compiler cell)

#### Chain

1. **Input**: `FlowDocument` with `FlowStage.fields` in canonical order.
2. `_build_stage_repr(stage)` — new arm before the generic `else`:
   `elif key == "verify" and isinstance(value, FlowVerify): stage_repr[key]
   = _verify_repr(value)`.
3. `_verify_step_repr(step)` (new helper, mirrors `_assistant_repr`):
   ordered mapping `name` → `run` xor `command` (whichever is not `None`) →
   `timeout` (when not `None`) → `prompt` (when not `None`); each of
   `run`/`command`/`timeout`/`prompt` wrapped in `_BlockLiteralScript`
   iff it is a `str` containing `"\n"` (the script-family pattern) →
   checkpoint: engine fields `name`/`run`/`command`/`prompt`/`timeout`
   exactly; no extra keys ✅.
4. `_verify_repr(gate)`: no authored setting (`max_failures is None and
   review_patience is None and fresh_correction is None`) → the steps list
   (the engine list form); else the ordered container `{"steps": [...]}`
   then present settings only, fixed order `max_failures`, `review_patience`,
   `fresh_correction` (plain scalars) → checkpoint: matches the engine
   container contract (`steps` plus the three settings; step fields at the
   container top level are a parse error — never emitted) ✅.
5. **Output**: canonical YAML via the existing `_CanonicalDumper` /
   `beautiful_yaml` parameters; a stage without a gate never enters the arm —
   no `verify` key, byte-identical.

#### Checkpoint Summary

- No reordering (canonical order fixed at assembly) — passed.
- No interpretation of the gate — passed.

### Trace: `merge_workflow_overlay` (hooks cell)

#### Chain

1. **Input**: authored `base` (or `None`), committed `contributions`.
2. Step 4d — `_merge_gates(base, contributions)` (new; line-for-line the
   `_merge_repeat` shape): the authored block when present (unbeatable),
   else the later contributing tool's block; no field-level merging.
3. Step 5b — `_STAGE_FIELDS` gains `"gates"` (last, declaration order):
   `_STAGE_DEFAULTS` (built `fromkeys(_STAGE_FIELDS)`) automatically gains
   the `None` default, and `_merge_stage`'s authored-wins field loop carries
   `gates` like `agent`/`prompt`/`notes` — an authored check-step list is
   never overwritten (`_is_set`: not-`None` = set); an unset field takes the
   later contributing tool's value. No `assistants`-style carve-out — gates
   is an ordinary field; the merge unit is the field.
4. Step 8 — the rebuilt `WorkflowDocument(..., repeat=repeat,
   gates=_merge_gates(base, contributions))`; `profile`/`build` verbatim as
   before.
5. **Output**: new document; inputs never mutated; gates values carried
   whole (never interpreted, validated, or rebuilt).

#### Checkpoint Summary

- A gates-only tool contribution is content: `amend_workflow`'s emptiness
  check gains `and document.gates is None` (see next trace) — passed.
- No cycles, no new imports (`WorkflowDocument` only) — passed.

### Trace: `WorkflowAmendment.contribute` / `PipelineHooks.amend_workflow` (hooks cell)

#### Chain

1. `contribute(document)` buffers the document — docstring enumeration gains
   `gates` ("prompt, stages, extend, memory, assistants, delegation, repeat,
   gates"); no behavioral change.
2. `amend_workflow` walk (events.py): the per-hook buffer duck-check tuple
   gains `"gates"` (`("prompt", "stages", "extend", "memory", "assistants",
   "delegation", "repeat", "gates")` — consistency: the buffer type check
   reads every fact); the empty-document discard gains `and
   document.gates is None`; the docstring's step-5 enumeration gains "and no
   gates block".
3. **Output**: a gates-only contribution commits as a `ToolContribution` and
   merges (authored base wins over it per 4d/5b).

#### Checkpoint Summary

- A contribution consisting of the gates block alone is NOT discarded —
  passed (contract Requirement).

### Trace: `apply_skip_stages` (pipeline cell)

#### Chain

1. **Input**: `workflow` (or `None`), `skip_stages`.
2. Step 3 — the replacement `WorkflowStage(skip=True, assistants=…)` carries
   NO gates: the dataclass default `gates=None` already provides this; no
   code change (documented in the docstring — the compiler removes the
   skipped stage before the gates walk).
3. Step 4 — the rebuilt document gains `gates=workflow.gates if workflow is
   not None else None` — carried verbatim (same object, opaque).
4. **Output**: new document; a `None` workflow with non-empty skips
   constructs with `gates=None`.

#### Checkpoint Summary

- The settings block survives skip-driven runs for the remaining gated
  stages — passed; the skipped stage's checks drop silently downstream —
  passed.

### Trace: Engine verify boundary (external contract — verified)

Verified against <https://akopichin.github.io/afm/verify/> (fetched
2026-11-09). Every ADR engine assumption is confirmed:

| Assumption | Verification |
|---|---|
| Container form = `steps` + `max_failures`/`review_patience`/`fresh_correction`; step fields at container top level = parse error | Confirmed ("No other top-level keys are allowed here: a step field (`run`/`command`/`prompt`/`timeout`) at the container's top level is a parse error"; `name` likewise rejected there) |
| Step `timeout` valid on both shell and AI steps | Confirmed (Fields table: `timeout` — either) |
| `prompt` AI-step-only; `run`/`command` mutually exclusive, exactly one required | Confirmed — and now enforced goga-side (Applied Fixes) |
| `command` resolves via the same mechanism as `stage.command` | Confirmed ("an agent alias, resolved by the same command/recipe mechanism as `stage.command`") — the wrapper-path composition is the known-good shape |
| Gates forbidden on `script` stages and planning-only (`agents: [planning]`) stages | Confirmed (both stated verbatim) |
| `name`: a string with ≥ 1 non-space character; empty/space-only = parse error | Confirmed — goga checks str-ness only; whitespace-only passes verbatim (engine-reported) |
| `max_failures ≥ review_patience` interplay; effective ceiling `min(max_failures, 15)` | Confirmed — engine-owned; goga performs no cross-check |
| Older engines reject a gated flow at load (downgrade not silent) | Confirmed |

Execution semantics that stay with the engine (never re-implemented by
goga): in-order fail-fast steps; full-list re-runs after a correction;
correction budget; stalemate acceptance; strict JSON verdicts
(`pass`/`needs_changes`/`inconclusive`); transient verifier retries; human
waiver; dashboard labeling (incl. the fallback numbering goga never relies
on because `name` is required).

## Algorithm Design

### `WorkflowGates` (workflow_gates.py — new)

**Responsibility**: data model of the workflow quality-gate settings; pure
data, no validation, no interpretation.

**Construction**: `@dataclass(kw_only=True)`; fields `patience:
int | None = None`, `max_iterations: int | None = None`,
`fresh_correction: bool | None = None` — fixed order, all defaults `None`
(authored values only; an authored `0` is a value, not an omission).
Google-style docstring per `convention`. Module docstring mirrors
`workflow_repeat.py`.

**Errors**: none (parse-time validation lives in `parse_workflow`).

**Edge cases**: authored zero on `patience`/`max_iterations` stays `0`
(disabled stalemate / strict budget respectively — engine semantics).

### `WorkflowGateStep` (workflow_gate_step.py — new)

**Responsibility**: data model of one authored check step.

**Construction**: `@dataclass(kw_only=True)`; fields `name: str` (required,
no default), `script: str | None = None`, `agent: str | None = None`,
`timeout: str | None = None`, `prompt: str | None = None` — fixed order
(name, script, agent, timeout, prompt). Exactly one of `script`/`agent` is
not `None` on every constructed instance (parser-enforced); `prompt` is
`None` on every shell instance (parser-enforced, Applied Fixes).

**Errors**: none.

### `WorkflowGateStep` list building — `_build_stage_gates` (parse_workflow.py)

**Algorithm** (per contract 6.1.15; check order is normative):

```
1. IF value is not a list:
     raise "non-list gates in workflow.stages.NAME"
2. IF value is empty: RETURN None            # empty list equals absence
3. FOR i, step in enumerate(value):
   a. IF step is not a dict:
        raise "non-mapping gate step in workflow.stages.NAME.gates[i]"
   b. IF any key outside {name, script, agent, timeout, prompt}:
        raise "unknown key in workflow.stages.NAME.gates[i]: KEY;
              valid keys: name, script, agent, timeout, prompt"
   c. IF "name" not in step:
        raise "gates step without name in workflow.stages.NAME.gates[i]"
      IF step["name"] is not a str:
        raise "non-str value in workflow.stages.NAME.gates[i].name"
   d. IF ("script" in step) == ("agent" in step):        # both or neither
        raise "gates step must carry exactly one of script/agent in
               workflow.stages.NAME.gates[i]"
   e. IF step["script"] is not a non-empty str:
        raise "script must be a non-empty string in
               workflow.stages.NAME.gates[i]"            # agent counterpart
   f. IF "timeout" in step and not a str:
        raise "non-str value in workflow.stages.NAME.gates[i].timeout"
      IF "prompt" in step and not a str:
        raise "non-str value in workflow.stages.NAME.gates[i].prompt"
   g. IF "prompt" in step and "script" in step:
        raise "prompt is forbidden on a script gate step in
               workflow.stages.NAME.gates[i]"            # Applied Fixes
4. RETURN [WorkflowGateStep(...) for each step]          # authored order
```

**Edge cases**: a present `null` (`script:` with no value) is a
type error (non-empty-str check), not an absence — consistent with the
`timeout: null`-is-present discipline of the stage body. An authored
malformed `timeout` (e.g. `"30x"`) or whitespace-only `name` passes verbatim
(engine-owned grammar).

### `WorkflowGates` building — `_build_gates` (parse_workflow.py)

**Algorithm** (per contract 6.10; mirrors `_build_repeat`):

```
1. IF gates_raw is None: RETURN None
2. FOR key, value in gates_raw.items():        # authored order, first defect raises
     patience / max_iterations:
       bool or non-int  -> raise "non-int value in workflow.gates.KEY"
       < 0              -> raise "KEY must be >= 0 in workflow.gates"
     fresh_correction:
       non-bool         -> raise "non-bool value in
                                  workflow.gates.fresh_correction"
     other key          -> raise "unknown key in workflow.gates: KEY; valid
                                  keys: patience, max_iterations,
                                  fresh_correction"
3. IF gates_raw is empty: RETURN None          # empty block equals absence
4. RETURN WorkflowGates(patience=…, max_iterations=…, fresh_correction=…)
   # authored keys only — absent keys stay None
```

### `parse_workflow` integration (parse_workflow.py)

- Constants: `_TOP_LEVEL_KEYS` += `"gates"`; `_STAGE_KEYS` += `"gates"`;
  new `_GATES_KEYS = ("patience", "max_iterations", "fresh_correction")` and
  `_GATE_STEP_KEYS = ("name", "script", "agent", "timeout", "prompt")`
  (message sources, mirroring `_REPEAT_KEYS`).
- `_extract_top_level` returns the 10-tuple ending in `gates_raw`.
- `_validate_stage_field` dispatch arm for `"gates"`.
- `_build_stage` construction gains `gates=fields.get("gates")`.
- `_reject_forbidden_extend_keys` tuple += `"gates"` (contract 6.11).
- Empty-workflow condition += `and gates is None`; message += `, or the
  gates block`.
- `WorkflowDocument(..., gates=gates)`; `parse_workflow` docstring `Raises`
  section extended with the gates cases.

### `FlowVerifyStep` (flow_verify_step.py — new)

**Responsibility**: one emitted verify step. `@dataclass(kw_only=True)`:
`name: str` (required), `run: str | None = None`, `command: str | None =
None`, `timeout: str | None = None`, `prompt: str | None = None` — fixed
order (the emission order of the step keys). Exactly one of `run`/`command`
not `None` mirrors the authored exclusivity.

### `FlowVerify` (flow_verify.py — new)

**Responsibility**: the emitted stage completion gate.
`@dataclass(kw_only=True)`: `steps: list[FlowVerifyStep]` (required, no
default), `max_failures: int | None = None`, `review_patience: int | None =
None`, `fresh_correction: bool | None = None` — fixed order (the emission
order of the block keys). An instance carrying no authored setting IS the
list emission form.

### `_gates_emission` (compile_flow.py — new)

**Algorithm**:

```
1. gates_settings = workflow.gates                # WorkflowGates | None
2. bodies = {step.name: step.body for step in expanded}
3. verify_by_id = {}
4. FOR base_name, produced_ids in expanded_ids.items():
     stage  = effective.get(base_name)
     gates  = stage.gates if stage is not None else None
     IF gates is None: CONTINUE
     body = bodies[produced_ids[0]]               # the original; copies share shape
     IF "script" in body:
       raise "gates are forbidden on a script stage in
              workflow.stages.{base_name}"
     IF _translate_body_agents(body) == ["planning"]:
       raise "gates are forbidden on a planning-only stage in
              workflow.stages.{base_name}"
     steps = []
     FOR gs in gates:                             # authored order
       IF gs.script is not None:
         steps.append(FlowVerifyStep(
           name=gs.name, run=gs.script,
           timeout=(gs.timeout if gs.timeout is not None else "1h"),
           prompt=gs.prompt))                     # None by the parse guarantee
       ELSE:
         steps.append(FlowVerifyStep(
           name=gs.name,
           command=_WRAPPER_PATH_TEMPLATE.format(agent=gs.agent),
           timeout=gs.timeout, prompt=gs.prompt)) # no AI default
     IF gates_settings is not None:               # ⇔ authored any key
       verify = FlowVerify(steps=steps,
         max_failures=gates_settings.max_iterations,
         review_patience=gates_settings.patience,
         fresh_correction=gates_settings.fresh_correction)
     ELSE:
       verify = FlowVerify(steps=steps)           # list form
     FOR pid in produced_ids: verify_by_id[pid] = verify
5. RETURN verify_by_id
```

**Errors**: `StructuralError` for the two cross-reference checks (texts
above — fixed by this design; the contract pins "a strict error naming the
stage").

**Edge cases**: a stage named in BOTH `extend` and `stages` — the merged
effective override carries the stages-block gates (fix in
`_effective_overrides`); an extend-only stage never carries gates (seeded
`None`); a skipped stage never reaches the walk; loop copies share the same
`FlowVerify` (uniform), deep-copied per stage at canonical assembly.

### `compile_flow` integration (compile_flow.py)

- `_CANONICAL_KEY_ORDER` += `"verify"` after `"assistants"` (comment block
  extended with the verify sentence).
- `_reject_authoring_output_keys` += the `gates` and `verify` prohibitions
  (exact texts above).
- `_effective_overrides` merged branch += `gates=stg.gates` (docstring
  updated).
- `_canonical_fields` signature += `verify_fields: FlowVerify | None = None`;
  `_assemble_verify(source, verify_fields)` assigns before the canonical
  loop (assistants pattern); docstring updated. The signature pin test of
  `test_compile_flow.py` extends accordingly — the parameter list ends with
  `verify_fields`, default None.
- `compile_flow` body: workflow path unpacks the fourth companion
  `verify_by_id`; both branches pass
  `verify_fields=verify_by_id.get(step.name)`; workflow-less path sets
  `verify_by_id = {}`; docstrings (Args/Raises/Returns) extended.
- The gates/verify body-key prohibitions fire from the `_canonical_fields`
  pass (step 5) — after the 4.10/4.11 emission checks; all pre-run.

### `serialize_flow` integration (serialize_flow.py)

- New `_verify_step_repr(step)` and `_verify_repr(gate)` helpers (design
  above); imports `FlowVerify`/`FlowVerifyStep`.
- `_build_stage_repr` gains the `verify` arm; docstring updated.

### `merge_workflow_overlay` integration (overlay.py)

- `_STAGE_FIELDS` += `"gates"`; `_merge_gates` (the `_merge_repeat` shape);
  final assembly += `gates=…`; docstring gains the 4d/5b/8 arms.

### `apply_skip_stages` integration (apply_skip_stages.py)

- Document assembly += `gates=workflow.gates if workflow is not None else
  None`; docstring bullets per the contract (replacement carries no gates;
  settings survive; `None` workflow → `gates None`).

## Cross-cutting Concerns

- **Error handling**: two existing exception types only —
  `WorkflowSyntaxError` (parser; one-line messages naming the workflow
  location) and `StructuralError` (compiler; one-line messages naming the
  stage/location). No new exception classes; no error swallowing; the engine
  remains the reporter of value-grammar errors at flow load/preflight.
- **Logging**: none added. The gates path emits no logs (the only compiler
  WARNING precedent — inline-declaration skills — has no gates analogue);
  hooks/pipeline carry silently, as for `repeat`.
- **Validation**: the two-layer split — parser = structure (key sets, types,
  bounds, step forms, exclusivity, required name, prompt binding, extend
  prohibition); compiler = cross-references after skip removal (unknown stage
  name [existing], script stage, planning-only stage, forbidden body keys).
  No engine-interplay cross-checks; no duration grammar; no name-content
  check beyond str-ness.
- **Caching**: none (pure functions; per-compile construction).
- **Concurrency**: not applicable (single-threaded pure transforms; the
  `FlowVerify` object shared across loop copies is read-only after build and
  deep-copied at assembly).

## Usages Analysis

### `convention` (.goga/usages/conventions.md)

- **What it provides**: Python rules — dataclasses with `kw_only=True`,
  relative intra-package imports, Google docstrings, test layout mirroring
  the source tree, boundary parametrized tests.
- **Where used**: every new/changed module and test.
- **Why chosen**: mandatory project practice.
- **How exactly**: `@dataclass(kw_only=True)` models; `from .workflow_gates
  import WorkflowGates` style imports; `tests/pipeline/<cell>/test_*.py`
  mirroring; `pytest.raises(..., match=...)` for every strict error.

### `beautiful_yaml` (.goga/usages/cooks/beautiful_yaml.md)

- **What it provides**: the `yaml.dump` parameter set used by
  `serialize_flow`.
- **Where used**: `serialize_flow` (unchanged call); the verify emission
  rides the same dumper — plain scalars for settings, `_BlockLiteralScript`
  for multi-line step strings, no new representer.
- **Why chosen**: the canonical serializer defaults.
- **How exactly**: as in the existing code; the new helpers only build
  ordered dicts/lists.

### `afm` (.goga/usages/cooks/afm.md) — GAP, rider of the implementation task

- **What it provides**: the external engine's CLI/flow contract.
- **Where used**: `compile_flow`/`serialize_flow` gates emission ("Use `afm`
  for the emitted verify contract").
- **Gap**: the file documents assistants, memory, repeat, hooks — but NOT the
  verify contract. The compiler annotations reference it for verify, so the
  fact base must land with the implementation (task.md item 7, the
  assistants-ADR precedent; arch.md records it as a rider). The verified
  facts to add are in the trace "Engine verify boundary" above (both goga
  authoring forms, step fields, container settings, exclusions, name
  grammar, strict JSON verdicts, stalemate/ceiling rules, downgrade
  behavior). The design consumes them; the implementation writes them.
- **How exactly (design side)**: emission shapes and prohibitions are
  verified against the published docs (see the table); nothing outside the
  documented contract is emitted.

### Imported Usages

- `gates` from `goga/pipeline/workflow` —
  Path: `goga/pipeline/workflow/.usages/gates.md` (exists; updated with the
  prompt binding). The authoring vocabulary of the consumed instructions;
  referenced by the compiler header Annotations and `compile_flow`
  Requirements/Constraints — a traceable cross-cell link, not a contractual
  obligation.
- `parse-workflow` from `goga/pipeline/workflow` — the parser surface
  overview (gates rows/sections present).
- `memory`, `assistants` from `goga/pipeline/workflow` — existing precedents
  (block carriage; attachment compilation) referenced by the same header.

## `.usages/` Update

### Cell: `goga/pipeline/workflow`

#### Existing Files — Consistency

- **`gates.md`** → `goga/pipeline/workflow/.usages/gates.md`
  - Status: current (created by apply-architecture; the prompt-binding row
    and error line added by this stage per the user-approved fix).
  - Additions needed: none beyond the applied fix.
- **`parse-workflow.md`** → same directory
  - Status: current (top-level key list, per-stage table row, gates section;
    prompt-binding notes added by this stage).

#### New Files

None beyond `gates.md` (already created; single functional domain).

### Cell: `goga/pipeline/compiler`

- **`compile-flow.md`**, **`serialize-flow.md`** — current (gates section,
  verify emission section, canonical lists carry `verify`). No further
  changes.

### Cell: `goga/pipeline/hooks`, Cell: `goga/pipeline`

No `.usages/` directories — nothing to update.

### Rider (implementation task, not cell `.usages/`)

`docs/features/pipelines/workflows.md` gains the user-facing "Quality gates
(`gates`)" section (authoring vocabulary, engine-vocabulary mapping, timeout
default, combination/exclusion rules, worked example that compiles as
documented); `.goga/usages/cooks/afm.md` gains the verify fact base.

## Test Stack Trace

### General Setup

- Pure functions — no mocks, no filesystem except `tmp_path` for
  `compile_flow` (pipeline-file in, flow-file out).
- Pipeline-file fixtures: STAGES-format text constants (the
  `test_compile_flow_memory.py` pattern). Workflow fixtures:
  `parse_workflow(text)` or direct model construction.
- Assertions on serialized flow text use exact substrings (`"\n  - name:
  …\n"` blocks) — the established slot-test style.

### Source File Registry

- New: `goga/pipeline/workflow/workflow_gates.py`,
  `workflow_gate_step.py`; `goga/pipeline/compiler/flow_verify.py`,
  `flow_verify_step.py`.
- Changed: `parse_workflow.py`, `workflow_stage.py`,
  `workflow_document.py`, `workflow/__init__.py`;
  `compile_flow.py`, `serialize_flow.py`, `compiler/__init__.py`;
  `hooks/overlay.py`, `hooks/events.py`, `hooks/amendments.py`;
  `apply_skip_stages.py`.
- Test files (new): `tests/pipeline/workflow/test_workflow_gates_contract.py`,
  `test_workflow_gate_step_contract.py`, `test_parse_workflow_gates.py`;
  `tests/pipeline/compiler/test_flow_verify_contract.py`,
  `test_flow_verify_step_contract.py`, `test_compile_flow_gates.py`,
  `test_serialize_flow_verify_slot.py`;
  `tests/pipeline/hooks/test_overlay_gates.py`.
  Extended: `tests/pipeline/test_apply_skip_stages.py`,
  `tests/pipeline/hooks/test_events.py` (the gates-only contribution
  commits — the emptiness enumeration counts the gates block),
  `tests/pipeline/workflow/test_workflow_stage_contract.py`,
  `test_workflow_document_contract.py`,
  `tests/pipeline/compiler/test_compile_flow.py` (the canonical order
  constant pin gains `"verify"` after `"assistants"`; the
  `_canonical_fields` signature pin gains `verify_fields` — last parameter,
  default None),
  `test_serialize_flow.py` (fields docstring/order pin if it pins the list).

---

### Positive Tests

#### `test_parse_workflow_gates.py::test_gates_settings_block_alone_is_valid`

**Setup**: none (pure parse).

**Input**: `"gates:\n  patience: 1\n"`.

**Trace**:
```
parse_workflow(text)
  → yaml.safe_load               # {"gates": {"patience": 1}}
  → _extract_top_level           # gates_raw = {"patience": 1}
  → _build_gates                 # int >= 0, not bool → ok
    returns: WorkflowGates(patience=1, max_iterations=None, fresh_correction=None)
  → empty-workflow check         # gates is None? NO → not empty
  → WorkflowDocument(gates=WorkflowGates(patience=1))
```

**Assertions**:
```
doc.gates is not None
doc.gates.patience == 1
doc.gates.max_iterations is None
doc.gates.fresh_correction is None
doc.prompt is None and doc.stages == {}     # block alone is valid content
```

**Sufficiency**: pins the empty-workflow rule extension — a gates-only
workflow must not raise (PRD requirement 5; regression: dropping the `and
gates is None` clause breaks gates-only authoring).

#### `test_parse_workflow_gates.py::test_stage_gates_steps_built_in_authored_order`

**Setup**: none.

**Input**:
```yaml
stages:
  implement:
    prompt: Do it
    gates:
      - name: Unit tests
        script: pytest -q
        timeout: 30m
      - name: Code review
        agent: codex
        prompt: Review the diff for correctness.
```

**Trace**:
```
parse_workflow(text)
  → _build_stage("implement", {...})
    → _validate_stage_field("implement", "gates", [...])
      → _build_stage_gates: step 0 script-form ok; step 1 agent-form ok
        returns: [WorkflowGateStep(name="Unit tests", script="pytest -q", timeout="30m"),
                  WorkflowGateStep(name="Code review", agent="codex", prompt="Review the diff…")]
  → WorkflowStage(gates=[…2 steps…])
```

**Assertions**:
```
doc.stages["implement"].gates is not None
len(doc.stages["implement"].gates) == 2
doc.stages["implement"].gates[0].name == "Unit tests"
doc.stages["implement"].gates[0].script == "pytest -q"
doc.stages["implement"].gates[0].timeout == "30m"
doc.stages["implement"].gates[1].agent == "codex"
doc.stages["implement"].gates[1].prompt == "Review the diff for correctness."
```

**Sufficiency**: authored-order preservation and verbatim carriage — the
compiled gate's step order is contract-critical (fail-fast semantics ride
on it).

#### `test_parse_workflow_gates.py::test_empty_settings_block_and_empty_list_equal_absence`

**Setup**: none.

**Input**: `"gates: {}\nstages:\n  a:\n    gates: []\n    prompt: x\n"`.

**Trace**: `_build_gates({})` → `None`; `_build_stage_gates("a", [])` →
`None` → `WorkflowStage(gates=None)`, `WorkflowDocument(gates=None)` — the
`prompt: x` keeps the workflow non-empty.

**Assertions**:
```
doc.gates is None
doc.stages["a"].gates is None
```

**Sufficiency**: the byte-identical invariant's parse-side anchor —
emptiness must normalize to `None` so nothing downstream emits.

#### `test_compile_flow_gates.py::test_gated_stage_compiles_verify_with_steps_and_materialized_timeout`

**Setup**: `tmp_path`; STAGES pipeline with one stage `build` (prompt-only).

**Input**: workflow text with `gates: [build: [name: compile, script: make
all]]` (no settings block), applied via `parse_workflow` → `compile_flow`.

**Trace**:
```
compile_flow(pipeline_path, flow_path, workflow=doc)
  → _reconstruct_body → effective gates for "build" = [WorkflowGateStep(name="compile", script="make all")]
  → _gates_emission: body has no script key; agents default ≠ ["planning"] → ok
    FlowVerifyStep(name="compile", run="make all", timeout="1h")   # materialized default
    FlowVerify(steps=[…])                                          # no settings → list form
  → _canonical_fields(verify_fields=FlowVerify) → fields["verify"] after "assistants" slot
  → serialize_flow → _verify_repr → list form
```

**Assertions** (exact substrings of the flow text; the canonical dumper
aligns a block-sequence dash with its parent key and puts stage fields at
2 spaces — verified against the dumper parameters, the shipped flow.yml,
and the buttons slot-test style):
```
"verify:\n" in text
"  - name: compile\n" in text
"    run: make all\n" in text
"    timeout: 1h\n" in text
text.index("verify:") > text.index("prompt:")      # canonical slot after known keys
"max_failures" not in text                          # list form — no settings
```

**Sufficiency**: the headline compile behavior — 1h materialization, list
form, canonical slot; regression: emitting `timeout` only when authored, or
the container form unconditionally, breaks the engine contract.

#### `test_compile_flow_gates.py::test_ai_step_command_composed_from_agent_wrapper_path`

**Setup**: `tmp_path`; one prompt stage `review`.

**Input**: workflow with `stages: {review: {gates: [{name: Check, agent:
codex, prompt: "Be strict.", timeout: 15m}]}}`.

**Trace**: `_gates_emission` → `FlowVerifyStep(name="Check",
command="/home/goga/bin/codex-as-claude.sh", timeout="15m", prompt="Be
strict.")` (no default timeout materialized — authored one verbatim).

**Assertions**:
```
"- name: Check\n" in text
"command: /home/goga/bin/codex-as-claude.sh\n" in text
"timeout: 15m\n" in text
"prompt: 'Be strict.'\n" in text or "prompt: Be strict.\n" in text   # per dumper quoting
```

**Sufficiency**: the ADR decision 2 — composition mirrors the per-stage
agent override; no existence checks, no host-side resolution.

#### `test_compile_flow_gates.py::test_settings_block_authors_container_form_on_every_gated_stage`

**Setup**: `tmp_path`; two prompt stages `a`, `b`; both gated; settings
`gates: {max_iterations: 2, fresh_correction: true}`.

**Trace**: `_gates_emission` builds per stage
`FlowVerify(steps, max_failures=2, fresh_correction=True,
review_patience=None)` → container form; `review_patience` absent
(authored keys only).

**Assertions**:
```
text.count("steps:\n") == 2
"max_failures: 2\n" in text
"fresh_correction: true\n" in text
"review_patience" not in text            # unauthored key never materializes
```

**Sufficiency**: settings ride ONLY on gated stages, authored keys only —
the no-materialized-defaults rule (gates settings block alone must remain
inert — covered by the negative test below).

#### `test_compile_flow_gates.py::test_loop_expanded_copies_carry_the_same_gate`

**Setup**: `tmp_path`; stage `check` with `loop: 2` and a gate step.

**Trace**: `_expand_loops` produces `check-1`, `check-2`;
`_gates_emission` maps the same `FlowVerify` onto both ids; both
`_canonical_fields` calls assemble `verify` (deep-copied per stage).

**Assertions**:
```
text.count("verify:\n") == 2             # both copies gated
"- id: check-1\n" in text and "- id: check-2\n" in text
```

**Sufficiency**: uniform application across loop copies (task lifecycle
invariant 5).

#### `test_serialize_flow_verify_slot.py::test_verify_list_form_is_the_steps_list`

**Setup**: direct `FlowDocument` construction (the repeat-slot test pattern).

**Input**: `FlowStage(fields={"prompt": "Do", "verify": FlowVerify(steps=[
FlowVerifyStep(name="t", run="pytest")]})})`.

**Trace**: `_build_stage_repr` → `_verify_repr` → no authored setting →
`[{"name": "t", "run": "pytest"}]` → YAML list under `verify:`.

**Assertions**:
```
"verify:\n" in text and "steps:" not in the verify block   # list, not container
"- name: t\n" in text
```

**Sufficiency**: the engine list form — an instance with no setting must
serialize as the bare steps list (the `FlowVerify` contract note).

#### `test_serialize_flow_verify_slot.py::test_verify_container_form_fixed_order_and_multiline_prompt`

**Setup**: direct construction.

**Input**: `FlowVerify(steps=[FlowVerifyStep(name="r", command="/x/y.sh",
prompt="line1\nline2")], max_failures=3, review_patience=1)`.

**Trace**: `_verify_repr` → `{"steps": […], "max_failures": 3,
"review_patience": 1}`; the multi-line `prompt` wrapped in
`_BlockLiteralScript` → block-literal `|` scalar.

**Assertions** (same indentation discipline — `steps:` nested one level
under `verify:` at 4 spaces, its list dashes aligned at 4, step fields at 6):
```
"verify:\n    steps:\n" in text
"    max_failures: 3\n" in text
"    review_patience: 1\n" in text
text.index("steps:") < text.index("max_failures:") < text.index("review_patience:")
"      prompt: |\n" in text
```

**Sufficiency**: container key order and the script-family scalar style —
canonical output stability (byte-level golden comparisons across releases).

#### `test_overlay_gates.py::test_authored_settings_block_unbeatable_and_stage_gates_fill`

**Setup**: pure models.

**Input**: `base = WorkflowDocument(gates=WorkflowGates(patience=1),
stages={"a": WorkflowStage(gates=[step])})`; one contribution with
`gates=WorkflowGates(max_iterations=9)` and `stages={"b":
WorkflowStage(gates=[other_step])}`.

**Trace**: `_merge_gates` — authored block kept; stage merge — authored
`a.gates` kept, fresh `b` arrives with its list.

**Assertions**:
```
overlay.workflow.gates.patience == 1
overlay.workflow.gates.max_iterations is None      # no field-level merge
overlay.workflow.stages["a"].gates == [step]
overlay.workflow.stages["b"].gates == [other_step]
```

**Sufficiency**: overlay preservation — an amended run never loses authored
gates (task lifecycle invariant 12).

#### `test_events.py::test_gates_only_contribution_is_not_empty`

**Setup**: the `test_repeat_only_contribution_is_not_empty` shape — a
registered tool hook buffers `WorkflowAmendment.contribute(
WorkflowDocument(gates=WorkflowGates(max_iterations=1)))`; `caplog` watches
the `"tool contributed an empty document; discarded"` warning.

**Input**: `PipelineHooks.amend_workflow(...)` with `workflow=None` and the
one subscribed tool.

**Trace**: walk → the buffer is not `None` → the duck-check reads every fact
(`gates` included) → the emptiness check: prompt None, stages {}, extend {},
memory None, assistants {}, delegation None, repeat None, **gates is not
None** → NOT empty → commits as a `ToolContribution` →
`merge_workflow_overlay` builds the document carrying `gates`.

**Assertions**:
```
overlay.workflow is not None
overlay.workflow.gates.max_iterations == 1
not [r for r in caplog.records if r.message == "tool contributed an empty document; discarded"]
```

**Sufficiency**: pins the events-level emptiness enumeration — without the
`and document.gates is None` clause a gates-only tool delivery is silently
discarded (the contribution drops, `overlay.workflow` stays `None`) and this
test fails; the hooks contract Requirement is exercised on the level that
owns the rule (the merge itself never discards).

#### `test_overlay_gates.py::test_gates_only_contribution_rides_the_merge`

**Setup**: pure models; `merge_workflow_overlay(None, [ToolContribution(
tool="t", document=WorkflowDocument(gates=WorkflowGates(max_iterations=1)))])`.

**Trace**: the merge-level carriage — no authored base → the later
contributing tool's block rides the rebuilt document (4d).

**Assertions**:
```
overlay.workflow is not None
overlay.workflow.gates.max_iterations == 1
```

**Sufficiency**: the merge carries the gates block through the document
rebuild (a rebuild omitting `gates=` drops it) — the emptiness rule itself
is covered at the events level above.

#### `tests/pipeline/test_apply_skip_stages.py::test_settings_block_survives_skip_rebuild`

**Setup**: pure models.

**Input**: `workflow = WorkflowDocument(gates=WorkflowGates(max_iterations=4),
stages={"a": WorkflowStage(prompt="x"), "gone": WorkflowStage(skip=True,
gates=[step])})`; `skip_stages=["gone"]`.

**Trace**: step 3 replacement `WorkflowStage(skip=True, assistants=None)`
→ `gates=None` (default); step 4 rebuild carries `gates` verbatim.

**Assertions**:
```
merged.gates is workflow.gates                  # same object, verbatim
merged.stages["gone"].gates is None             # replacement carries no gates
```

**Sufficiency**: skip-driven runs keep retry tuning for remaining gated
stages; the skipped stage's checks drop silently.

---

### Negative Tests

#### `test_parse_workflow_gates.py::test_every_structural_error_message` (parametrized)

**Setup**: none.

**Input** (parametrized table — workflow text, expected message):

```
"gates: 5"                                  → "non-mapping gates block in workflow"
"gates: {patiance: 1}"                      → "unknown key in workflow.gates: patiance; valid keys: patience, max_iterations, fresh_correction"
"gates: {patience: true}"                   → "non-int value in workflow.gates.patience"
"gates: {max_iterations: -1}"               → "max_iterations must be >= 0 in workflow.gates"
"gates: {fresh_correction: 1}"              → "non-bool value in workflow.gates.fresh_correction"
"stages: {a: {gates: {name: x}}}"           → "non-list gates in workflow.stages.a"
"stages: {a: {gates: [pytest]}}"            → "non-mapping gate step in workflow.stages.a.gates[0]"
"stages: {a: {gates: [{script: x}]}}"       → "gates step without name in workflow.stages.a.gates[0]"
"stages: {a: {gates: [{name: 1, script: x}]}}" → "non-str value in workflow.stages.a.gates[0].name"
"stages: {a: {gates: [{name: x}]}}"         → "gates step must carry exactly one of script/agent in workflow.stages.a.gates[0]"
"stages: {a: {gates: [{name: x, script: y, agent: z}]}}" → "gates step must carry exactly one of script/agent in workflow.stages.a.gates[0]"
"stages: {a: {gates: [{name: x, script: \"\"}]}}" → "script must be a non-empty string in workflow.stages.a.gates[0]"
"stages: {a: {gates: [{name: x, script: y, timeout: 5}]}}" → "non-str value in workflow.stages.a.gates[0].timeout"
"stages: {a: {gates: [{name: x, script: y, prompt: z}]}}" → "prompt is forbidden on a script gate step in workflow.stages.a.gates[0]"
"stages: {a: {gates: [{name: x, agent: y, extra: 1}]}}" → "unknown key in workflow.stages.a.gates[0]: extra; valid keys: name, script, agent, timeout, prompt"
"extend: {n: {after: [a], gates: [...]}}"   → "gates is forbidden in workflow.extend.n"
```

**Trace**: `parse_workflow(text)` → the specific validator raises on the
first defect.

**Assertions**: `with pytest.raises(WorkflowSyntaxError, match=re.escape(msg))`.

**Sufficiency**: the strict one-line error surface is the product's
usability contract (PRD failure scenarios; every case from the plan).
The `agent` counterparts (`agent must be a non-empty string…`,
`non-str … .prompt` on an agent step) join the same table.

#### `test_compile_flow_gates.py::test_gates_on_script_stage_rejected`

**Setup**: `tmp_path`; pipeline stage `s` with `script: make check` (script
stage).

**Input**: workflow `stages: {s: {gates: [{name: g, script: pytest}]}}`.

**Trace**: `_gates_emission` → body carries `script` → `StructuralError`.

**Assertions**: `pytest.raises(StructuralError, match="gates are forbidden
on a script stage in workflow.stages.s")`.

**Sufficiency**: the engine rejects gates on script stages; goga surfaces
it pre-run with its own message (task product rule 14).

#### `test_compile_flow_gates.py::test_gates_on_planning_only_stage_rejected`

**Setup**: `tmp_path`; stage with `roles: [planner]`.

**Input**: workflow gating that stage.

**Trace**: `_translate_body_agents(body) == ["planning"]` (the alias
translated) → `StructuralError("gates are forbidden on a planning-only
stage in workflow.stages.p")`.

**Assertions**: `pytest.raises(StructuralError, match="gates are forbidden
on a planning-only stage in workflow.stages.p")` — plus a twin case with
`roles: [planning]` (already-afm name) proving the translated comparison.

**Sufficiency**: same engine exclusion, translated-agents semantics (the
attachment-check precedent).

#### `test_compile_flow_gates.py::test_gates_and_verify_keys_forbidden_in_stage_body` (parametrized)

**Setup**: `tmp_path`; pipeline stage bodies carrying `gates: []` / `verify:
"make test"` respectively (also one embedded in an extend-entry body).

**Input**: compile with a trivial workflow.

**Trace**: `_canonical_fields` → `_reject_authoring_output_keys` →
`StructuralError`.

**Assertions**:
```
match="gates key is forbidden in stage body; use gates in workflow.stages"
match="verify key is forbidden in stage body; use gates in workflow.stages"
```

**Sufficiency**: closes the accidental raw-`verify` passthrough (ADR
decision 5) — today such a key reaches the engine unvalidated.

#### `test_compile_flow_gates.py::test_settings_block_alone_compiles_inert`

**Setup**: `tmp_path`; plain ungated pipeline.

**Input**: workflow = `gates: {patience: 2}` only.

**Trace**: no stage has effective gates → `verify_by_id == {}` → nothing
assembled.

**Assertions**:
```
"verify" not in flow_text        # no error, no key
```

**Sufficiency**: the inert-settings-block rule (the memory shape).

---

### Edge Case Tests

#### `test_compile_flow_gates.py::test_gate_free_workflow_compiles_byte_identically`

**Setup**: `tmp_path`; any pipeline + a workflow without gates.

**Input**: compile; compare against the expected flow text (golden string
verbatim from the pre-feature output).

**Trace**: `gates=None` everywhere → no emission, no canonical slot, no
serializer arm.

**Assertions**: `flow_text == EXPECTED_UNCHANGED` (full-string equality).

**Sufficiency**: the lifecycle invariant 11/PRD 10 — byte-identical output
(no `verify` key anywhere, no other key affected).

#### `test_compile_flow_gates.py::test_malformed_timeout_passes_verbatim`

**Setup**: `tmp_path`; gated shell step with `timeout: "30x"` (invalid Go
duration).

**Trace**: parser checks str only → `FlowVerifyStep(timeout="30x")` →
serialized verbatim.

**Assertions**: `"timeout: 30x" in flow_text` (no goga error).

**Sufficiency**: the validation boundary — value grammar is engine-owned
(the `script_timeout` precedent); a regression here would grow a duration
parser into goga.

#### `test_compile_flow_gates.py::test_extend_plus_stages_entry_keeps_gate`

**Setup**: `tmp_path`; pipeline stage `x`; workflow `extend: {x: {after:
[a], agent: codex}}` AND `stages: {x: {gates: [step]}}`.

**Trace**: `_effective_overrides` merged branch — `gates=stg.gates` passed
explicitly → gate survives (the omission would silently drop it).

**Assertions**: `"verify:" in flow_text` (and the composed `command` from
the inline extend agent also present).

**Sufficiency**: pins the contract Requirement added for the effective
merge — the exact silent-drop failure mode the task warns about.

#### `test_parse_workflow_gates.py::test_authored_zero_is_a_value`

**Setup**: none.

**Input**: `"gates: {patience: 0, max_iterations: 0}\n"`.

**Trace**: bounds check `>= 0` passes; model keeps `0`.

**Assertions**: `doc.gates.patience == 0 and doc.gates.max_iterations == 0`
(both `is not None`).

**Sufficiency**: authored zero vs absence distinguishability (strict
budget / disabled stalemate — engine semantics goga must not collapse).

#### Model contract tests (four files, the `test_flow_repeat_contract.py`
pattern)

- `test_workflow_gates_contract.py` / `test_workflow_gate_step_contract.py`
  / `test_flow_verify_contract.py` / `test_flow_verify_step_contract.py`:
  facade importability + `__all__` membership, `is_kw_only_dataclass`, fixed
  field order via `dataclasses.fields` (`WorkflowGateStep`: name, script,
  agent, timeout, prompt; `FlowVerify`: steps, max_failures, review_patience,
  fresh_correction), defaults (`None`; `steps` required —
  `pytest.raises(TypeError)` on missing), authored-zero preservation.
- `tests/pipeline/workflow/test_workflow_stage_contract.py` and
  `test_workflow_document_contract.py`: extend the field-order pins with
  `gates` (last).
- `tests/pipeline/compiler/test_compile_flow.py`: `_CANONICAL_KEY_ORDER`
  pin gains `"verify"` after `"assistants"`.

**Sufficiency**: the public API surface declared by the CODEMANIFESTs
(facade obligation) and the emission-order guarantees.

## Additional Instructions for the Implementation Agent

- Implement in cell order **workflow → compiler → hooks → pipeline**; after
  each cell run `pytest tests/pipeline/<cell> -x` and `ruff check goga/`;
  finish with the full `pytest tests/ -x` and `ruff`.
- New modules get module + Google docstrings per `convention`; relative
  imports only; models via `@dataclass(kw_only=True)`.
- Facade exports: workflow gains `WorkflowGateStep`, `WorkflowGates`
  (import list and `__all__`, ASCII order: `WorkflowGateStep` before
  `WorkflowGates`, after `WorkflowExtendStage`); compiler gains `FlowVerify`,
  `FlowVerifyStep` (after `FlowTeamMember`, before `PhaseStep`).
- Exact error texts are normative: every parser message from contract steps
  4/5/6.1.2/6.1.15/6.10/6.11/7 (quoted in the traces above), the two
  compiler body-key prohibitions, and the two design-fixed script/planning
  messages (`gates are forbidden on a script stage in
  workflow.stages.{name}` / `…planning-only…`).
- Do not modify: `PipelineDocument`, the pipeline-file parsing, existing
  instructions' semantics, the engine (external), or unrelated files (the
  working tree carries an unrelated `goga.css` change — leave it alone).
- Byte-identical guarantee: a gate-free workflow (and empty gates blocks)
  must compile to byte-identical output — assert with full-string golden
  comparisons, not key-subset checks.
- Riders landing with the implementation task (from task.md item 7): the
  user-facing "Quality gates (`gates`)" section in
  `docs/features/pipelines/workflows.md` (vocabulary, engine mapping table,
  timeout default, combination/exclusion rules, worked example that compiles
  as documented), and the engine verify fact base in
  `.goga/usages/cooks/afm.md` — use the verified facts recorded in the
  "Engine verify boundary" trace above; note `.goga/usages/cooks/*` are
  synced usage files managed by `goga usages sync` — follow the assistants
  precedent for how the fact base was added there.
- Engine-version assumption: the feature assumes an engine whose verify
  contract matches the published documentation; older engines reject a
  gated flow at load/preflight (documented downgrade behavior, not silent).
  If implementation contradicts any verified fact above, stop and update
  the afm cook + this design rather than silently diverging.
