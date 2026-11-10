# Design Document: `recycle-pipeline`

Complete implementation design for the two authoring-surface changes of
`.goga/history/2026/recycle-pipeline/` — the repeating run cycle
(`repeatable` pipeline flag + workflow `repeat` block) and the map-form
assistants authoring. Derived from the CODEMANIFEST changes materialized by
the apply-architecture stage (plan: `.goga/history/2026/recycle-pipeline/
arch.md`; ADR: `adr.md`, normative). The CODEMANIFEST set is the contract
source of truth; this document specifies **what to implement and how**, at
the level of concrete files, routines, message strings, and tests. No
implementation code is written here.

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/pipeline/workflow/CODEMANIFEST`: `WorkflowRepeat` (new type),
  `WorkflowDocument` (+`repeat`), `WorkflowStage` (`assistants`
  `list` → `dict`), `WorkflowAssistant` (name/when rewording for the map
  form), `parse_workflow` (top-level `repeat`, catalog/attachment map
  grammars, empty-workflow rule), global annotations, footer.
- `goga/pipeline/compiler/CODEMANIFEST`: `WorkflowRepeat` import (the
  single import delta), `FlowRepeat` (new type), `PipelineHeader`
  (+`repeatable`), `parse_dsl` (+`repeatable` extraction), `FlowDocument`
  (+`repeat`), `compile_flow` (step 4.0 cross-check, step 4.10 map
  wording, step 6 repeat bullet, requirements/constraints), `serialize_flow`
  (repeat emission), global annotations, footer.
- `goga/pipeline/hooks/CODEMANIFEST`: `merge_workflow_overlay` (step 4c
  repeat merge, step 5a/8 map wording, requirements/constraints),
  `WorkflowAmendment.contribute` (emptiness counts `repeat`), global
  annotations (overlay paragraph).
- `goga/pipeline/CODEMANIFEST`: `apply_skip_stages` (step 3 assistants-map
  carry, step 4 `repeat` verbatim carry, survival requirement).

### New Entities

- `WorkflowRepeat(max_cycles: int | None = None, keep_runs: int | None = None)`
  — `goga/pipeline/workflow/workflow_repeat.py` (new file). Data model of
  the authored run-cycle tuning block; authored values only.
- `FlowRepeat(max_cycles: int | None = None, keep_runs: int | None = None)`
  — `goga/pipeline/compiler/flow_repeat.py` (new file). Emitted top-level
  repeat directive; an instance carrying no authored key IS the scalar
  form.

### Changed Entities

- `WorkflowStage.assistants`: `list[WorkflowAssistant] | None` →
  `dict[str, WorkflowAssistant] | None` (name-keyed, authored order).
- `WorkflowDocument.repeat`: new field `WorkflowRepeat | None = None`
  (after `delegation`; last field).
- `PipelineHeader.repeatable`: new field `bool = False` (after `roles`).
- `FlowDocument.repeat`: new field `FlowRepeat | None = None` (between
  `description` and `memory` — the canonical emission order).
- `parse_workflow`, `parse_dsl`, `compile_flow`, `serialize_flow`,
  `merge_workflow_overlay`, `WorkflowAmendment.contribute` (via the
  `PipelineHooks` delivery), `apply_skip_stages`: algorithm/annotation
  changes per the manifests.

### Deleted Entities

None.

### Usages and Annotations Changes

- `.goga/usages/cooks/afm.md` — the `repeat` section (added at task
  formulation, user-approved): scalar/map forms, strict parse, goga's
  stance. Read-only for implementation.
- Cell `.usages/` files — all already rewritten/updated by the
  apply-architecture stage (see `.usages/` Update below); implementation
  keeps them consistent with the final behavior, no further edits planned.

## Applied Fixes

CODEMANIFEST defects found by the Phase 3 consistency audit and fixed in
this stage (user-approved, dialog q1):

### Fixed CODEMANIFEST Defects

- `goga/pipeline/hooks/CODEMANIFEST` (`PipelineHooks`, algorithm step 5):
  the empty-contribution enumeration lacked `repeat`, contradicting the
  updated `WorkflowAmendment.contribute` annotation and the plan checklist
  ("a `repeat`-only contribution is NOT empty"). Fixed: "… no assistants,
  no delegation, **and no repeat** — is a content no-op …". (Annotations ↔
  Entity consistency.)
- `goga/pipeline/compiler/CODEMANIFEST` (`compile_flow`, Requirements):
  "trigger from when (the checkpoints default written explicitly)" was
  stale — the compiler-side engagement default no longer exists (`when` is
  authored on every attachment). Fixed: "trigger from when (always written
  explicitly — when is authored on every attachment; the engine's one_shot
  default is never relied upon)". (Annotations ↔ Entity consistency; the
  backticks around `when` were dropped — an unresolvable reference in the
  compiler context, `annotation_links_exists`.)
- `goga/pipeline/compiler/CODEMANIFEST` (`FlowAssistant`, Requirements):
  "the checkpoints trigger is written explicitly" — same stale family.
  Fixed: "the trigger is written explicitly, never inherited from the
  engine default".

`goga lint` after the fixes: 91 cells, 0 errors.

## Entity Interaction and Data Flow

### Interaction Diagram

```
                          workflow-file                pipeline-file
                               │                            │
                               ▼                            ▼
                       parse_workflow                parse_dsl
                               │                            │
              WorkflowDocument │                    PipelineHeader
              ├ assistants: dict[str, WorkflowAssistant]   ├ repeatable: bool
              ├ delegation ────┘                            └────────┬─────────┐
              └ repeat: WorkflowRepeat | None                        │         │
                               │                                    │         │
        ┌──────────────────────┼──────────────────────────┐         │         │
        │ (tool amendments)    │ (CLI -s/--skip)          │         │         │
        ▼                      ▼                          ▼         ▼         ▼
  PipelineHooks.amend    apply_skip_stages            compile_flow(pipeline, flow, workflow, …)
  ├ emptiness counts …   ├ skip replacement carries    ├ 4.0 cross-check: workflow.repeat × header.repeatable
  │  repeat (events.py)  │  the pre-skip assistants map├ 4.1–4.10 reconstruction (assistants maps consumed)
  └ merge_workflow_…     └ repeat carried verbatim     ├ step 5 FlowStage assembly (assistants slot)
       ├ 4c repeat: authored-wins, whole              ├ step 6: repeat = _repeat_emission(header, workflow)
       └ 5a stage maps append with dedup               │         → FlowRepeat | None
                               │                       └ FlowDocument(prompt, root_dir, name, description,
                               │                            repeat, memory, collaboration, team, stages)
                               ▼                                     │
                        WorkflowOverlay                              ▼
                         (effective doc)                      serialize_flow
                                                             ├ repeat None → key omitted (byte-identical)
                                                             ├ no authored key → `repeat: true`
                                                             └ authored keys → block map, order fixed
                                                                   │
                                                                   ▼
                                                        afm run (single invocation; engine owns cycles)
```

### Data Flows

1. **Repeat authoring → compiled directive.** `repeat: {max_cycles: 3}`
   in the workflow-file → `parse_workflow` step 6.9 →
   `WorkflowRepeat(max_cycles=3, keep_runs=None)` on `WorkflowDocument` →
   survives `apply_skip_stages` (verbatim) and `merge_workflow_overlay`
   (whole-block, authored-wins) → `compile_flow` step 4.0 (cross-check
   passes: `header.repeatable` is True) → step 6 →
   `FlowRepeat(max_cycles=3, keep_runs=None)` → `serialize_flow` emits
   `repeat:\n  max_cycles: 3` between `description` and `memory`.
2. **Repeatable default.** `repeatable: true` header, workflow without a
   block (or `workflow=None`, or `--no-workflow`) →
   `WorkflowDocument.repeat is None` → `compile_flow` step 6 builds
   `FlowRepeat()` (no authored key) → `serialize_flow` writes the scalar
   `repeat: true`.
3. **Cross-check failure.** non-repeatable header + workflow `repeat`
   block → `compile_flow` step 4.0 raises `StructuralError("workflow
   repeat block requires a repeatable pipeline; author repeatable: true
   in the pipeline header")` before any reconstruction.
4. **Map-form assistants → engine list.** catalog + attachments as
   name-keyed maps → `WorkflowAssistant` per entry (name = map key) →
   `_effective_overrides` carries the stage map verbatim →
   `_assistant_namespace` (catalog ∪ inline declarations) →
   `_assistants_by_id` resolves references and builds the engine-facing
   `FlowAssistant` list in authored key order → `_canonical_fields`
   assembles the `assistants` slot → `serialize_flow` writes the list of
   mappings — **output shape unchanged** versus the old list-form
   authoring.
5. **Tool contribution of repeat.** A tool's `WorkflowDocument` carrying
   only `repeat` → `PipelineHooks` delivery: not empty (counts) →
   `merge_workflow_overlay` step 4c: applies only when the authored base
   has no block; later tools win among contributions.

### Entity Dependencies

Implementation order (leaf → root, one commit-surface per cell):

1. `goga/pipeline/workflow` — models first (`workflow_repeat.py`,
   `workflow_stage.py`, `workflow_document.py`,
   `workflow_assistant.py` docstrings, facade), then
   `parse_workflow.py`.
2. `goga/pipeline/compiler` — models (`flow_repeat.py`,
   `pipeline_header.py`, `flow_document.py`, facade), then
   `parse_dsl.py`, then `compile_flow.py`, then `serialize_flow.py`.
3. `goga/pipeline/hooks` — `overlay.py`, `events.py`.
4. `goga/pipeline` — `apply_skip_stages.py`, `afm_config.py`
   (mechanical map adaptation).

Consumers outside the four cells are untouched: `goga/build` imports
`WorkflowBuild`/`LoadedWorkflow` (unchanged); `goga/commands/*` import
usages and `load_home_profiles` (unchanged).

## Code Stack Trace

### Trace: `parse_workflow(text)` — repeat block

#### Chain

1. **Input**: rendered workflow-file text (rendering happened in
   `load_workflow`; `parse_workflow` accepts text only).
2. `yaml.safe_load(text)`; a scanner error → `WorkflowSyntaxError(
   "invalid YAML in workflow-file")`; a non-dict root →
   `"workflow must be a mapping"`. → checkpoint: unchanged behavior.
3. `_extract_top_level(loaded)` — the `for key, value` loop gains a
   `repeat` branch: `repeat_raw = _validate_top_level_mapping(
   "non-mapping repeat block in workflow", value)`. A scalar
   (`repeat: true`, `repeat: false`, `repeat: 5`), a list, or a string
   fails the mapping check with exactly that message. The unknown-key
   else-branch now lists `repeat` (the message is built from
   `_TOP_LEVEL_KEYS`, which gains `"repeat"`). The return arity becomes a
   9-tuple with `repeat_raw` appended. → checkpoint: message strings and
   arity verified against contract step 4.
4. `_build_repeat(repeat_raw)` (new routine; see Algorithm Design) →
   `WorkflowRepeat | None`; an empty `{}` yields `None`. → checkpoint:
   `None`-vs-zero distinction preserved (`max_cycles: 0` is a value).
5. Empty-workflow rule: the conjunction gains `and repeat is None`; the
   message enumeration gains "… the delegation block, or the repeat
   block". A `repeat:`-only workflow passes; a `profile:`-only workflow
   still raises. → checkpoint: contract step 7 message verbatim.
6. **Output**: `WorkflowDocument(..., delegation=delegation,
   repeat=repeat)` — the new ninth construction argument.

#### Checkpoint Summary

- Type flow `repeat_raw: dict | None` → `WorkflowRepeat | None`: passed.
- Boolean-vs-int: `_build_repeat` rejects `True`/`False` values as
  non-int (a `bool` is an `int` subclass in Python — the check must be
  `isinstance(v, bool) or not isinstance(v, int)`, the existing
  `_validate_delegation_bound` pattern): passed (design adopts the
  pattern).
- Empty-map convention (`{}` == absence): passed.

### Trace: `parse_workflow(text)` — map-form assistants

#### Chain

1. **Input**: the raw `assistants` top-level value (now required to be a
   mapping) and each stage entry's `assistants` value.
2. `_extract_top_level` `assistants` branch: replaced
   `_validate_top_level_list("non-list assistants block in workflow",
   value)` with `_validate_top_level_mapping("non-mapping assistants
   block in workflow; author the map form keyed by assistant name",
   value)` — the hard-transition error naming the map form. → checkpoint:
   a list-form catalog now fails here with the rename error (project
   precedent: `agents` → `roles`).
3. `_build_assistant_catalog(assistants_raw)` iterates
   `assistants_raw.items()` (was: list elements). Each entry value must
   be a dict → `"non-mapping assistant entry in workflow.assistants.NAME"`.
   Field validation via `_validate_catalog_field` over the reduced key
   constant `_ASSISTANT_CATALOG_KEYS = ("prompt", "skills", "agent",
   "delegate", "env")` — `name`, `gate`, `when` all fall to the
   unknown-key error `"unknown key in workflow.assistants.NAME: KEY;
   valid keys: prompt, skills, agent, delegate, env"`. At-least-one rule
   (presence, not truthiness — `skills: []` satisfies). Name grammar via
   `_validate_assistant_name` (gains a non-`str` guard: a YAML key like
   `123:` raises `"invalid assistant name: 123"` instead of a
   `TypeError` from `re.fullmatch`). Builds
   `WorkflowAssistant(name=<map key>, …)`. → checkpoint: an in-catalog
   duplicate cannot occur (a dict key is unique; duplicate YAML keys
   collapse at `safe_load` before the parser sees them — the same
   convention as the `stages`/`env` maps); the document-wide namespace
   check below still guards cross-surface duplicates.
4. `_build_stage_assistants(stage, value)` (contract 6.7): value must be
   a dict → `"non-mapping assistants in workflow.stages.NAME; author the
   map form keyed by assistant name"` (the bare-string and list forms die
   here — the hard transition). Empty map → `None`. Per
   `(key, entry_value)`: `entry_value` must be a dict → `"non-mapping
   assistant attachment in workflow.stages.NAME.ASSISTANT"`. `when` is
   required — the missing-key check runs for BOTH forms before building:
   `"when is required in workflow.stages.NAME.assistants.ASSISTANT"`
   (an empty entry value `{}` is a reference missing `when` and raises).
   Discrimination: `set(entry_value) <= {"gate", "when"}` → reference
   (gate bool check; `when` domain check via `_validate_when`); any
   further key → full inline declaration (`_validate_attachment_field`
   over `_ATTACHMENT_DECLARATION_KEYS = (*_ASSISTANT_CATALOG_KEYS,
   "gate", "when")` — the constant shrinks automatically when the
   catalog constant drops `name`; unknown-key error lists the seven
   valid keys), plus the at-least-one rule. Builds
   `WorkflowAssistant(name=<map key>, …)`; the reference passes only
   `gate`/`when` (declaration fields stay `None`). → checkpoint: the
   model default `when="checkpoints"` is never consulted for authored
   attachments — `when` is always in the constructor call.
5. `_validate_assistant_namespace(assistants, stages)`: iterates
   `(stage.assistants or {}).values()` (was: list elements); a
   declaration name repeated across the catalog and any inline
   declaration raises `"duplicate assistant name: NAME"`. References
   never count. → checkpoint: dict-key uniqueness makes an in-stage
   repeat impossible for authored files; the check remains the
   cross-surface guard.
6. **Output**: `WorkflowDocument.assistants: dict[str,
   WorkflowAssistant]` (authored order = dict insertion order =
   delivery order) and `WorkflowStage.assistants: dict[str,
   WorkflowAssistant] | None` (empty map normalized to `None` at step
   6.1.14).

#### Checkpoint Summary

- Old-form rejection with rename errors: passed (three distinct sites:
  catalog non-mapping, attachment non-mapping, and — implicitly — the
  disappearance of the bare-string branch).
- Reference/declaration discrimination unchanged by key set: passed.
- Authored order preservation (PyYAML constructs dicts in document
  order; Python dicts preserve insertion order): passed — the compiled
  output order equals the authored key order.

### Trace: `parse_dsl(text)` — repeatable flag

#### Chain

1. **Input**: pipeline-file text; the header segment before `---`.
2. `_parse_header`: after the existing `roles` extraction, extract
   `repeatable`: present-and-not-strictly-bool → `StructuralError(
   "non-bool value in header.repeatable")` (an explicit `null` is
   "present and non-bool" → the same error); absent → `False`. Build
   `PipelineHeader(name, description, roles, repeatable)`. → checkpoint:
   `isinstance(v, bool)` is the strict test (`repeatable: 1` fails it —
   Python `1 == True` but is not a `bool`).
3. **Output**: the 4-field header flows 1:1 into `PipelineDocument`;
   `repeatable` never enters `FlowDocument` directly (only the derived
   `FlowRepeat` does).

#### Checkpoint Summary

- Header ordering of checks (`agents` rename → roles → repeatable):
  the flag check comes last, after `roles` — matches the contract's
  step-2 narrative: passed.

### Trace: `compile_flow(...)` — repeat compilation

#### Chain

1. **Input**: `pipeline_path`, `flow_path`, `workflow:
   WorkflowDocument | None`, `root_dir`, `project_name`.
2. `parse_dsl` → `header` (now carries `repeatable`); empty-body guard
   unchanged.
3. **Step 4.0** — `_check_repeat_correspondence(header, workflow)`
   (new helper, called in `compile_flow` before the
   `workflow is not None` reconstruction branch so the error precedes
   every reconstruction error — embed refs, stage names, skip guards):
   `if workflow is not None and workflow.repeat is not None and not
   header.repeatable: raise StructuralError("workflow repeat block
   requires a repeatable pipeline; author repeatable: true in the
   pipeline header")`. → checkpoint: the workflow parser never sees the
   pipeline (two-layer pattern); only this cell sees both documents.
4. Reconstruction 4.1–4.10 unchanged except the assistants map
   consumption: `_assistant_namespace` and `_assistants_by_id` iterate
   `.values()` (see Algorithm Design). → checkpoint: `if not
   attachments:` keeps working (`None`/`{}` both falsy); loop-expanded
   copies share one entry list.
5. **Step 6** — `FlowDocument(..., description=…, repeat=_repeat_emission(
   header, workflow), memory=memory_emission.block, …)`:
   `repeatable` False → `None`; else the workflow block's authored keys
   or the empty `FlowRepeat()` (scalar form). The constructor argument
   sits between `description` and `memory`. → checkpoint: authored keys
   only — no default materialization (`max_cycles: 0` compiles as 0).
6. `serialize_flow(doc)` → text; `flow_path.write_text(text_out)`;
   return `(PipelineDocument, FlowDocument)`. `PipelineDocument` keeps
   the original body and the unprefixed description — the repeat
   directive is output-side only.

#### Checkpoint Summary

- Always-emit rule (block → authored keys; no block / `workflow=None` /
  workflow-free → scalar; non-repeatable → no key): passed.
- Byte-identity for non-repeatable pipelines: `repeat=None` → the
  serializer omits the key: passed.
- `PipelineDocument` mirror untouched: passed.

### Trace: `serialize_flow(doc)` — repeat emission

#### Chain

1. **Input**: `FlowDocument` with `repeat: FlowRepeat | None`.
2. After `top["description"] = doc.description` and before the `memory`
   block:
   - `doc.repeat is None` → nothing (byte-identical output).
   - both fields `None` → `top["repeat"] = True` → serializes as the
     plain scalar `repeat: true`.
   - otherwise → `top["repeat"] = {"max_cycles": …, "keep_runs": …}`
     (present keys only, fixed insertion order) → serializes as a
     block-style mapping of plain scalars:
     `repeat:\n  max_cycles: 3\n  keep_runs: 5`.
   → checkpoint: `_CanonicalDumper` + `yaml.dump(sort_keys=False,
   default_flow_style=False, indent=2)` needs no new representer — a
   plain `bool`/`dict` of `int`s hits the SafeDumper defaults exactly as
   the memory block does.
3. **Output**: canonical text, one trailing newline; top-level order
   `prompt, root_dir, name, description, repeat, memory, collaboration,
   team, stages`.

#### Checkpoint Summary

- Emission position and style rules: passed.
- No reordering of other keys: passed.

### Trace: `merge_workflow_overlay(base, contributions)` — repeat + maps

#### Chain

1. **Input**: authored base (post decision, post skip-merge),
   contributions in enumeration order.
2. `_authored_namespace(base)`: `for entry in (stage.assistants or
   {}).values()` — declarations join the namespace seed.
3. `_merge_catalog` unchanged (already map-keyed by name).
4. **Step 4c** — `_merge_repeat(base, contributions)` (new; the exact
   shape of `_merge_delegation`): the authored block wins; with none, the
   later contributing tool's block wins; no field-level merging.
5. `_merge_stage` → `_merge_stage_assistants(authored_map, …)`: the
   result is a dict seeded from the authored map (authored order), then
   contribution entries appended per name in enumeration order; a name
   already on the stage is dropped silently; an appended declaration
   whose name is in the evolving namespace is dropped silently; `{}`
   result → `None`. → checkpoint: the namespace invariant (each name at
   most once across catalog + every inline declaration) is preserved by
   construction.
6. The rebuilt `WorkflowDocument(..., delegation=…, repeat=_merge_repeat(
   base, contributions))` — the ninth field rides the rebuild.
7. **Output**: `WorkflowOverlay`; workflow `None` only for a `None` base
   with no committed contribution.

#### Checkpoint Summary

- Whole-block authored-wins semantics identical to memory/delegation:
  passed.
- Purity (inputs never mutated — new dicts built): passed.

### Trace: `PipelineHooks` delivery (events.py) — emptiness counts repeat

#### Chain

1. **Input**: a tool's buffered `WorkflowDocument` (`amendment.
   _contribution`).
2. The intercept fact walk tuple gains `"repeat"`: `for fact in
   ("prompt", "stages", "extend", "memory", "assistants",
   "delegation", "repeat")` — a `getattr` failure on an out-of-contract
   object still fails the hook under the same hard error.
3. The emptiness discard gains `and document.repeat is None`: a
   `repeat`-only contribution is NOT empty — it commits and merges.
4. **Output**: committed `ToolContribution` list →
   `merge_workflow_overlay`.

#### Checkpoint Summary

- Consistency with `WorkflowAmendment.contribute`'s annotation (fixed
  this stage): passed.

### Trace: `apply_skip_stages(workflow, skip_stages)`

#### Chain

1. **Input**: resolved workflow (or `None`), CLI skip names.
2. Step 3 replacement now carries the pre-skip entry's assistants **map**
   (`assistants=(existing.assistants if existing is not None else None)`
   — the code already forwards the field verbatim; only its type and the
   docstring wording change): the compiler removes the skipped stage
   before the attachment walk, but `_assistant_namespace` reads every
   stage entry, so the stage's inline declarations stay resolvable for
   other stages' references.
3. Step 4 rebuild gains `repeat=workflow.repeat if workflow is not None
   else None` — carried verbatim (same object, opaque). A dropped field
   would silently recompile an authored `repeat: {max_cycles: N}` as the
   scalar `true` on every `--skip` run.
4. **Output**: new `WorkflowDocument`; input unmutated.

#### Checkpoint Summary

- Verbatim carry of all nine fields: passed.

### Trace: `write_afm_config(agent, flow, workflow)` — mechanical adaptation

#### Chain

1. `_assistant_namespace(workflow)`: `for entry in (stage.assistants or
   {}).values()` (was `or []`). No behavior change — the contract wording
   ("the catalog plus every full inline declaration of the stages
   block") was already map-agnostic.
2. Everything else (profile materialization, closures, limits) is
   untouched. → checkpoint: the compiled-flow side (`flow.stages[].
   fields["assistants"]` — the engine list) is unchanged.

## Algorithm Design

### `WorkflowRepeat` (new — `goga/pipeline/workflow/workflow_repeat.py`)

**Responsibility**: pure data model of the authored run-cycle tuning
block; carried inside `WorkflowDocument`.

**Algorithm** (construction contract):
```
1. @dataclass(kw_only=True); fields max_cycles: int | None = None,
   keep_runs: int | None = None — fixed order (per `convention`:
   stdlib dataclasses, never pydantic)
   → authored values only; zero is a value, None is an omission
```

**Errors**: none (the model never validates — `parse_workflow` owns it).

**Edge Cases**: `WorkflowRepeat(max_cycles=0)` is distinct from
`WorkflowRepeat()` — the serializer distinguishes them (0 emits a key,
None omits it).

### `_build_repeat` (new routine in `parse_workflow.py`)

**Responsibility**: validate the raw `repeat` block and build the model
(contract step 6.9). The structural twin of `_build_delegation`.

**Algorithm**:
```
1. repeat_raw is None → return None (no block)
2. FOR (key, value) IN repeat_raw.items():
   - key == "max_cycles" → max_cycles = _validate_repeat_bound("max_cycles", value)
   - key == "keep_runs"  → keep_runs  = _validate_repeat_bound("keep_runs", value)
   - ELSE → raise WorkflowSyntaxError(
       f"unknown key in workflow.repeat: {key}; valid keys: max_cycles, keep_runs")
3. empty dict (no keys survived) → return None (empty block equals absence)
4. RETURN WorkflowRepeat(max_cycles=…, keep_runs=…)
```

`_validate_repeat_bound(key, field_value)` — the twin of
`_validate_delegation_bound` with `minimum=0` and the
`workflow.repeat` scope:
```
1. isinstance(field_value, bool) or not isinstance(field_value, int)
   → raise f"non-int value in workflow.repeat.{key}"
2. field_value < 0 → raise f"{key} must be >= 0 in workflow.repeat"
3. RETURN field_value
```

**Errors**: `WorkflowSyntaxError` with the four exact messages above
(non-int incl. boolean; negative; unknown key; plus the top-level
non-mapping error raised in `_extract_top_level`).

**Edge Cases**: `{}` → `None`; `max_cycles: 0`/`keep_runs: 0` carried
verbatim; a boolean value is rejected as non-int.

### `_build_assistant_catalog` (rewritten for the map form)

**Responsibility**: validate the name-keyed catalog (contract 6.5).

**Algorithm**:
```
1. assistants_raw is None → return {}
2. FOR (key, entry_value) IN assistants_raw.items():
   - not isinstance(entry_value, dict) → raise
     f"non-mapping assistant entry in workflow.assistants.{key}"
   - name = key (a non-str key fails the name grammar — see below)
   - fields = {k: _validate_catalog_field(scope, k, v) for k, v in
     entry_value.items()}   # scope = f"workflow.assistants.{name}"
   - at-least-one: fields["prompt"] is None and fields["skills"] is None
     → raise f"assistant {name} requires at least one of prompt or skills"
   - _validate_assistant_name(name)
   - catalog[name] = WorkflowAssistant(name=name, prompt=…, skills=…,
     agent=…, delegate=fields.get("delegate", False), env=…)
3. RETURN catalog   # insertion order = authored order
```

`_validate_assistant_name` gains the non-`str` guard (a YAML key may
parse as `int`/`float`/`bool`):
```
if not isinstance(name, str) or not _ASSISTANT_NAME_PATTERN.fullmatch(name):
    raise WorkflowSyntaxError(f"invalid assistant name: {name}")
```
`_ASSISTANT_CATALOG_KEYS` drops `"name"` → `("prompt", "skills",
"agent", "delegate", "env")`; the unknown-key message and
`_ATTACHMENT_DECLARATION_KEYS` derive from it automatically. The explicit
`if key == "name"` acceptance branch in `_validate_catalog_field` is
DELETED — with the branch gone, an inner `name` key reaches the
else-branch and raises the unknown-key error (dropping the constant alone
would leave the branch silently accepting it). The now-dead list-form
helpers are deleted with the rewrite: `_build_catalog_entry`,
`_build_attachment_entry`, `_required_attachment_name`,
`_build_attachment_reference`, `_build_attachment_declaration`, and
`_validate_top_level_list` (used only by the old `assistants` branch of
`_extract_top_level`).

**Errors**: non-mapping entry; unknown key (incl. `name`/`gate`/`when`)
with the five-key valid list; field type errors (unchanged validators);
at-least-one; name grammar/reserved; (duplicate names become
structurally impossible in-catalog — the dict key is unique; YAML
duplicate keys collapse at load, the project's map convention).

**Edge Cases**: `assistants: {}` → empty catalog (no namespace); an
`env: {}` entry value equals absence (existing `_validate_stage_env`).

### `_build_stage_assistants` (rewritten for the map form)

**Responsibility**: validate a stage's attachment map (contract 6.7).

**Algorithm**:
```
1. not isinstance(value, dict) → raise
   f"non-mapping assistants in workflow.stages.{stage}; author the map
   form keyed by assistant name"     # kills the list AND bare-string forms
2. empty dict → return None
3. FOR (key, entry_value) IN value.items():
   - not isinstance(entry_value, dict) → raise
     f"non-mapping assistant attachment in workflow.stages.{stage}.{key}"
   - name = key; scope = f"workflow.stages.{stage}.assistants.{name}"
   - "when" not in entry_value → raise f"when is required in {scope}"
     # runs for BOTH forms, before discrimination — an empty {} dies here
   - gate/when validation:
       gate = entry_value.get("gate", False); non-bool → f"non-bool value in {scope}.gate"
       when = _validate_when(scope, entry_value["when"])
   - IF set(entry_value) <= {"gate", "when"}:      # reference
       _validate_assistant_name(name)
       attachments[name] = WorkflowAssistant(name=name, gate=gate, when=when)
   - ELSE:                                          # full inline declaration
       fields = {k: _validate_attachment_field(scope, k, v) for k, v in
                 entry_value.items()}
       at-least-one (same message as the catalog, on `name`)
       _validate_assistant_name(name)
       attachments[name] = WorkflowAssistant(name=name, prompt=…, skills=…,
         agent=…, delegate=…, env=…, gate=gate, when=when)
4. RETURN attachments   # None when empty
```

**Errors**: as listed; the unknown attachment key error lists the
seven-key valid set `prompt, skills, agent, delegate, env, gate, when`.

**Edge Cases**: `{}` → `None`; a reference with only `when:` is valid
(gate materializes `False`); a declaration may carry `gate`/`when` plus
declaration keys; `skills: []` satisfies at-least-one (presence, never
truthiness).

### `_check_repeat_correspondence` + `_repeat_emission` (new routines in `compile_flow.py`)

**Responsibility**: the cross-document check (4.0) and the single
compilation rule (step 6).

**Algorithm**:
```
_check_repeat_correspondence(header, workflow):
1. workflow is None or workflow.repeat is None or header.repeatable
   → return (no error)
2. ELSE raise StructuralError("workflow repeat block requires a
   repeatable pipeline; author repeatable: true in the pipeline header")

_repeat_emission(header, workflow) -> FlowRepeat | None:
1. not header.repeatable → None
2. workflow is not None and workflow.repeat is not None →
   FlowRepeat(max_cycles=workflow.repeat.max_cycles,
              keep_runs=workflow.repeat.keep_runs)   # authored keys only
3. ELSE → FlowRepeat()                                # the scalar form
```

Placement: `_check_repeat_correspondence` is called in `compile_flow`
immediately after the empty-body guard, before the
`workflow is not None` reconstruction branch (error precedence: the
cross-check fires before any extend-ref/stage-name/skip error).
`_repeat_emission` is called at the `FlowDocument` construction
(`repeat=` between `description` and `memory`).

**Errors**: the one `StructuralError` above.

**Edge Cases**: a repeatable pipeline with `workflow=None` lands in
branch 3 (scalar); `--no-workflow` reaches the same branch through the
caller passing `workflow=None`.

### `_assistant_namespace` / `_assistants_by_id` (adapted)

**Responsibility**: namespace build and the step-4.10 attachment walk.

**Algorithm** (deltas only):
```
_assistant_namespace:
  for stage in workflow.stages.values():
      for entry in (stage.assistants or {}).values():   # was: `or []`
          if _is_assistant_declaration(entry): namespace[entry.name] = entry

_assistants_by_id:
  for entry in attachments.values():                    # was: list iteration
      … checks 1–4 and FlowAssembly unchanged …
```

The duplicate-in-one-stage guard (check 2, `seen` set) is retained as a
defensive check per the contract ("a programmatic contribution"): an
authored map cannot repeat a key and the overlay merge deduplicates, so
the guard is unreachable through authored paths — it costs O(n) and
keeps the contract's four checks in one place.

**Edge Cases**: `attachments` falsy (`None` or `{}`) skips the stage;
loop-expanded copies share one built entry list (uniform across copies).

### `merge_workflow_overlay` deltas (hooks)

```
_merge_repeat(base, contributions) -> WorkflowRepeat | None:   # new, twin of _merge_delegation
1. repeat = base.repeat if base is not None else None
2. IF repeat is None:
     FOR contribution IN contributions:
       IF contribution.document.repeat is not None:
         repeat = contribution.document.repeat      # later tool wins, whole
3. RETURN repeat

_merge_stage_assistants(authored_map, stage_name, contributions, namespace):
1. result = dict(authored_map) if authored_map is not None else {}
2. present_on_stage = set(result)
3. FOR contribution, FOR (name, entry) IN tool_stage.assistants.items():
     - name in present_on_stage → skip (silent drop)
     - declaration AND name in namespace → skip (silent drop)
     - result[name] = entry; present_on_stage.add(name)
     - declaration → namespace.add(name)
4. RETURN result or None
```

### `apply_skip_stages` deltas (pipeline root)

```
step 4 construction gains:  repeat=workflow.repeat if workflow is not None else None
step 3 replacement keeps:   assistants=(existing.assistants if existing is not None else None)
                            # the field now a map — forwarded verbatim, no rebuild
docstring: "list" → "map" wording; the repeat bullet added to Requirements
```

## Cross-cutting Concerns

- **Error handling**: unchanged strategy — `WorkflowSyntaxError` (a
  `ValueError` subclass) for workflow authoring, `StructuralError` (a
  `ValueError` subclass) for pipeline parsing/compilation; raised, never
  returned; exact message strings specified above and frozen by the
  contract. No wrapping, no recovery — authoring-time defects.
- **Validation split**: the workflow parser validates the `repeat` block
  structure (mapping, key set, int-not-bool, non-negative) and the
  assistants map grammar; the compiler owns only the cross-document
  check (4.0) and the attachment checks (4.10) — the two-layer pattern.
  goga's validation is at least as strict as afm's flow-file parse (a
  negative value and an unknown key are engine errors too — they must
  surface at authoring time).
- **Logging**: no new log points. The one existing collaboration
  diagnostic (inline declaration's skills WARNING, once per name) is
  unchanged. Nothing about repeat is logged — it is a pure compile
  output.
- **Caching**: none (pure functions; `compile_flow` idempotent over the
  same inputs).
- **Concurrency**: no thread-safety requirements (unchanged — the
  compile path is single-threaded per run).
- **Defaults discipline**: the parser materializes assistant defaults
  (`delegate False`, `gate False`, `max_tasks 50` when the delegation
  block is authored) but materializes NO repeat defaults — authored
  values only, `None` for absence, `{}` == absence. The compiler
  materializes no repeat values either; the scalar form delegates the
  cycle defaults to the engine (unlimited cycles, `keep_runs: 2`).

## Usages Analysis

### `convention` (`.goga/usages/conventions.md`)
- **What it provides**: mandatory Python rules — stdlib dataclasses with
  `kw_only=True`, relative intra-package imports, Google docstrings,
  structured `logging`, test layout (`tests/` mirrors source; contract /
  logic test pairs per model), `pytest tests/ -x` + `ruff check` as the
  validation commands.
- **Where used**: every new/changed module and test of the four cells.
- **Why chosen**: mandatory project practice.
- **How exactly**: `WorkflowRepeat`/`FlowRepeat` as `@dataclass(
  kw_only=True)`; helpers private to their modules; new tests under
  `tests/pipeline/{workflow,compiler,hooks}` following the
  `test_<module>_<kind>.py` naming.

### `beautiful_yaml` (`.goga/usages/cooks/beautiful_yaml.md`)
- **What it provides**: the `yaml.dump` parameters the `_CanonicalDumper`
  extends (`sort_keys=False`, `default_flow_style=False`,
  `allow_unicode=True`, `indent=2`).
- **Where used**: `serialize_flow` repeat emission.
- **Why chosen**: the repeat block must serialize as a block-style
  mapping of plain scalars — the SafeDumper defaults over a plain `dict`
  produce exactly that; no new representer is needed.
- **How exactly**: `top["repeat"] = True` (scalar) or a plain
  insertion-ordered dict (block form).

### `afm` (`.goga/usages/cooks/afm.md`)
- **What it provides**: the engine contract — the flow-file `repeat`
  directive forms, the strict block parse, cycle semantics
  (`flow_repeated`, stop-on-failed-cycle, `keep_runs` pruning), the
  team-member/stage-assistant key sets, mode/trigger vocabularies.
- **Where used**: `compile_flow` (always-emit rule, cross-check),
  `serialize_flow` (emission), `FlowRepeat`/`FlowAssistant` models.
- **Why chosen**: the engine vocabulary is imported verbatim; goga never
  duplicates cycle semantics.
- **How exactly**: the compiled directive mirrors the usage table
  (`repeat: true` ⇔ unlimited defaults; block ⇔ authored bounds).

### `jinja2` (`.goga/usages/cooks/jinja2.md`)
- **What it provides**: whole-file workflow rendering before parsing.
- **Where used**: unchanged (`render_workflow`); repeat/assistants ride
  the rendered text like every other block.
- **Why chosen**: no rendering change; noted to confirm no interaction.

### Imported Usages
- `parse-workflow`, `memory`, `assistants` from `goga/pipeline/workflow` —
  the compiler's bridge to the authoring vocabulary.
  - Paths: `goga/pipeline/workflow/.usages/{parse-workflow,memory,assistants}.md`
  - `assistants` documents the map-form catalog/attachments grammar the
    compiler consumes; `parse-workflow` documents the repeat block
    grammar and the empty-workflow rule; `memory` scopes the memory
    consumption (unchanged this task).
- `collaboration-emission`, `compile-flow`, `serialize-flow`,
  `parse-dsl`, `checkpoints` — consumer-side cells import the compiler /
  hooks practices; all were updated by apply-architecture and stay
  consistent with this design (verified: the repeat sections, the
  always-written trigger wording, the map merge-slot bullet).

## `.usages/` Update

All consumer documentation was already materialized by the
apply-architecture stage; this design confirms consistency and requires
no further `.usages/` edits.

### Cell: `goga/pipeline/workflow`

#### Existing Files — Consistency
- **`assistants.md`** → `goga/pipeline/workflow/.usages/assistants.md`
  - Status: current (full rewrite landed: map-form catalog/attachments,
    required `when`, complete structural-error table, no list-form
    examples).
- **`parse-workflow.md`** → `goga/pipeline/workflow/.usages/parse-workflow.md`
  - Status: current (the repeat-block section, the top-level key list
    with `repeat`, the empty-workflow rule, the scalar anti-pattern).

### Cell: `goga/pipeline/compiler`

#### Existing Files — Consistency
- **`parse-dsl.md`** — current ("The header repeatable flag" section).
- **`compile-flow.md`** — current (top-level order line, "Repeat
  compilation" section with the authoring→compiled table).
- **`serialize-flow.md`** — current (repeat style rule; key-presence
  note between `description` and `memory`).
- **`collaboration-emission.md`** — current (always-written trigger with
  no compiler-side engagement default; programmatic-contribution
  duplicate wording; name-keyed map source with authored key order).

### Cell: `goga/pipeline/hooks`

#### Existing Files — Consistency
- **`checkpoints.md`** — current (merge-slot bullet: the repeat block is
  whole; stage assistant maps append with name deduplication).

### Cell: `goga/pipeline`

No `.usages/` directory — none to update.

## Test Stack Trace

### General Setup

- pytest per `convention` (tests mirror source; `tmp_path` for files; no
  mocks for pure logic). `parse_workflow`/`parse_dsl`/`serialize_flow`
  are pure — text in, model/text out. `compile_flow` needs `tmp_path`
  for `pipeline_path`/`flow_path`. Overlay tests build
  `WorkflowDocument`/`ToolContribution` values directly.
- Reusable local fixtures follow the existing per-directory `conftest.py`
  pattern; no new shared fixtures required.
- Neither pytest nor ruff is installed in the design environment — the
  implementation stage must run `pytest tests/ -x` and
  `ruff check goga/` in a virtualenv (per `convention`).

### Source File Registry

- `goga/pipeline/workflow/`: `workflow_repeat.py` (new),
  `workflow_stage.py`, `workflow_document.py`,
  `workflow_assistant.py`, `parse_workflow.py`, `__init__.py`
- `goga/pipeline/compiler/`: `flow_repeat.py` (new),
  `pipeline_header.py`, `flow_document.py`, `parse_dsl.py`,
  `compile_flow.py`, `serialize_flow.py`, `__init__.py`
- `goga/pipeline/hooks/`: `overlay.py`, `events.py`
- `goga/pipeline/`: `apply_skip_stages.py`, `afm_config.py`

---

### Positive Tests

#### `test_parse_repeat_block_carries_authored_keys`

**Setup**: none (pure function).

**Input**: `"repeat:\n  max_cycles: 3\n  keep_runs: 5\n"` (plus any
content key, e.g. a `prompt:`).

**Trace**:
```
parse_workflow(text)
  → yaml.safe_load                       # dict root
  → _extract_top_level                   # repeat branch → mapping check passes
  → _build_repeat({"max_cycles": 3, "keep_runs": 5})
    → _validate_repeat_bound("max_cycles", 3)  returns: 3
    → _validate_repeat_bound("keep_runs", 5)   returns: 5
  → WorkflowDocument(repeat=WorkflowRepeat(max_cycles=3, keep_runs=5))
```

**Assertions**:
```
doc.repeat is not None
doc.repeat.max_cycles == 3
doc.repeat.keep_runs == 5
```

**Sufficiency**: freezes the authored-keys-only carry — a regression
that materializes engine defaults (e.g. `keep_runs=2`) or swaps the
fields fails here.

---

#### `test_parse_repeat_block_single_key_and_zero_values`

**Setup**: none.

**Input**: three texts — `"repeat:\n  max_cycles: 0\n"`,
`"repeat:\n  keep_runs: 0\n"`, `"repeat:\n  max_cycles: 1\n"`.

**Trace**:
```
parse_workflow(text) → _build_repeat → WorkflowRepeat(one authored key, other None)
```

**Assertions**:
```
doc.repeat.max_cycles == 0 and doc.repeat.keep_runs is None     # text 1
doc.repeat.max_cycles is None and doc.repeat.keep_runs == 0     # text 2
doc.repeat.max_cycles == 1                                      # text 3
```

**Sufficiency**: pins the zero-is-a-value rule and the None/0
distinction the serializer's key-presence rule depends on.

---

#### `test_parse_repeat_only_workflow_is_valid`

**Setup**: none.

**Input**: `"repeat:\n  max_cycles: 2\n"` (nothing else).

**Trace**:
```
parse_workflow(text)
  → _build_repeat → WorkflowRepeat(max_cycles=2)
  → empty-workflow rule: repeat is not None → no raise
  → WorkflowDocument(prompt=None, …, repeat=WorkflowRepeat(2, None))
```

**Assertions**:
```
doc.prompt is None; not doc.stages; doc.repeat.max_cycles == 2   # no WorkflowSyntaxError raised
```

**Sufficiency**: guards the acceptance criterion "a workflow consisting
of the block alone is valid" — a rule counting regression (repeat
omitted from the conjunction) would raise "empty workflow" here.

---

#### `test_parse_assistant_catalog_map_form`

**Setup**: none.

**Input**:
```yaml
assistants:
  reviewer:
    agent: claude
    delegate: true
    skills: [code-audit]
    prompt: |
      Review the stage changes.
stages:
  build:
    assistants:
      reviewer:
        when: finish
```

**Trace**:
```
parse_workflow(text)
  → _extract_top_level        # assistants is a dict → mapping check passes
  → _build_assistant_catalog  # per (name, value): value dict; fields over the
                              # five-key set; at-least-one via skills; name grammar
  → _build_stage_assistants   # entry value {when: finish} ⊆ {gate, when} → reference
  → _validate_assistant_namespace   # one declaration, no duplicates
  → WorkflowDocument(assistants={"reviewer": WorkflowAssistant(name="reviewer", …)})
```

**Assertions**:
```
doc.assistants["reviewer"].name == "reviewer"
doc.assistants["reviewer"].delegate is True
doc.assistants["reviewer"].gate is False            # materialized default
doc.stages["build"].assistants["reviewer"].when == "finish"
doc.stages["build"].assistants["reviewer"].prompt is None   # reference carries none
```

**Sufficiency**: the canonical map-form happy path — locks the
name-from-key extraction and the reference/declaration discrimination.

---

#### `test_parse_attachment_full_inline_declaration`

**Setup**: none.

**Input**:
```yaml
stages:
  build:
    assistants:
      security:
        agent: codex
        prompt: Audit the diff.
        gate: true
        when: checkpoints
```

**Trace**:
```
parse_workflow(text)
  → _build_stage_assistants  # {agent, prompt, gate, when} ⊄ {gate, when} → declaration
    → _validate_attachment_field over the seven-key set
    → at-least-one via prompt
  → WorkflowAssistant(name="security", prompt=…, agent="codex", gate=True, when="checkpoints")
```

**Assertions**:
```
att = doc.stages["build"].assistants["security"]
att.prompt == "Audit the diff." and att.agent == "codex"
att.gate is True and att.when == "checkpoints"
```

**Sufficiency**: the declaration form with explicit gate — proves the
catalog field set plus gate/when accepts inline authoring.

---

#### `test_parse_dsl_repeatable_flag`

**Setup**: none.

**Input**: header texts `"name: X\ndescription: Y\nrepeatable: true\n---\n…"` and
the same without the flag; plus `repeatable: false`.

**Trace**:
```
parse_dsl(text) → _parse_header → header_data["repeatable"]
  → strictly-bool check passes → PipelineHeader(repeatable=True/False)
```

**Assertions**:
```
header.repeatable is True    # explicit true
header.repeatable is False   # absent key
header.repeatable is False   # explicit false
```

**Sufficiency**: pins absent == False == explicit false — the capability
tripod the always-emit rule reads.

---

#### `test_compile_flow_repeatable_with_block_emits_authored_keys`

**Setup**: `tmp_path` — a pipeline-file with `repeatable: true` and one
stage; a workflow text with `repeat: {max_cycles: 3, keep_runs: 5}`
parsed via `parse_workflow`.

**Input**: `compile_flow(pipeline_path, flow_path, workflow=doc)`.

**Trace**:
```
compile_flow
  → parse_dsl → header.repeatable == True
  → _check_repeat_correspondence   # workflow.repeat set, repeatable → no raise
  → _reconstruct_body (unchanged)
  → _repeat_emission → FlowRepeat(max_cycles=3, keep_runs=5)
  → FlowDocument(repeat=FlowRepeat(3, 5), …)
  → serialize_flow → "…\nrepeat:\n  max_cycles: 3\n  keep_runs: 5\n…"
```

**Assertions**:
```
doc.repeat.max_cycles == 3 and doc.repeat.keep_runs == 5
text = flow_path.read_text()
"repeat:\n  max_cycles: 3\n  keep_runs: 5\n" in text
text.index("description:") < text.index("repeat:") < text.index("memory:")
```

**Sufficiency**: the acceptance criteria "authored keys only" and the
emission position, in one shot.

---

#### `test_compile_flow_repeatable_without_block_emits_scalar`

**Setup**: `tmp_path`; repeatable pipeline; two workflow variants — a
workflow without a `repeat` block, and `workflow=None` (the
`--no-workflow` CLI path reaches the same second variant: the caller
passes `workflow=None`).

**Input**: `compile_flow(pipeline_path, flow_path, workflow=…)`.

**Trace**:
```
compile_flow → _repeat_emission → FlowRepeat()          # no authored key
  → serialize_flow → top["repeat"] = True → "repeat: true"
```

**Assertions**:
```
doc.repeat is not None
doc.repeat.max_cycles is None and doc.repeat.keep_runs is None
"\nrepeat: true\n" in flow_path.read_text()      # both variants
```

**Sufficiency**: the always-emit rule's default arm — the scalar form
for a missing block, a missing workflow, and a workflow-free compile.

---

#### `test_compile_flow_non_repeatable_output_byte_identical`

**Setup**: `tmp_path`; a non-repeatable pipeline without a workflow
repeat block (the six-asset shape); compile once on this branch's
compiler.

**Input**: `compile_flow(pipeline_path, flow_path)`; read the text.

**Trace**:
```
compile_flow → _repeat_emission → None → FlowDocument(repeat=None)
  → serialize_flow → no repeat key anywhere
```

**Assertions**:
```
"repeat" not in flow_path.read_text()
doc.repeat is None
```

**Sufficiency**: the byte-identity acceptance criterion for
non-repeatable pipelines (pair with a golden-file comparison over the
shipped assets in the integration pass).

---

#### `test_compile_flow_map_form_output_equals_list_form_output`

**Setup**: `tmp_path`; one pipeline; two workflow texts authoring the
same collaboration — the new map form and a pre-change equivalent list
form (kept as a literal string in the test, not parsed by the new
parser); the expected flow text is computed once from the map-form
compile.

**Input**: compile with the map-form workflow; compare against the
expected stage `assistants` list and `team` block.

**Trace**:
```
compile_flow(map_form_workflow)
  → _assistant_namespace (catalog ∪ inline declarations)
  → _assistants_by_id → FlowAssistant(profile="goga-reviewer", title="reviewer",
      instruction=…, mode="required", trigger="on_completion")   # gate:true, when:finish
  → serialize_flow → stages[].assistants list, team list
```

**Assertions** (for both the reference form and the declaration form):
```
stage.fields["assistants"] == [FlowAssistant(profile="goga-reviewer", …, mode=…, trigger=…)]
every entry has an explicit trigger ("one_shot"/"checkpoints"/"on_completion")
team == [FlowTeamMember(id="reviewer", title="reviewer", profile="goga-reviewer", …)]
```

**Sufficiency**: the acceptance criterion that the compiled output for
map-form authoring equals the engine list-form output for the
equivalent old authoring — the engine-facing contract is untouched.

---

#### `test_overlay_authored_repeat_wins_and_contribution_fills`

**Setup**: base `WorkflowDocument(repeat=WorkflowRepeat(max_cycles=2))`;
contributions: tool A doc with `repeat=WorkflowRepeat(keep_runs=9)`,
tool B doc with `repeat=WorkflowRepeat(max_cycles=7)`; second scenario
with `base.repeat = None`.

**Input**: `merge_workflow_overlay(base, [contrib_a, contrib_b])`.

**Trace**:
```
merge_workflow_overlay
  → _merge_repeat: authored present → unbeatable      # scenario 1
  → _merge_repeat: no authored → later tool wins      # scenario 2 → B's block
  → WorkflowDocument(repeat=…)
```

**Assertions**:
```
overlay.workflow.repeat.max_cycles == 2    # scenario 1 — authored wins
overlay.workflow.repeat.keep_runs is None  # contribution not merged in (whole-block)
overlay.workflow.repeat.max_cycles == 7    # scenario 2 — later tool wins
```

**Sufficiency**: the whole-block authored-wins rule and the
later-tool-wins fill — the memory/delegation semantics mirrored for
repeat.

---

#### `test_events_repeat_only_contribution_is_not_empty`

**Setup**: a hook tool whose contribution is
`WorkflowDocument(repeat=WorkflowRepeat(max_cycles=4))`; registry per
the existing hooks conftest.

**Input**: `hooks.amend_workflow(pipeline=…, decision=…, workflow=None,
work=…)` with the tool registered.

**Trace**:
```
amend_workflow → delivery walk → contribution buffered
  → emptiness check: repeat is not None → NOT empty → commits
  → merge_workflow_overlay(None, [contrib]) → workflow carries the block
```

**Assertions**:
```
overlay.workflow is not None
overlay.workflow.repeat.max_cycles == 4
```

**Sufficiency**: guards the fixed PipelineHooks rule — a dropped `repeat`
term in the emptiness conjunction would discard the contribution with a
warning and yield `workflow=None`.

---

#### `test_apply_skip_stages_carries_repeat_and_assistants_map`

**Setup**: `WorkflowDocument(stages={"build": WorkflowStage(assistants={
"security": WorkflowAssistant(name="security", prompt="Audit.",
when="start")})}, repeat=WorkflowRepeat(max_cycles=3))`.

**Input**: `apply_skip_stages(doc, ["build"])`.

**Trace**:
```
apply_skip_stages
  → step 3: replacement WorkflowStage(skip=True, assistants={"security": …})   # map rides
  → step 4: rebuild with repeat=doc.repeat (same object)
```

**Assertions**:
```
out.repeat is doc.repeat                      # verbatim, same object
out.stages["build"].skip is True
out.stages["build"].assistants["security"].prompt == "Audit."   # namespace stays resolvable
```

**Sufficiency**: the acceptance criterion for the skip path — a dropped
carry would silently recompile the authored bound as the scalar default
and break cross-stage references.

---

#### `test_run_pipeline_skip_path_compiles_authored_repeat` (integration)

**Setup**: project dir with a `repeatable: true` pipeline, a workflow
with `repeat: {max_cycles: 2}`, tmp dirs.

**Input**: the run coordination path with `skip=["review"]` (or the
direct chain `load_workflow → apply_skip_stages → compile_flow` if the
full run is too heavy for the unit layer).

**Trace**:
```
resolve → load_workflow → apply_skip_stages(skip) → compile_flow
  → repeat survives the rebuild → FlowRepeat(max_cycles=2) → flow text
```

**Assertions**: the flow-file carries `max_cycles: 2` and omits the
skipped stage.

**Sufficiency**: end-to-end guard of the two rebuilds composed.

---

### Negative Tests

#### `test_parse_repeat_non_mapping_block`

**Setup**: none.

**Input**: parametrized texts — `"repeat: true\nprompt: x\n"`,
`"repeat: false\nprompt: x\n"`, `"repeat: 5\nprompt: x\n"`,
`"repeat: [1, 2]\nprompt: x\n"`, `"repeat: soon\nprompt: x\n"`.

**Trace**:
```
parse_workflow → _extract_top_level repeat branch
  → _validate_top_level_mapping fails (non-dict value)
  → WorkflowSyntaxError("non-mapping repeat block in workflow")
```

**Assertions**:
```
with pytest.raises(WorkflowSyntaxError, match="non-mapping repeat block in workflow"): …
```

**Sufficiency**: the scalar-form rejection at parse time — including
`repeat: true`/`false`, the forms the ADR explicitly bans from the
workflow surface.

---

#### `test_parse_repeat_unknown_key`

**Input**: `"repeat:\n  max_cycles: 1\n  cycles: 3\n"`.

**Trace**: `_build_repeat` else-branch → raise.

**Assertions**:
```
pytest.raises(WorkflowSyntaxError, match="unknown key in workflow.repeat: cycles;
valid keys: max_cycles, keep_runs")
```

**Sufficiency**: goga must be at least as strict as afm's flow-file
parse (an unknown key is an engine error).

---

#### `test_parse_repeat_non_int_and_negative_values`

**Input**: parametrized — `{"max_cycles": true}`, `{"keep_runs": "3"}`,
`{"max_cycles": 1.5}`; and `{"max_cycles": -1}`, `{"keep_runs": -2}`.

**Trace**: `_validate_repeat_bound` → bool/non-int arm → "non-int value
in workflow.repeat.max_cycles" (resp. keep_runs); `< 0` arm →
"max_cycles must be >= 0 in workflow.repeat" (resp. keep_runs).

**Assertions**: `pytest.raises` with each exact message.

**Sufficiency**: a boolean is not an integer — the Python `bool`⊂`int`
trap must not let `repeat: {max_cycles: true}` through.

---

#### `test_parse_list_form_catalog_rejected_naming_map_form`

**Input**: the old list form —
`"assistants:\n- name: reviewer\n  prompt: X\nprompt: x\n"`.

**Trace**: `_extract_top_level` assistants branch → mapping check fails.

**Assertions**:
```
pytest.raises(WorkflowSyntaxError, match="non-mapping assistants block in workflow;
author the map form keyed by assistant name")
```

**Sufficiency**: the hard transition — the error must name the map form
(project precedent `agents` → `roles`); `.goga/workflows/
refinement.yml` will hit exactly this until its separate conversion.

---

#### `test_parse_attachment_list_and_string_forms_rejected`

**Input**: `"stages:\n  build:\n    assistants: [reviewer]\nprompt: x\n"`
and `"stages:\n  build:\n    assistants: reviewer\nprompt: x\n"`.

**Trace**: `_build_stage_assistants` non-dict value → raise.

**Assertions**:
```
pytest.raises(WorkflowSyntaxError, match="non-mapping assistants in
workflow.stages.build; author the map form keyed by assistant name")
```

**Sufficiency**: kills the bare-string form (no map rendering exists).

---

#### `test_parse_attachment_missing_when`

**Input**:
```yaml
stages:
  build:
    assistants:
      reviewer:
        gate: true
```

**Trace**: the required-`when` check precedes form discrimination →
raise.

**Assertions**:
```
pytest.raises(WorkflowSyntaxError, match="when is required in
workflow.stages.build.assistants.reviewer")
```

**Sufficiency**: the removed `checkpoints` default — engagement timing
is always authored.

---

#### `test_parse_catalog_inner_name_gate_when_unknown`

**Input**: catalog entries carrying `name:`, `gate:`, or `when:` keys.

**Trace**: `_validate_catalog_field` else-branch over the five-key set.

**Assertions**:
```
pytest.raises(WorkflowSyntaxError, match="unknown key in
workflow.assistants.reviewer: (name|gate|when); valid keys: prompt, skills, agent, delegate, env")
```

**Sufficiency**: the name IS the key; gate/when are attachment keys.

---

#### `test_parse_duplicate_assistant_name_across_surfaces`

**Input**: a catalog `reviewer` plus an inline declaration `reviewer` on
a stage (or the same name declared inline on two stages).

**Trace**: `_validate_assistant_namespace` → second declaration seen →
raise `"duplicate assistant name: reviewer"`.

**Sufficiency**: one namespace per workflow-file.

---

#### `test_parse_dsl_repeatable_non_bool`

**Input**: `"name: X\ndescription: Y\nrepeatable: 1\n---\n…"` (also
`repeatable: "yes"` — a QUOTED string; a bare `yes` parses as bool True
under PyYAML's YAML 1.1 — and `repeatable: null`).

**Trace**: `_parse_header` strictly-bool check → raise.

**Assertions**:
```
pytest.raises(StructuralError, match="non-bool value in header.repeatable")
```

**Sufficiency**: Python's `1 == True` must not leak a non-bool through.

---

#### `test_compile_flow_cross_check_error`

**Setup**: `tmp_path`; a NON-repeatable pipeline; a workflow with
`repeat: {max_cycles: 2}`.

**Input**: `compile_flow(pipeline_path, flow_path, workflow=doc)`.

**Trace**:
```
compile_flow → _check_repeat_correspondence
  → workflow.repeat set AND not header.repeatable
  → StructuralError("workflow repeat block requires a repeatable pipeline;
     author repeatable: true in the pipeline header")     # before reconstruction
```

**Assertions**:
```
pytest.raises(StructuralError, match="workflow repeat block requires a repeatable
pipeline; author repeatable: true in the pipeline header")
```

**Sufficiency**: the compiler-owned cross-reference check — the
acceptance criterion naming the conflict; also pins the precedence (the
error fires even when the workflow would also fail a stage-name check
later).

---

#### `test_parse_empty_workflow_still_rejects_profile_only`

**Input**: `"profile: dev\n"`.

**Trace**: all content fields absent (repeat included) → raise
`"empty workflow — provide at least prompt, one stage, one extend entry,
the memory block, the build block, the assistants block, the delegation
block, or the repeat block"`.

**Sufficiency**: activation is not content — unchanged semantics with
the new enumeration.

---

### Edge Case Tests

#### `test_parse_repeat_empty_block_equals_absence`

**Input**: `"repeat: {}\nprompt: x\n"`.

**Trace**: `_build_repeat({})` → `None` → the document carries no repeat
instruction.

**Assertions**: `doc.repeat is None` (and the workflow is valid via
`prompt`).

**Sufficiency**: the project's empty-map convention.

---

#### `test_parse_attachment_reference_with_when_only`

**Input**: an attachment value `{when: start}`.

**Assertions**: builds a reference with `gate is False`,
`when == "start"`, `prompt is None`.

**Sufficiency**: the minimal reference — gate is optional, when is not.

---

#### `test_parse_attachment_empty_map_equals_absence`

**Input**: `"stages:\n  build:\n    assistants: {}\nprompt: x\n"`.

**Assertions**: `doc.stages["build"].assistants is None`.

**Sufficiency**: normalization to `None` (the compiler's falsy checks
and the overlay's seed depend on it).

---

#### `test_parse_empty_assistants_catalog_equals_absence`

**Input**: `"assistants: {}\nprompt: x\n"` and `"assistants: {}\n"`.

**Trace**:
```
parse_workflow(text)
  → _extract_top_level            # assistants is a dict → mapping check passes
  → _build_assistant_catalog({})  → {}   # no entries, no namespace
  → empty-workflow rule:
      prompt variant — prompt is not None → no raise
      catalog-only variant — assistants empty (falsy) AND everything else absent → raise
```

**Assertions**:
```
doc.assistants == {} and doc.prompt == "x"                     # variant 1 — valid, empty catalog
pytest.raises(WorkflowSyntaxError, match="empty workflow")     # variant 2
```

**Sufficiency**: pins the empty-map-equals-absence convention at the
catalog level and its interaction with the empty-workflow rule — the
map-form twin of the old `assistants: []` behavior.

---

#### `test_parse_assistant_name_grammar_and_reserved`

**Input**: catalog keys `"good.name-1_X"`, `"bad name!"`, `"assistant"`,
`123`.

**Assertions**: the first parses; the others raise (`invalid assistant
name: …` / `assistant name is reserved`).

**Sufficiency**: the grammar plus the non-str YAML key guard added by
this design.

---

#### `test_serialize_flow_repeat_scalar_and_block_forms`

**Setup**: build `FlowDocument` values directly.

**Input**: `serialize_flow(FlowDocument(name="X", description="Y",
repeat=FlowRepeat(), stages=[…]))` and the `FlowRepeat(max_cycles=3)`
variant, plus `repeat=None`.

**Assertions**:
```
"\nrepeat: true\n" in text                                  # scalar
"repeat:\n  max_cycles: 3\n" in text and "keep_runs" not in text   # block, present keys only
"repeat" not in text                                        # None → omitted
```

**Sufficiency**: the serializer's three output arms in isolation.

---

#### `test_workflow_repeat_and_flow_repeat_model_contracts`

**Input**: `WorkflowRepeat()`, `WorkflowRepeat(max_cycles=0)`,
`FlowRepeat()`.

**Assertions**: defaults `None`; field order
(`list(dataclasses.fields(…))` names == `["max_cycles", "keep_runs"]`);
`kw_only=True`; `WorkflowRepeat(max_cycles=0).max_cycles == 0`.

**Sufficiency**: the model contracts (convention compliance, the
zero-vs-None distinction).

---

#### `test_facades_export_new_types`

**Input**: `from goga.pipeline.workflow import WorkflowRepeat` /
`from goga.pipeline.compiler import FlowRepeat`.

**Assertions**: both import cleanly (the compiler cell already imports
`WorkflowRepeat` from the workflow package for its own annotations —
the facade export is the consumer surface).

**Sufficiency**: the plan's checklist item "facade exports FlowRepeat"
(and the workflow-side counterpart the compiler import depends on).

---

#### `test_afm_config_namespace_walks_map_attachments`

**Setup**: effective workflow with a stage assistants map; a
`FlowDocument` referencing the same names.

**Input**: `write_afm_config(agent=None, flow=flow, workflow=workflow)`
(tmp home).

**Assertions**: the generated profiles cover the map's declaration
names (the namespace walk over `.values()` finds them).

**Sufficiency**: the mechanical adaptation in `afm_config.py` — proves
the third consumer reads the new container correctly.

---

## Additional Instructions for the Implementation Agent

- Implement cell by cell in the dependency order above; after each cell
  run bare `goga lint` from the repository root (per-path invocation
  yields false usage-filepath errors). At the end run `pytest tests/ -x`
  and `ruff check goga/` inside a virtualenv — neither tool is
  installed in the design environment; both must pass before the stage
  is done.
- Error message strings are contract — copy them verbatim from this
  document (they mirror the CODEMANIFEST annotations). A boolean is not
  an integer: every int validation in the new paths uses the
  `isinstance(v, bool) or not isinstance(v, int)` guard.
- Do not convert `.goga/workflows/refinement.yml` — the list-form parse
  rejection is the known accepted consequence; its conversion is a
  separate task (recorded twice in the task docs).
- The hard transition breaks the existing assistants test suite: every
  test authoring list-form assistants YAML or constructing
  `WorkflowStage(assistants=[...])` must be rewritten to the map form
  (and the dict model) — 24 files across
  `tests/pipeline/{workflow,hooks,compiler}` and `tests/pipeline`
  (`test_parse_workflow_assistants.py` alone carries 25 tests / 47
  list-form fixtures). The rewrite is mechanical: `- name: X` entries
  become map keys; expected `WorkflowAssistant` lists become name-keyed
  dicts; assertion messages change only where the new rename errors
  apply. Budget this work in the implementation stage — it surfaces on
  the first `pytest tests/ -x` run otherwise.
- Do not add `repeatable: true` to any shipped pipeline asset; do not
  surface repeat in `goga pipeline card` / `describe_pipeline` (ADR
  decision 8 — a card change is a later decision).
- `run_pipeline` stays a single `afm run` invocation; no goga-side
  cycle logic anywhere (no counting, no stop conditions, no pruning).
- New files: `workflow_repeat.py`, `flow_repeat.py` — one dataclass
  each, docstrings in the surrounding style (Google format, model
  contract notes). Update the two `__init__.py` facades (`__all__`
  stays alphabetical).
- Update stale docstrings that name the assistants "list" (workflow
  models, `_effective_overrides`, `_merge_stage_assistants`,
  `apply_skip_stages`, `afm_config` namespace walk) to the map wording —
  the CODEMANIFEST annotations are the wording source. Additionally
  update the `amend_workflow` docstring in
  `goga/pipeline/hooks/events.py`: its emptiness enumeration (and the
  Algorithm step-5 text) gains "and no repeat", mirroring the
  PipelineHooks contract wording.
- Byte-identity spot check: compile the six shipped assets plus the
  project pipelines before and after the change (git stash or a golden
  copy) and diff the flow outputs — they must be byte-identical.
