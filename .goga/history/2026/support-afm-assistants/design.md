# Design Document: `support-afm-assistants`

Design of the code implementation against the applied CODEMANIFEST contracts
(branch `support-afm-assistants`, working tree as materialized by the
apply-architecture stage). The architectural plan is
`.goga/history/2026/support-afm-assistants/arch.md`; the decision record is
`adr.md` in the same directory. This document specifies the code: files,
functions, algorithms, error messages, and tests. No implementation code is
written here.

`goga lint` on the four changed manifests: **0 errors (91 cells)**. No
CODEMANIFEST defect was found during tracing; every finding below is an
implementation-level decision or a mandatory touch point the contract implies.

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/pipeline/workflow/CODEMANIFEST` — new `WorkflowAssistant` /
  `WorkflowDelegation` models; `WorkflowStage.assistants`;
  `WorkflowDocument.assistants`/`delegation`; `parse_workflow` steps 6.5–6.8
  plus the extraction/valid-keys/empty/return consistency updates; global
  assistants paragraph; new Description.
- `goga/pipeline/compiler/CODEMANIFEST` — Imports extended
  (`WorkflowAssistant`, `WorkflowDelegation`, `assistants` usage); new
  `FlowCollaboration` / `FlowTeamMember` / `FlowAssistant` models;
  `FlowDocument` eight-key contract; `FlowStage` canonical order +
  `assistants` slot; `compile_flow` steps 4.10 / 5 / 6; `serialize_flow`
  emission rules; collaboration-emission paragraph.
- `goga/pipeline/hooks/CODEMANIFEST` — overlay annotation paragraph on the
  assistant-namespace invariant; `merge_workflow_overlay` steps 4a/4b/5a and
  the step-4 carve-out; `WorkflowAmendment.contribute` and
  `PipelineHooks.amend_workflow` empty-contribution rules; Description.
- `goga/pipeline/CODEMANIFEST` — Imports extended (`FlowDocument`,
  `FlowTeamMember`, `FlowAssistant`, `collaboration-emission`, `assistants`);
  `write_afm_config` fully replaced (flow + workflow parameters, generated
  profiles, env closures, `limits.max_tasks`, kill-switch stance);
  `run_pipeline` step 16 + threading requirements; `apply_skip_stages`
  verbatim-carry rule; collaboration-delivery paragraph.

### New Entities

| Entity | Cell | Location | Kind |
|---|---|---|---|
| `WorkflowAssistant` | workflow | `workflow_assistant.py` | Entity (data model) |
| `WorkflowDelegation` | workflow | `workflow_delegation.py` | Entity (data model) |
| `FlowCollaboration` | compiler | `flow_collaboration.py` | Entity (data model) |
| `FlowTeamMember` | compiler | `flow_team_member.py` | Entity (data model) |
| `FlowAssistant` | compiler | `flow_assistant.py` | Entity (data model) |

### Changed Entities

| Entity | Cell | Change |
|---|---|---|
| `WorkflowStage` | workflow | + `assistants: list[WorkflowAssistant] \| None = None` (last field) |
| `WorkflowDocument` | workflow | + `assistants: dict[str, WorkflowAssistant]` (default empty dict), `delegation: WorkflowDelegation \| None` (last fields) |
| `parse_workflow` | workflow | + steps 6.5–6.8; top-level keys, stage keys, empty rule, return value |
| `FlowDocument` | compiler | + `collaboration: FlowCollaboration \| None`, `team: list[FlowTeamMember] \| None` between `memory` and `stages` |
| `FlowStage` | compiler | `fields` gains the canonical `assistants` slot after `memory_use` (docstring contract) |
| `serialize_flow` | compiler | emits collaboration block, team list, stage-assistant entries |
| `compile_flow` | compiler | step 4.10 (attachment resolution + four checks), step 5 assistants assembly, step 6 collaboration/team assembly |
| `merge_workflow_overlay` | hooks | steps 4a/4b/5a; rebuilt document carries the collaboration fields |
| `WorkflowAmendment.contribute` | hooks | empty-contribution vocabulary gains assistants + delegation |
| `PipelineHooks.amend_workflow` | hooks | step 5 empty-document rule gains assistants + delegation |
| `write_afm_config` | pipeline | signature `(agent, flow=None, workflow=None)`; collaboration plumbing |
| `run_pipeline` | pipeline | step 16 threads `flow_doc` + `overlay.workflow` |
| `apply_skip_stages` | pipeline | rebuild carries `assistants`/`delegation` verbatim |

### Deleted Entities

None.

### Usages and Annotations Changes

- Project usage `.goga/usages/cooks/afm.md` — gained the "Collaboration
  (afm v2.x)" fact base and "goga's stance" (verified against the `v2.0.9`
  binary). This is the authority for the emitted contract.
- New cell practices: `goga/pipeline/workflow/.usages/assistants.md`,
  `goga/pipeline/compiler/.usages/collaboration-emission.md`,
  `goga/pipeline/.usages/collaboration-delivery.md` (connected via `Imports`
  by the compiler and pipeline cells respectively).
- Modified practices: `parse-workflow.md`, `compile-flow.md`,
  `serialize-flow.md`, `checkpoints.md`, `run-pipeline.md`,
  `per-stage-env.md` — all already materialized by apply-architecture.

---

## Applied Fixes

### Fixed CODEMANIFEST Defects

None — `goga lint` reports 0 errors and the four-consistency-dimension audit
(interface↔type, type↔mutation, interface↔interface, annotations↔entity)
found no contract defect. All findings below are code-level.

### Approved Design Decisions (user-confirmed, answer "A")

1. **Unpinned error-message wording** — house-style messages adopted
   verbatim (catalog in "Error Message Catalog" below).
2. **Declaration/reference discriminator** — an attachment entry is a *full
   inline declaration* iff `prompt is not None or skills is not None`
   (identity check, never truthiness). Justification: the parser requires at
   least one of `prompt`/`skills` on every declaration (catalog rule 6.5 and
   the full-inline rule 6.7) and never accepts either on a reference (a map
   carrying only `name`/`gate`/`when`); an authored `prompt: null` /
   `skills: null` is a type error at parse time, so `None` unambiguously
   means "not authored". The discriminator is implemented as a private
   one-line helper in each consuming cell (compiler, hooks, pipeline) —
   cells may not grow undeclared public API.
3. **`write_afm_config` pre-run error type** — `ValueError` (house precedent:
   `apply_stage_env_wrappers`, the amendment delivery). It propagates out of
   `run_pipeline` before any run event fires.
4. **Assistant closure base directory** — `/tmp/goga-assistant-env`
   (mode `0o700`), separate from `/tmp/goga-stage-env`.
5. **`_effective_overrides` merged-entry fix** — the compiler's extend-seed ×
   stages-block merge must pass `assistants=stg.assistants` explicitly or
   attachments on stages that also carry an extend-entry are silently
   dropped (see Trace 2, checkpoint C2.4).

Two deliberate refinements of the approved wording, both required by the
contract text itself (noted here so the implementation does not "correct"
them back):

- The no-agent pre-run errors carry the **authoring site** fragment
  (`at workflow.assistants` / `at workflow.stages.NAME`) because the
  contract pins "naming the assistant and its authoring site (the catalog or
  the stage whose attachment declares it)".
- Attachment-entry field errors are scoped to the entry
  (`workflow.stages.STAGE.assistants.NAME.when`) rather than the stage, so a
  multi-entry list names the offending entry — the same per-field scoping
  the house validators use (`approve must be one of: … in {scope}`).

---

## Entity Interaction and Data Flow

### Interaction Diagram

```
workflow-file (YAML)
      │ parse_workflow                     ┌────────────────────────────────┐
      ▼                                    │ afm engine (v2.x)              │
WorkflowDocument                           │  flow-file: collaboration,     │
  .assistants   dict[name → WorkflowAssistant]  │           team, stages[].assistants │
  .delegation   WorkflowDelegation|None    │  config: collaboration.profiles│
  .stages[*].assistants list[WorkflowAssistant] │         collaboration.limits  │
      │                                   └────────────────────────────────┘
      │                    │                          ▲              ▲
      │ compile_flow       │ merge_workflow_overlay   │ serialize    │ write_afm_config
      ▼                    ▼ (hooks: tool              │ (compiler)  │ (pipeline)
assistant namespace ──────▶ contributions append)      │              │
 = catalog ∪ inline declarations                        │   flow: FlowDocument + workflow:
      │                                                 │     profile ids ← flow
      ▼                                                 │     declarations ← workflow
FlowDocument                                             │     closures ← assistant env
  .collaboration FlowCollaboration (always)              │
  .team         list[FlowTeamMember] (catalog order)     │
  .stages[*].fields["assistants"] list[FlowAssistant] ───┘
```

### Data Flows

**Flow 1 — authoring to flow-file.** `parse_workflow` validates the three
authoring surfaces and materializes defaults → `WorkflowDocument`. The
compiler builds the namespace, resolves attachments, emits the collaboration
block, team list, and per-stage assistant entries → `serialize_flow` →
flow-file bytes.

**Flow 2 — flow-file + workflow to engine config.** `run_pipeline` step 16
passes the compiled `FlowDocument` and the effective `WorkflowDocument` to
`write_afm_config`. The config write walks the flow for referenced profile
ids (`goga-<name>` of every team member and every stage attachment), walks
the workflow for each id's declaration, resolves the command (env closure or
wrapper), and writes `collaboration.profiles` + (when authored)
`collaboration.limits.max_tasks`. The compiled flow is the single source of
truth for which ids exist.

**Flow 3 — tool contributions.** `PipelineHooks.amend_workflow` buffers tool
contributions (each a parsed `WorkflowDocument`, internally
duplicate-name-free), drops empty ones, and `merge_workflow_overlay` composes
the overlay: catalog merge by name (namespace invariant), whole-block
delegation, per-stage append-with-dedup. The merged document feeds Flow 1.

**Flow 4 — skip.** `apply_skip_stages` rebuilds the document carrying
`assistants`/`delegation` verbatim; the compiler removes skipped stages
before the attachment checks, so a skipped stage attaches nothing and its
ids never reach the flow (hence no profile).

### Entity Dependencies

Implementation order (bottom-up, leaves first):

1. `workflow` cell — models + parser (no imports).
2. `compiler` cell — models + `compile_flow`/`serialize_flow` (imports
   workflow types).
3. `hooks` cell — overlay merge (imports `WorkflowDocument` only).
4. `pipeline` cell — `afm_config`, `run_pipeline`, `apply_skip_stages`
   (imports compiler + workflow types).

Facade updates ride with each cell: `goga/pipeline/workflow/__init__.py`
exports `WorkflowAssistant`, `WorkflowDelegation`;
`goga/pipeline/compiler/__init__.py` exports `FlowCollaboration`,
`FlowTeamMember`, `FlowAssistant`. `goga/pipeline/__init__.py` is unchanged
(`write_afm_config` is already exported; its signature change is internal).

---

## Code Stack Trace

### Trace 1: `parse_workflow` — assistants and delegation path

#### Chain

1. **Input**: rendered workflow-file text (the caller owns reading/rendering).
2. `yaml.safe_load` → mapping check → `_extract_top_level(loaded)`.
   New dispatch arms: `assistants` must be a `list` (else
   `non-list assistants block in workflow`); `delegation` must be a `dict`
   (else `non-mapping delegation block in workflow`). Returns an 8-tuple.
   → checkpoint: type match, messages pinned. **passed**
3. `_build_stages(stages_raw)` — per stage, `_validate_stage_field` gains the
   `assistants` arm dispatching to `_build_stage_assistants(name, value)`
   (step 6.7 grammar); the unknown-key message of 6.1.2 lists `assistants`
   last. → checkpoint: `_STAGE_KEYS` extended, empty list normalizes to
   `None`. **passed**
4. `_build_extend(extend_raw)` — `_reject_forbidden_extend_keys` tuple gains
   `"assistants"` (step 6.8). → checkpoint: message
   `assistants is forbidden in workflow.extend.NAME`. **passed**
5. `_build_assistant_catalog(assistants_raw)` (step 6.5) — per entry:
   mapping check → name required/str → unknown-key check (catalog key set;
   `gate`/`when` are unknown here) → per-field validation (`prompt`/`agent`
   str, `skills` list[str], `delegate` bool, `env` via `_validate_stage_env`
   with empty→`None`) → at-least-one-of-prompt-or-skills → name grammar +
   reserved. Returns `dict[str, WorkflowAssistant]` in authored order.
   → checkpoint: every message pinned; defaults materialized
   (`delegate=False`, `gate=False`, `when="checkpoints"`).
   **passed**
6. `_build_delegation(delegation_raw)` (step 6.6) — key set
   {`depth`, `max_tasks`}; `depth` int (bool excluded) ≥ 0, presence-based;
   `max_tasks` int (bool excluded) ≥ 1; `max_tasks` materializes to 50 when
   absent; an empty block is valid (`WorkflowDelegation(depth=None,
   max_tasks=50)`). → checkpoint: bool-is-int excluded like `max_rules`.
   **passed**
7. `_validate_assistant_namespace(assistants, stages)` — walks the catalog
   entries then every stage attachment that is a declaration (discriminator),
   in stage/attachment order; the second occurrence of a name raises
   `duplicate assistant name: NAME`. References never count. → checkpoint:
   references may repeat names freely; the namespace is document-wide (a
   skipped stage's declaration still counts — skip is a compiler concept).
   **passed**
8. Empty-workflow rule counts the new content:
   `prompt is None AND stages empty AND extend empty AND memory is None AND
   build is None AND assistants empty AND delegation is None` → pinned
   message. → checkpoint: assistants-only and delegation-only workflows are
   valid. **passed**
9. **Output**: `WorkflowDocument(..., assistants=assistants,
   delegation=delegation)`.

#### Checkpoint Summary

- Types/messages: passed (all pinned or approved).
- Ordering decision: stage attachments validate inside the stage pass
  (contract 6.1.14 builds `WorkflowStage` from validated values including
  `assistants`); the catalog (6.5) and delegation (6.6) follow the
  extend pass; the duplicate-name pass runs last (it needs the catalog).
  Single-defect files pin exactly one message; multi-defect files surface
  the earlier pass's error — recorded as the deterministic pass order.

### Trace 2: `compile_flow` — collaboration emission (steps 4.10 / 5 / 6)

#### Chain

1. **Input**: pipeline-file path, flow path, optional `WorkflowDocument`.
2. Existing reconstruction (unchanged until 4.9): deep copy → extend embed →
   strict stage-name validation → skip removal → per-stage overrides → loop
   expansion → `expanded_ids` map. → checkpoint: attachments ride the
   `effective` map, never the step bodies (an authored body `assistants` key
   is a structural error — see step 5). **passed**
3. **C2.4 — `_effective_overrides`**: extend-seeded defaults stay
   `assistants=None`; the merged branch adds `assistants=stg.assistants`
   explicitly. Without it, a stage that has both an extend-entry and a
   stages-block entry loses its attachments. → checkpoint: **defect if
   missed** — mandatory touch point (approved decision 5).
4. `_collaboration_emission(workflow, effective, expanded, expanded_ids)`
   (step 4.10): builds `namespace = workflow.assistants ∪ {declarations of
   workflow.stages[*].assistants}` (document-wide, catalog first); for every
   base name with a non-empty effective attachment list and every produced
   id, runs the four checks in contract order (unknown reference → duplicate
   in one stage list → body carries `script` → translated agents exactly
   `["planning"]`, computed as `[translate_role(r) for r in roles]` when
   usable, else the `["auto"]` default); then builds the `FlowAssistant`
   list once per base stage and maps it onto every produced id (uniform
   across loop copies). → checkpoint: references take declaration fields
   (prompt/skills/agent/delegate/env) from the namespace entry and keep
   their own `gate`/`when`; declarations are their own source. **passed**
5. Step 5 assembly: `_reject_authoring_output_keys` gains the
   `assistants` prohibition (pinned message); `_canonical_fields` gains the
   `assistants_fields` argument; `_assemble_assistants` assigns the list
   into the rebuilt fields before the canonical-order loop, which slots it
   after `memory_use` (`_CANONICAL_KEY_ORDER` gains `"assistants"` last).
   → checkpoint: the value deep-copies through the canonical loop like every
   other field; `None`/empty assembles no key. **passed**
6. Step 6 assembly: `collaboration = FlowCollaboration(mode="assistants",
   max_depth=workflow.delegation.depth if delegation present else None)` on
   EVERY compilation (workflow-less included); `team = [FlowTeamMember per
   catalog entry in authored order]` (empty list when no catalog);
   `FlowDocument(..., memory=..., collaboration=..., team=..., stages=...)`.
   → checkpoint: byte-identity — a collaboration-free workflow differs from
   today's output only by the `collaboration: {mode: assistants}` block;
   `PipelineDocument` and the source bodies stay untouched. **passed**
7. **Output**: `(PipelineDocument, FlowDocument)`; `serialize_flow` writes
   the flow-file.

#### Checkpoint Summary

- Type flow `WorkflowAssistant` → `FlowAssistant`/`FlowTeamMember`: passed
  (every emitted field materializes; `instruction = prompt if not None else
  ""`, `skills = skills if not None else []`).
- Interface alignment `compile_flow` ↔ `serialize_flow`: passed (canonical
  order fixed at assembly; serializer never reorders).
- Mutation/embedding rules: no new mutations or embeddings. **passed**

### Trace 3: `serialize_flow` — new keys

#### Chain

1. **Input**: `FlowDocument` in canonical assembly order.
2. Top level: `prompt` → `root_dir` → `name` → `description` → `memory`
   (when not `None`, `None` fields dropped) → **`collaboration`** (when not
   `None`: block mapping, key order `mode, max_depth`, `max_depth` omitted
   when `None`) → **`team`** (when non-empty: block list; each member a
   block mapping `id, title, profile, instruction, skills`; `instruction`
   wrapped in `_BlockLiteralScript` iff it contains `\n`; `skills` a plain
   list, `[]` when empty) → `stages`.
3. Stage fields: the `assistants` value (a `list[FlowAssistant]`) is
   converted in `_build_stage_repr` into a list of ordered mappings
   `profile, title, instruction, mode, trigger, skills` with the same
   `instruction` wrapping; `mode`/`trigger` plain scalars; `skills: []`
   when empty. → checkpoint: `yaml.dump(default_flow_style=False)`
   already renders empty lists as `[]` (the `depends_on: []` precedent) and
   mappings as block style — no new representer needed; the existing
   `_BlockLiteralScript` representer is reused for instructions. **passed**
4. **Output**: canonical YAML string, single trailing newline.

#### Checkpoint Summary

- Placement/slot checks: passed (collaboration between memory and team; team
  before stages; stage assistants after `memory_use`).
- Constraint "do not reorder": passed — conversion preserves the assembled
  key order verbatim.

### Trace 4: `merge_workflow_overlay` — steps 4a / 4b / 5a

#### Chain

1. **Input**: authored base (post decision, post runner-skip) + committed
   contributions in enumeration order.
2. Seed the namespace: authored catalog names ∪ inline-declaration names of
   authored stage entries.
3. **4a `_merge_catalog`**: `merged = dict(authored catalog)`; for each
   contribution, for each catalog entry: dropped when the name is in the
   seed (authored layer wins); otherwise `merged[name] = entry` — a later
   contribution overwrites an earlier one per fresh name (the "later entry
   wins per name" clause); after the loop the namespace becomes
   `seed ∪ merged.keys()`. → checkpoint: each name appears at most once in
   the merged catalog; the invariant statement's third clause
   ("earlier-accepted contribution") is realized for *inline appends* in 5a,
   while contribution-vs-contribution catalog collisions are resolved by
   overwrite — both satisfy "the merged namespace carries each name exactly
   once". **passed** (reading recorded as the design's authoritative
   interpretation of the contract text)
   **Cross-kind collision, outcome pinned**: because `_merge_catalog`
   consults only the authored seed (the catalog pass runs before any stage
   append is accepted, per the contract's 4a → 5a step order), a LATER
   tool's catalog entry displaces an EARLIER tool's inline declaration: the
   catalog entry is accepted, and the earlier declaration is then dropped
   at stage-merge time by the namespace check (the stage loses that
   attachment; the name lives on only as the catalog entry). The mirror
   direction keeps the earlier catalog entry and drops the later
   declaration. Deterministic, invariant-preserving, and the recorded
   reading — pinned by
   `test_overlay_catalog_entry_displaces_earlier_inline_declaration`.
4. **4b `_merge_delegation`**: authored block when present (unbeatable);
   else the last contribution carrying a block wins; no field merging —
   identical to `_merge_memory`. → checkpoint: whole-block. **passed**
5. **5a `_merge_stage_assistants`** (inside `_merge_stage`, which excludes
   `assistants` from the field-set-complete loop per the contract carve-out):
   result = authored list (verbatim, authored order) when present else `[]`;
   `present_on_stage` = its names; for each contribution carrying the stage,
   for each entry in enumeration order: dropped when the name is already on
   the stage; an appended *declaration* additionally dropped when its name
   is in the evolving namespace; accepted entries append, join
   `present_on_stage`, and accepted declarations join the namespace (later
   stages see them). Empty result → `None`. → checkpoint: references never
   claim names; stage processing follows the merged stage order (authored
   names first, then fresh contribution names) — deterministic. **passed**
6. `_STAGE_FIELDS` gains `"assistants"` last; `_STAGE_DEFAULTS` leaves it
   `None`; `WorkflowStage(**values)` carries the merged list.
7. Buffer shape guard in `PipelineHooks.amend_workflow`: the accessed-fact
   tuple gains `"assistants"` and `"delegation"` — without them a
   duck-typed buffer missing the new attributes would raise `AttributeError`
   inside `merge_workflow_overlay`, *outside* the per-hook intercept.
   The empty-document condition gains `not document.assistants and
   document.delegation is None`. → checkpoint: the merged result stays
   declarative (compilable) and the namespace never duplicates. **passed**
8. **Output**: `WorkflowOverlay(workflow=WorkflowDocument(..., assistants=…,
   delegation=…), provenance=…)`; inputs never mutated.

#### Checkpoint Summary

- Interface↔interface (overlay → compiler): passed — the merged document is
  a valid `WorkflowDocument`; duplicate-free namespace is exactly what
  `compile_flow`'s step 4.10 assumes.
- No-raise constraint: passed — every collision is a silent drop.

### Trace 5: `write_afm_config` — collaboration plumbing

#### Chain

1. **Input**: `agent` (effective global agent or `None`), `flow`
   (`FlowDocument` or `None`), `workflow` (`WorkflowDocument` or `None`).
2. Resolve the client wrapper (`agent` only); compose the base content
   (client block, four static fields, observer hook) — unchanged.
3. When `flow is not None and workflow is not None`:
   1. Collect referenced names in order: `[member.id for member in
      flow.team] + [entry.title for stage in flow.stages for entry in
      stage.fields.get("assistants", [])]`, deduplicated preserving first
      occurrence (`FlowTeamMember.id` and `FlowAssistant.title` both carry
      the authored name; the profile binding is `goga-<name>`).
   2. Build the namespace: `workflow.assistants` ∪ inline declarations of
      `workflow.stages[*].assistants` (document order), recording each
      declaration's site (`workflow.assistants` or
      `f"workflow.stages.{stage}"`).
   3. Resolve every profile in memory, no I/O yet: locate the declaration
      (defensive `ValueError` on a name with no declaration — unreachable
      through `run_pipeline` since the compiler enforced resolution); env
      keys validated against `^[A-Za-z_][A-Za-z0-9_]*$` (fail-fast,
      `invalid environment variable name in the {name} assistant env:
      {key!r}`); command = closure path (env case) or
      `resolve_wrapper_path(declaration.agent or agent)`; neither agent
      resolves → the site-carrying `ValueError`. → checkpoint: **both
      pre-run errors fire before any file is written** (closures included).
      **passed**
   4. Materialize closures: `mkdir /tmp/goga-assistant-env` (`0o700`,
      re-chmod like the stage wrapper base), one `goga-<name>` file per env
      assistant, `os.open(..., 0o700)` + `#!/bin/sh\nexport K=V…\nexec
      target "$@"\n` (the `per-stage-env` content contract; file names are
      always `goga-`-prefixed so the `[A-Za-z0-9._-]` name grammar cannot
      produce `.`/`..` path segments).
   5. `profiles = {f"goga-{name}": {"title": name, "command": command,
      "delegate": declaration.delegate}}` — exactly three keys; `limits` =
      `{"max_tasks": workflow.delegation.max_tasks}` only when the
      workflow carries a delegation block.
4. Write the whole file to the fixed home path (`client`, static fields,
   `hooks`, then `collaboration`); return the path. → checkpoint: profiles
   exist exactly for the flow-referenced ids — an attachment removed by a
   stage skip never appears in the flow, so no dead profile; the kill-switch
   (`collaboration.enabled` / `AFM_COLLABORATION`) is neither read nor
   written. **passed**
5. **Output**: the written `Path`.

#### Checkpoint Summary

- Type flow `FlowDocument`/`WorkflowDocument` → config dict: passed
  (`FlowTeamMember`, `FlowAssistant` imported per the manifest Imports).
- Error strategy vs. `run_pipeline`: passed — `ValueError` propagates at
  step 16, before the run-creation facts; no events fire, afm never
  launches.

### Trace 6: `run_pipeline` step 16 — threading

#### Chain

1. **Input**: the already-compiled `flow_doc` (step 13) and
   `overlay.workflow` (step 12; the overlay workflow when the amendment
   layer is on, the skip-merged resolved workflow when disabled, `None`
   when nothing resolved).
2. `write_afm_config(config.pipeline.agent, flow_doc, overlay.workflow)` —
   after the prompt materialization, before the composition/launch.
   → checkpoint: `flow_doc` is the exact document the flow-file was
   serialized from (post env-wrapper patch — the stage `command` rewrite
   does not touch profile ids), and `overlay.workflow` is the exact
   document it was compiled from, so the two artifacts cannot diverge.
   **passed**
3. **Output**: config written; the run proceeds to facts and launch; a
   collaboration `ValueError` surfaces here with no events fired.

### Trace 7: `apply_skip_stages` — verbatim carry

#### Chain

1. **Input**: resolved workflow (or `None`), skip names.
2. The rebuild passes `assistants=workflow.assistants if workflow is not
   None else {}` (same object — opaque carry) and
   `delegation=workflow.delegation if workflow is not None else None`.
   → checkpoint: matches the memory/profile/build precedent; `None`
   workflow + skips synthesizes a document with the default empty catalog.
   **passed**
3. **Output**: new `WorkflowDocument`; input never mutated. Skipped stages'
   `WorkflowStage(skip=True)` entries carry `assistants=None` (constructor
   default) — correct: skip removes the stage before the attachment checks.

### Trace 8: `PipelineHooks.amend_workflow` — empty-contribution vocabulary

#### Chain

1. **Input**: committed per-tool buffers.
2. The per-hook buffer shape guard accesses `prompt`, `stages`, `extend`,
   `memory`, **`assistants`, `delegation`** (see Trace 4 step 7).
3. The empty-document condition gains the two new blocks; the warning and
   discard behavior are unchanged. → checkpoint: a delegation-only
   contribution is content (not a no-op) and reaches the merge. **passed**
4. **Output**: `merge_workflow_overlay(workflow, contributions)`.

---

## Algorithm Design

### `WorkflowAssistant` (new, `workflow_assistant.py`)

**Responsibility**: data model of one assistant authoring entry — catalog
declaration, full inline stage declaration, or stage reference (with
overrides). Pure data; no validation, no resolution.

```python
@dataclass(kw_only=True)
class WorkflowAssistant:
    name: str                                  # required, no default
    prompt: str | None = None
    skills: list[str] | None = None
    agent: str | None = None
    delegate: bool = False
    env: dict[str, str] | None = None
    gate: bool = False
    when: str = "checkpoints"
```

Docstring documents every arg (name grammar and uniqueness enforced by
`parse_workflow`; `gate`/`when` authored only on attachments; consumers own
resolution and delivery). Constraints honored: no validation, no profile-id
derivation, no env action.

### `WorkflowDelegation` (new, `workflow_delegation.py`)

**Responsibility**: data model of the delegation block with materialized
defaults.

```python
@dataclass(kw_only=True)
class WorkflowDelegation:
    depth: int | None = None
    max_tasks: int = 50
```

### `parse_workflow` — new/changed internals

**Algorithm** (additions; existing structure preserved):

```
_TOP_LEVEL_KEYS += ("assistants", "delegation")            # message order pinned
_STAGE_KEYS      += ("assistants",)
_ASSISTANT_CATALOG_KEYS = ("name", "prompt", "skills", "agent", "delegate", "env")
_ATTACHMENT_DECLARATION_KEYS = catalog keys + ("gate", "when")
_DELEGATION_KEYS = ("depth", "max_tasks")
_WHEN_VALUES = ("start", "checkpoints", "finish")
_ASSISTANT_NAME_PATTERN = re.compile(r"[A-Za-z0-9._-]+")   # fullmatch
_RESERVED_ASSISTANT_NAME = "assistant"

_build_stage_assistants(stage, value):
  1. non-list → "non-list assistants in workflow.stages.{stage}"
  2. empty → None (absence)
  3. per element, in list order → _build_attachment_entry(stage, element)
  → list[WorkflowAssistant]

_build_attachment_entry(stage, element):
  1. str element → reference: _validate_assistant_name(element) →
     WorkflowAssistant(name=element) (all defaults materialized)
  2. dict element:
     a. keys ⊆ {name, gate, when} → reference with overrides:
        name required+str; gate bool; when domain
     b. else → full inline declaration: unknown-key check against
        _ATTACHMENT_DECLARATION_KEYS; per-field validation (catalog rules);
        gate bool; when domain; at-least-one-of prompt/skills;
        name rules
  3. non-str non-dict element → "invalid assistant entry in
     workflow.stages.{stage}.assistants"
  → WorkflowAssistant

_build_assistant_catalog(raw): step 6.5 over list entries
  (scope workflow.assistants.NAME; unknown keys include gate/when;
   at-least-one; name rules) → dict[str, WorkflowAssistant] (authored order)

_build_delegation(raw): step 6.6 (int checks exclude bool; presence-based;
  max_tasks materialized 50) → WorkflowDelegation | None

_validate_assistant_namespace(assistants, stages):
  seen = set()
  for entry in assistants.values():            # catalog order
      if entry.name in seen: raise "duplicate assistant name: {name}"
      seen.add(entry.name)
  for stage in stages.values():                # authored stage order
      for entry in stage.assistants or []:
          if _is_declaration(entry):
              if entry.name in seen: raise "duplicate assistant name: {name}"
              seen.add(entry.name)
```

`_validate_assistant_name(name)`: non-str handled by the callers'
required/str checks; grammar `fullmatch` else `invalid assistant name:
{name}`; `name == "assistant"` → `assistant name is reserved`.

**Errors** — see the Error Message Catalog; all are `WorkflowSyntaxError`.

**Edge cases**: empty catalog list `assistants: []` → empty dict (and does
not rescue an empty workflow — the empty rule counts `assistants` empty);
`delegation: {}` → `WorkflowDelegation(None, 50)`; `skills: []` on a
declaration satisfies at-least-one (presence, not truthiness) and the entry
is a declaration; `env: {}` → `None`; duplicate reference on one stage list
is legal at parse time (the compiler owns the per-stage duplicate check);
`assistants` on an extend-entry is rejected before any other extend check
ordering change (appended last to the forbidden tuple).

### `FlowCollaboration` / `FlowTeamMember` / `FlowAssistant` (new)

Plain kw-only dataclasses mirroring the emission order:

```python
@dataclass(kw_only=True)
class FlowCollaboration:
    mode: str = "assistants"
    max_depth: int | None = None

@dataclass(kw_only=True)
class FlowTeamMember:
    id: str
    title: str
    profile: str
    instruction: str
    skills: list[str]

@dataclass(kw_only=True)
class FlowAssistant:
    profile: str
    title: str
    instruction: str
    mode: str
    trigger: str
    skills: list[str]
```

### `compile_flow` — collaboration internals

```
_PROFILE_PREFIX = "goga-"
_GATE_MODE = {True: "required", False: "advisory"}
_WHEN_TRIGGER = {"start": "one_shot", "checkpoints": "checkpoints",
                 "finish": "on_completion"}

_is_assistant_declaration(entry) -> entry.prompt is not None or entry.skills is not None

_assistant_namespace(workflow) -> dict[str, WorkflowAssistant]:
  namespace = dict(workflow.assistants)
  for stage in workflow.stages.values():
      for entry in stage.assistants or []:
          if _is_assistant_declaration(entry): namespace[entry.name] = entry
  → namespace (parser/overlay guarantee: no duplicate names)

@dataclass _CollaborationEmission:
  block: FlowCollaboration; team: list[FlowTeamMember];
  assistants_by_id: dict[str, list[FlowAssistant]]

_collaboration_emission(workflow, effective, expanded, expanded_ids):
  1. namespace = _assistant_namespace(workflow)     # None workflow → empty
  2. team = [FlowTeamMember(id=n, title=n, profile=_PROFILE_PREFIX+n,
                            instruction=prompt or "", skills=skills or [])
             for n, e in workflow.assistants.items()]   # authored order
  3. block = FlowCollaboration(mode="assistants",
             max_depth=workflow.delegation.depth if workflow.delegation else None)
  4. step_by_id = {s.name: s for s in expanded}
     for base, produced in expanded_ids.items():
         stage = effective.get(base); attachments = stage.assistants if stage else None
         if not attachments: continue
         seen: set[str] = set()
         for entry in attachments:
             if not _is_assistant_declaration(entry) and entry.name not in namespace:
                 raise "unknown assistant reference in workflow.stages.{base}: {name}"
             if entry.name in seen:
                 raise "duplicate assistant in workflow.stages.{base}: {name}"
             seen.add(entry.name)
             decl = entry if _is_assistant_declaration(entry) else namespace[entry.name]
             for produced_id in produced:
                 body = step_by_id[produced_id].body
                 if "script" in body:
                     raise "assistant is forbidden on a script stage in workflow.stages.{base}: {name}"
                 translated = ([translate_role(r) for r in body["roles"]]
                               if _has_usable_roles(body) else list(_DEFAULT_AGENTS))
                 if translated == ["planning"]:
                     raise "assistant is forbidden on a planning-only stage in workflow.stages.{base}: {name}"
             flow_entries.append(FlowAssistant(
                 profile=_PROFILE_PREFIX + entry.name, title=entry.name,
                 instruction=decl.prompt if decl.prompt is not None else "",
                 mode=_GATE_MODE[entry.gate], trigger=_WHEN_TRIGGER[entry.when],
                 skills=decl.skills if decl.skills is not None else []))
         for produced_id in produced:
             assistants_by_id[produced_id] = flow_entries   # shared; deep-copied at assembly
```

Assembly wiring: `_reconstruct_body` returns the emission as a fourth value;
workflow-less compiles construct the default emission
(`block=FlowCollaboration(mode="assistants", max_depth=None), team=[],
assistants_by_id={}`). `_canonical_fields` gains `assistants_fields`;
`_assemble_assistants(source, assistants)` assigns when non-empty;
`_CANONICAL_KEY_ORDER` gains `"assistants"`; `_reject_authoring_output_keys`
gains the pinned prohibition; `_effective_overrides` merged branch gains
`assistants=stg.assistants`; `FlowDocument(... collaboration=emission.block,
team=emission.team ...)`.

**Errors**: the four structural errors above (contract order per entry:
unknown → duplicate → script → planning).

**Edge cases**: skipped stage → removed before the loop, attachments never
checked, no ids in the flow, no profile later; loop-expanded copies share
the same `FlowAssistant` list (uniform) and each copy's body is checked;
`roles` missing → default `["auto"]` never trips the planning check;
`workflow=None` → block only.

### `serialize_flow`

```
if doc.collaboration is not None:
    top["collaboration"] = {"mode": …, "max_depth": …}   # max_depth dropped when None
if doc.team:                                             # empty/None → omitted
    top["team"] = [_member_repr(m) for m in doc.team]

_member_repr(m) = {"id": …, "title": …, "profile": …,
                   "instruction": _BlockLiteralScript(m.instruction) if "\n" in m.instruction else m.instruction,
                   "skills": m.skills}

# in _build_stage_repr, for the "assistants" key (value: list[FlowAssistant]):
[{"profile": e.profile, "title": e.title,
  "instruction": wrapped-or-plain(e.instruction),
  "mode": e.mode, "trigger": e.trigger, "skills": e.skills} for e in value]
```

### `merge_workflow_overlay` — hooks internals

```
_STAGE_FIELDS += ("assistants",)                 # last; _STAGE_DEFAULTS keeps None
_is_assistant_declaration(entry)                 # same one-line rule as the compiler

merge_workflow_overlay(base, contributions):
  1. passthrough when no contributions (unchanged)
  2. namespace = {authored catalog names} ∪ {declaration names of authored stage entries}
  3. assistants = _merge_catalog(base, contributions, namespace)
       merged = dict(base.assistants) if base else {}
       for c in contributions:
           for name, entry in c.document.assistants.items():
               if name in seed: continue          # seed = the step-2 namespace snapshot
               merged[name] = entry               # later contribution wins per name
       namespace |= merged.keys()
  4. delegation = _merge_delegation(base, contributions)      # whole block, like memory
  5. stages = _merge_stages(base, contributions, namespace)   # threads the namespace
       _merge_stage: field loop SKIPS "assistants";
         values["assistants"] = _merge_stage_assistants(...)
  6. WorkflowDocument(prompt, stages, extend, memory, profile, build,
                      assistants, delegation)
```

`_merge_stage_assistants(authored_list, stage_name, contributions, namespace)`
as traced in Trace 4 step 5.

### `write_afm_config`

```
_CLOSURE_BASE = Path("/tmp/goga-assistant-env")
_LEGAL_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PROFILE_PREFIX = "goga-"

write_afm_config(agent, flow=None, workflow=None):
  1. wrapper = resolve_wrapper_path(agent) if agent is not None else None
  2. content = {client? , theme, open_browser, proxy, prompts_dir, hooks}   # unchanged
  3. if flow is not None and workflow is not None:
       content["collaboration"] = _collaboration_section(agent, flow, workflow)
  4. write whole file (yaml.safe_dump, sort_keys=False) → return path

_collaboration_section(agent, flow, workflow):
  1. names = ordered-unique([m.id for m in flow.team] +
                            [e.title for s in flow.stages
                             for e in s.fields.get("assistants", [])])
  2. namespace = workflow.assistants ∪ inline declarations (with site)
  3. resolved = {}                                  # name → (title, command, delegate) — no I/O
     for name in names:
         decl, site = namespace[name] or raise ValueError(f"unknown assistant reference in the compiled flow: {name}")
         if decl.env is not None:
             for key in decl.env:
                 if not _LEGAL_ENV_NAME_PATTERN.fullmatch(key):
                     raise ValueError(f"invalid environment variable name in the {name} assistant env: {key!r}")
         target_agent = decl.agent if decl.agent is not None else agent
         if target_agent is None:
             raise ValueError(f"assistant {name} at {site}
                               {'declares env but ' if decl.env is not None else ''}
                               resolved no agent: set its agent or a global agent")
         resolved[name] = (decl.delegate, decl.env, resolve_wrapper_path(target_agent))
  4. _CLOSURE_BASE.mkdir(parents=True, exist_ok=True, mode=0o700); chmod(0o700)
     for name, (_, env, target) in resolved.items():
         if env is not None:
             path = _CLOSURE_BASE / f"{_PROFILE_PREFIX}{name}"
             _write_owner_only(path, _render_closure(env, target))   # local helpers
             command = str(path)
         else:
             command = target
         profiles[f"{_PROFILE_PREFIX}{name}"] = {"title": name, "command": command,
                                                 "delegate": resolved[name][0]}
  5. section = {"profiles": profiles}
     if workflow.delegation is not None:
         section["limits"] = {"max_tasks": workflow.delegation.max_tasks}
     → section
```

`_render_closure(env, target)` = `#!/bin/sh\n` + one `export K=V` per entry
(`shlex.quote`) + `exec target "$@"\n` (the `per-stage-env` content
contract, implemented locally — no cross-module private import);
`_write_owner_only` = `os.open(path, O_WRONLY|O_CREAT|O_TRUNC, 0o700)`.

### `run_pipeline` / `apply_skip_stages`

One-line threading (Trace 6) and the two verbatim-carry fields (Trace 7).

### Error Message Catalog (pinned for tests)

`WorkflowSyntaxError` (parser):

| Condition | Message |
|---|---|
| `assistants:` non-list | `non-list assistants block in workflow` |
| catalog entry non-mapping | `non-mapping assistant entry in workflow.assistants` |
| catalog unknown key (incl. gate/when) | `unknown key in workflow.assistants.NAME: KEY; valid keys: name, prompt, skills, agent, delegate, env` |
| catalog missing name | `name is required in workflow.assistants entry` |
| entry name non-str | `non-str name in workflow.assistants entry` / `non-str name in workflow.stages.STAGE.assistants entry` |
| no prompt and no skills | `assistant NAME requires at least one of prompt or skills` |
| name grammar | `invalid assistant name: NAME` |
| reserved name | `assistant name is reserved` |
| duplicate declaration name | `duplicate assistant name: NAME` |
| `delegation:` non-mapping | `non-mapping delegation block in workflow` |
| delegation unknown key | `unknown key in workflow.delegation: KEY; valid keys: depth, max_tasks` |
| `depth` non-int / < 0 | `non-int value in workflow.delegation.depth` / `depth must be >= 0 in workflow.delegation` |
| `max_tasks` non-int / < 1 | `non-int value in workflow.delegation.max_tasks` / `max_tasks must be >= 1 in workflow.delegation` |
| stage `assistants` non-list | `non-list assistants in workflow.stages.NAME` |
| attachment element non-str non-map | `invalid assistant entry in workflow.stages.NAME.assistants` |
| attachment missing name | `name is required in workflow.stages.NAME.assistants entry` |
| attachment unknown key (declaration) | `unknown key in workflow.stages.STAGE.assistants.NAME: KEY; valid keys: name, prompt, skills, agent, delegate, env, gate, when` |
| `gate` non-bool | `non-bool value in workflow.stages.STAGE.assistants.NAME.gate` |
| `when` out of domain | `when must be one of: start, checkpoints, finish in workflow.stages.STAGE.assistants.NAME` |
| `assistants` in extend-entry | `assistants is forbidden in workflow.extend.NAME` |
| top-level unknown key | `… valid keys: prompt, stages, extend, memory, profile, build, assistants, delegation` |
| stage unknown key | `… valid keys: agent, env, prompt, loop, skills, skip, approve, manual, notes, reflect, memory, assistants` |
| empty workflow | `empty workflow — provide at least prompt, one stage, one extend entry, the memory block, the build block, the assistants block, or the delegation block` |

`StructuralError` (compiler):

| Condition | Message |
|---|---|
| reference names no namespace member | `unknown assistant reference in workflow.stages.NAME: X` |
| same name twice in one stage list | `duplicate assistant in workflow.stages.NAME: X` |
| attachment on a script stage | `assistant is forbidden on a script stage in workflow.stages.NAME: X` |
| attachment on a planning-only stage | `assistant is forbidden on a planning-only stage in workflow.stages.NAME: X` |
| authored `assistants` in a stage body | `assistants key is forbidden in stage body; use assistants in workflow.stages` |

`ValueError` (`write_afm_config`):

| Condition | Message |
|---|---|
| illegal env key | `invalid environment variable name in the NAME assistant env: 'KEY'` |
| no agent (env assistant) | `assistant NAME at SITE declares env but resolved no agent: set its agent or a global agent` |
| no agent (plain assistant) | `assistant NAME at SITE resolved no agent: set its agent or a global agent` |
| flow references an undeclared name (defensive) | `unknown assistant reference in the compiled flow: NAME` |

---

## Cross-cutting Concerns

- **Error handling**: two-layer validation is preserved — structural
  (parser, `WorkflowSyntaxError`) vs cross-reference (compiler,
  `StructuralError`) vs delivery (`write_afm_config`, `ValueError`). The
  config-write errors are strict pre-run: they fire before any file is
  written and before any run event; `run_pipeline` does not catch them.
- **Logging**: the compiler logs nothing new for collaboration (byte-stable
  transformation); `write_afm_config` logs one `logger.info` after the write
  (`"wrote afm collaboration plumbing"`, extra: profile count / has-limits)
  — no env values, no commands (constraint: never print env values or
  configuration content).
- **Validation**: name grammar, uniqueness, key sets, domains, and types at
  parse; reference/script/planning/duplicate at compile; env-key legality
  and agent resolvability at delivery. No layer re-validates another
  layer's vocabulary (contract constraint).
- **Caching**: none. Closures are regenerated on every launch by design —
  the authored workflow-file is the durable store, the artifacts are
  per-launch.
- **Concurrency**: no new shared state; all merges are pure (inputs never
  mutated), all emission values are fresh objects or shared immutables
  deep-copied at assembly.
- **Security**: closures are owner-only from the first byte (`os.open`
  `0o700`, never create-then-chmod); base directory `0o700`; env keys
  validated against the sh identifier grammar before any file write; file
  names are always `goga-`-prefixed so no `.`/`..` segment can occur; the
  project-layer `.afm/config.yaml` is never touched (the `goga-` prefix is
  the user's deliberate override channel).

---

## Usages Analysis

### `convention` (project, all cells)
- **What it provides**: code style, docstring style, exception message
  formatting, REPL cycle, test infrastructure rules.
- **Where used**: every new/changed module and test.
- **Why chosen**: house baseline.
- **How exactly**: google-style docstrings with `Args:`/`Returns:`/
  `Raises:`; one module per contract type; `ValueError`/`WorkflowSyntaxError`
  message shapes mirrored from existing validators.

### `afm` (project, `.goga/usages/cooks/afm.md`) — compiler + pipeline
- **What it provides**: the engine's collaboration contract — profile shape
  (`title`, `command` required and non-inheriting, `delegate`), stage-helper
  keys (`profile` required; `mode` advisory|required; `trigger`
  one_shot|checkpoints|on_completion; engine defaults advisory/one_shot),
  team-member keys (`id` `[A-Za-z0-9._-]`, `profile`, `title`,
  `@assistant` reserved), flow-overridable keys (`mode`, `max_depth` only),
  config-layer keys (`profiles`, `limits`), the kill-switch stance.
- **Where used**: `compile_flow` (vocabularies and mappings),
  `serialize_flow` (key order), `write_afm_config` (profile/limits shape).
- **Why chosen**: verified against the `v2.0.9` binary in the image — the
  single authority for the emitted surface.
- **How exactly**: `_GATE_MODE` / `_WHEN_TRIGGER` mappings;
  `collaboration: {mode: assistants}` always (flow is the only layer goga
  authors, precedence flow > project > global); `checkpoints` written
  explicitly because the engine default is `one_shot`; profiles exactly
  `{title, command, delegate}`; `limits.max_tasks` only with a delegation
  block.

### `assistants` (imported, `goga/pipeline/workflow/.usages/assistants.md`) — compiler + pipeline
- **What it provides**: the authoring vocabulary — three entry forms, key
  tables, defaults, the complete structural-error table, anti-patterns.
- **Where used**: compiler step 4.10 (reference/declaration semantics),
  `write_afm_config` (declaration fields and env delivery).
- **Why chosen**: the consumer-facing mirror of the parser contract.
- **How exactly**: the discriminator (`prompt`/`skills` presence) and the
  reference-takes-declaration-fields rule are read from its entry-form
  section.
- Path: `goga/pipeline/workflow/.usages/assistants.md`

### `collaboration-emission` (imported, `goga/pipeline/compiler/.usages/collaboration-emission.md`) — pipeline
- **What it provides**: the compiled flow surface — always-emitted block,
  team table, attachment table, compilation checks.
- **Where used**: `write_afm_config` (where the profile ids are read from).
- **Why chosen**: the flow is the single source of truth for the profile
  set; this practice documents that surface.
- **How exactly**: ids collected from `flow.team` members and stage
  `assistants` entries.
- Path: `goga/pipeline/compiler/.usages/collaboration-emission.md`

### `resolve-wrapper-path` (imported, `goga/agents`) — pipeline
- **What it provides**: `resolve_wrapper_path` — agent name → in-container
  wrapper path (pure string composition).
- **Where used**: the client command and every generated profile command.
- **Why chosen**: the single resolution site (contract: "the command
  resolved the stage-agent way").
- **How exactly**: `resolve_wrapper_path(agent)` for the client and plain
  assistants; the closure path replaces it for env assistants.

### `per-stage-env` (cell-level, `goga/pipeline/.usages/per-stage-env.md`) — pipeline
- **What it provides**: the sh-closure delivery pattern and the new
  "Assistant env" section (closure path becomes the profile command).
- **Where used**: `write_afm_config` closure rendering.
- **Why chosen**: same mechanism, second consumer.
- **How exactly**: `#!/bin/sh` + `export` lines + `exec target "$@"`,
  owner-only file, per-launch regeneration.

### `parse-workflow`, `memory`, `compile-flow`, `serialize-flow`, `memory-emission`, `checkpoints`, `run-flow`, `profiles`, `load-workflow` (imported/declared)
Unchanged in role; the collaboration paths follow the same patterns they
document (extraction normalization, emission companions, canonical slots,
overlay merge vocabulary). All still referenced by at least one annotation
(lint-verified).

---

## `.usages/` Update

Status: **all practice files were materialized by the apply-architecture
stage** (new: `assistants.md`, `collaboration-emission.md`,
`collaboration-delivery.md`; modified: `parse-workflow.md`,
`compile-flow.md`, `serialize-flow.md`, `checkpoints.md`,
`run-pipeline.md`, `per-stage-env.md`). This design stage re-read them and
confirms they match the contracts and this design (the
`collaboration-emission.md` tables equal the `_collaboration_emission`
mapping; `assistants.md` error table equals the parser catalog; the
`collaboration-delivery.md` profile table equals `_collaboration_section`).
**No further `.usages/` change is required by the code design.** One
follow-up note for the implementation stage: if any error message is
re-worded during implementation, `assistants.md`'s error table must be
updated in the same change (it duplicates the parser messages verbatim).

---

## Test Stack Trace

### General Setup

- Parser tests: plain `parse_workflow(text)` calls on YAML literals;
  `pytest.raises(WorkflowSyntaxError, match=…)`.
- Compile tests: write a pipeline-file + optional workflow-file into
  `tmp_path`, `WorkflowDocument` via `parse_workflow`, call `compile_flow`,
  assert on the returned `FlowDocument` and the written flow-file text.
- Serialize tests: construct `FlowDocument` directly, `serialize_flow`,
  assert the exact YAML string (golden snippets).
- Overlay tests: construct base/contribution documents, `merge_workflow_overlay`,
  assert the rebuilt document (existing `tests/pipeline/hooks/test_overlay.py`
  fixtures).
- Config tests: `_afm_config_module._AFM_CONFIG_PATH` patched into `tmp_path`
  (existing `config_path` fixture); `_CLOSURE_BASE` patched likewise;
  `FlowDocument`/`WorkflowDocument` built in memory.
- Run tests: the existing `_in_container_run_context` autouse fixture; the
  fake `_write_afm_config` updated to the new signature (see Additional
  Instructions).

### Source File Registry

New: `goga/pipeline/workflow/workflow_assistant.py`,
`workflow_delegation.py`; `goga/pipeline/compiler/flow_collaboration.py`,
`flow_team_member.py`, `flow_assistant.py`.
Changed: `parse_workflow.py`, `workflow_stage.py`, `workflow_document.py`,
`workflow/__init__.py`, `compile_flow.py`, `serialize_flow.py`,
`flow_document.py`, `flow_stage.py`, `compiler/__init__.py`,
`hooks/overlay.py`, `hooks/events.py`, `hooks/amendments.py`,
`afm_config.py`, `run_pipeline.py`, `apply_skip_stages.py`,
`stage_env_wrappers.py` (one line — see Additional Instructions item 9).

### New Test Files

- `tests/pipeline/workflow/test_workflow_assistant_contract.py`,
  `test_workflow_delegation_contract.py` (+logic variants per the
  house pair when behavior exists; these are pure data models, so the
  contract file asserts fields/defaults/order).
- `tests/pipeline/workflow/test_parse_workflow_assistants.py` — steps
  6.5–6.8 coverage.
- `tests/pipeline/compiler/test_flow_collaboration_contract.py`,
  `test_flow_team_member_contract.py`, `test_flow_assistant_contract.py`.
- `tests/pipeline/compiler/test_compile_flow_collaboration.py`.
- `tests/pipeline/compiler/test_serialize_flow_collaboration.py`.
- `tests/pipeline/hooks/test_overlay_assistants.py`.
- `tests/pipeline/test_afm_config_collaboration.py`.

### Extended Test Files

- `tests/pipeline/workflow/test_workflow_stage_contract.py` (+ `assistants`
  field default/annotation), `test_workflow_document_contract.py` (+
  `assistants`/`delegation` defaults), `test_parse_workflow_contract.py` /
  `test_parse_workflow_logic.py` (top-level key set, stage key set, empty
  rule), `test_parse_workflow_memory.py` untouched.
- `tests/pipeline/compiler/test_flow_document_contract.py` (signature),
  `test_compile_flow.py` (byte-identity), `test_data_models.py`.
- `tests/pipeline/test_afm_config.py` (**signature test must change**),
  `tests/pipeline/test_run_pipeline.py` (fake signature + threading
  assertions), `tests/pipeline/test_apply_skip_stages.py`.

---

### Positive Tests

#### `test_parse_assistants_catalog_full_form_materializes_defaults`

**Setup**: none (pure text).

**Input**:
```yaml
assistants:
  - name: reviewer
    agent: claude
    delegate: true
    skills: [code-audit]
    prompt: |
      Review the stage changes.
stages:
  build:
    assistants:
      - name: reviewer
        gate: true
        when: finish
```

**Trace**:
```
parse_workflow(text)
  → _extract_top_level → assistants_raw list, stages_raw dict
  → _build_stage("build") → _build_stage_assistants → reference-with-overrides
      → WorkflowAssistant(name="reviewer", gate=True, when="finish")
  → _build_assistant_catalog → WorkflowAssistant(name="reviewer",
      prompt="Review the stage changes.\n", skills=["code-audit"],
      agent="claude", delegate=True, env=None, gate=False, when="checkpoints")
  → _validate_assistant_namespace → one declaration name, no duplicate
  → WorkflowDocument(assistants={"reviewer": …}, stages={"build": …})
```

**Assertions**:
```
doc.assistants.keys() == ["reviewer"]                      # authored order
doc.assistants["reviewer"].delegate is True
doc.assistants["reviewer"].gate is False                   # catalog default
doc.assistants["reviewer"].when == "checkpoints"           # catalog default
doc.stages["build"].assistants[0].gate is True             # attachment override
doc.stages["build"].assistants[0].prompt is None           # reference carries none
doc.delegation is None
```

**Sufficiency**: pins the one-entry-model rule — a catalog entry and a
reference share the type; attachment overrides do not leak into the catalog
object.

#### `test_parse_attachment_three_entry_forms`

**Setup**: none.

**Input**:
```yaml
stages:
  build:
    assistants:
      - reviewer
      - name: reviewer2
        gate: true
      - name: security
        agent: codex
        prompt: Audit.
        when: start
```
(with a catalog declaring `reviewer`, `reviewer2`)

**Trace**:
```
parse_workflow → _build_stage_assistants("build")
  → element 1: bare str → WorkflowAssistant(name="reviewer")           (all defaults)
  → element 2: keys ⊆ {name, gate} → reference with overrides
  → element 3: carries "agent" → full inline declaration (at-least-one satisfied by prompt)
```

**Assertions**:
```
[ (a.name, a.gate, a.when, a.prompt) for a in doc.stages["build"].assistants ] ==
[("reviewer", False, "checkpoints", None),
 ("reviewer2", True, "checkpoints", None),
 ("security", False, "start", "Audit.")]
```

**Sufficiency**: the three authoring forms of contract 6.7 and their
materialized defaults.

#### `test_parse_delegation_block_materializes_max_tasks`

**Input**: `delegation: {depth: 3}` (+ one stage so the file is non-empty).

**Trace**: `_build_delegation` → presence-based reads → `WorkflowDelegation(depth=3, max_tasks=50)`.

**Assertions**: `doc.delegation.depth == 3; doc.delegation.max_tasks == 50`.
Empty block `delegation: {}` → `(None, 50)`. `max_tasks: 7` → 7.

**Sufficiency**: the materialized-default rule (engine default 20 is never
relied upon).

#### `test_compile_collaboration_block_always_emitted`

**Setup**: pipeline-file (phases, one stage) in `tmp_path`; `workflow=None`.

**Trace**:
```
compile_flow(pipeline_path, flow_path, workflow=None)
  → default _CollaborationEmission(block=FlowCollaboration("assistants", None), team=[], …)
  → FlowDocument(collaboration=block, team=[])
  → serialize_flow → flow-file text
```

**Assertions** (written text):
```
"collaboration:\n  mode: assistants\n" in text
"max_depth" not in text
"team:" not in text
```
And the remainder of the text is byte-identical to a pre-change golden
except that block (checked by removing the two lines and comparing).

**Sufficiency**: the one deliberate byte-level change; guards the
byte-identity invariant for collaboration-free and workflow-less compiles.

#### `test_compile_team_and_stage_attachments_full_materialization`

**Setup**: catalog `reviewer` (prompt/skills), delegation depth 2; stage
`build` attaches `reviewer` with `gate: true, when: finish`.

**Trace**:
```
compile_flow → _collaboration_emission
  → team = [FlowTeamMember(id="reviewer", title="reviewer", profile="goga-reviewer",
        instruction="Review.", skills=["code-audit"])]
  → attachments: reference resolves against namespace → decl fields
  → assistants_by_id["build"] = [FlowAssistant(profile="goga-reviewer", title="reviewer",
        instruction="Review.", mode="required", trigger="on_completion", skills=["code-audit"])]
  → serialize_flow
```

**Assertions** (flow-file text):
```
team block: "- id: reviewer\n  title: reviewer\n  profile: goga-reviewer\n  instruction: Review.\n  skills:\n  - code-audit\n"
stage block contains "assistants:" after memory/reflect slots with:
  "  assistants:\n  - profile: goga-reviewer\n    title: reviewer\n    instruction: Review.\n    mode: required\n    trigger: on_completion\n    skills:\n    - code-audit\n"
"max_depth: 2" present in the collaboration block
```
Layout note (verified against `yaml.dump` run with the `serialize_flow`
parameters `indent=2`, `default_flow_style=False`): a list item's dash sits at
the PARENT key's indentation (column 0 under a top-level `team:`, column 2
under a stage's `assistants:`), the item's own keys at dash-indent + 2, and a
nested list's items at the KEY's indentation — never indented under their key.
The serializer produces exactly this with no change; do not "fix" the
indentation by altering the dumper (that would break byte-identity with the
existing stage rendering).
And `flow_doc.stages[i].fields["assistants"][0].trigger == "on_completion"`.

**Sufficiency**: every emitted key materializes; `checkpoints` written
explicitly; profile binding `goga-<name>`.

#### `test_compile_attachments_uniform_across_loop_copies`

**Setup**: stage `build` with `loop: 3` and one attachment.

**Trace**: `_expand_loops` produces `build-1..3`; the emission maps the same
`FlowAssistant` list onto all three ids.

**Assertions**: all three serialized stage blocks carry identical
`assistants:` entries; the flow references `goga-<name>` three times (one
profile still — verified on the config side).

**Sufficiency**: the uniformity rule and the no-dead-profile premise.

#### `test_serialize_collaboration_styles`

**Input**: hand-built `FlowDocument` with a multi-line team instruction and
an assistant whose `skills` is `[]` and `instruction` is `""`.

**Assertions** (exact golden):
```
instruction: |     (block-literal for the multi-line member)
skills: []          (explicit empty list)
instruction: ''     (empty string plain scalar)
key order mode → max_depth; id → title → profile → instruction → skills;
profile → title → instruction → mode → trigger → skills
```

**Sufficiency**: the style rules that keep the flow-file canonical.

#### `test_overlay_catalog_merge_later_tool_wins_and_namespace_drop`

**Setup**: base catalog `{reviewer}`; contribution A catalog `{reviewer, qa}`;
contribution B catalog `{reviewer, qa, ops}`.

**Trace**:
```
seed = {reviewer}
A: reviewer dropped (seed); qa accepted
B: reviewer dropped (seed); qa OVERWRITTEN by B's entry; ops accepted
```

**Assertions**: `merged.assistants.keys() == ["reviewer", "qa", "ops"]`;
`merged.assistants["qa"] is B's entry object`.

**Sufficiency**: pins the authoritative catalog-merge reading (authored wins,
later-wins overwrite among tools, namespace never duplicates).

#### `test_overlay_stage_assistants_append_with_dedup`

**Setup**: authored stage `build` attaches `[reviewer(gate=true)]`; tool 1
attaches `[reviewer, security(decl)]`; tool 2 attaches `[security(decl), audit(ref)]`.

**Trace**:
```
present = {reviewer}; namespace = {reviewer}
tool1: reviewer dropped (on stage); security declaration accepted → namespace + security
tool2: security dropped (namespace); audit reference accepted
```

**Assertions**: stage list names in order `["reviewer", "security", "audit"]`;
the merged document's namespace has each name once; an authored inline
declaration on another stage blocks a tool's same-name declaration
(covered by a sibling test).

**Sufficiency**: the 5a rules — including that references are dropped only
by the on-stage rule, never by the namespace rule.

#### `test_afm_config_profiles_exactly_for_referenced_ids`

**Setup**: `config_path` fixture; flow with team `[reviewer]` + stage
attachment `goga-reviewer` + stage attachment `goga-security` (security
declared inline, attached on a stage); workflow catalog `{reviewer}`, inline
`security`; `agent="claude"`.

**Trace**:
```
write_afm_config("claude", flow, workflow)
  → names = [reviewer, security]           # dedup: team first, then stage entries
  → decls located (reviewer@catalog, security@workflow.stages.build)
  → commands = wrapper paths (no env)
  → content["collaboration"] = {"profiles": {"goga-reviewer": {title, command, delegate},
                                             "goga-security": {…}}}
```

**Assertions** (parsed YAML at the patched path):
```
config["collaboration"]["profiles"].keys() == ["goga-reviewer", "goga-security"]
each profile == {"title": <name>, "command": "/home/goga/bin/<agent>-as-claude.sh", "delegate": <bool>}
"limits" not in config["collaboration"]            # no delegation block
config["client"]["command"] == "/home/goga/bin/claude-as-claude.sh"   # unchanged base
```

**Sufficiency**: the single-source-of-truth rule — profile set = flow
references; exactly three keys per profile.

#### `test_afm_config_env_closure_delivery`

**Setup**: catalog assistant `reviewer` with `env={"REVIEW_MODE": "strict"}`
and `agent="codex"`; `_CLOSURE_BASE` patched into `tmp_path`; flow team
`[reviewer]`.

**Trace**:
```
env keys validated → closure written at <tmp>/goga-assistant-env/goga-reviewer (mode 0o700)
→ profile command == str(closure path)
→ closure text == '#!/bin/sh\nexport REVIEW_MODE=strict\nexec /home/goga/bin/codex-as-claude.sh "$@"\n'
```

**Assertions**: file content exact; `stat().st_mode & 0o777 == 0o700`;
profile `command` equals the closure path; `delegate` from the declaration.

**Sufficiency**: the env-delivery channel (ADR #6) and the owner-only
guarantee.

#### `test_afm_config_max_tasks_only_with_delegation`

**Input pair**: workflow without `delegation` (no `limits`); with
`delegation {max_tasks: 7}` → `limits == {"max_tasks": 7}`; with
`delegation {}` → `{"max_tasks": 50}`.

**Sufficiency**: the budget channel and materialization.

#### `test_run_pipeline_threads_flow_and_workflow_to_config_write`

**Setup**: the existing run-pipeline wiring fakes; `_write_afm_config`
spyrecords `(agent, flow, workflow)`.

**Assertions**: the spy's flow is the object returned by `compile_flow`
(`flow_doc`) and the workflow is `overlay.workflow` (the merged document
when a tool contributed).

**Sufficiency**: the two artifacts cannot diverge (contract requirement).

#### `test_apply_skip_stages_carries_collaboration_verbatim`

**Input**: workflow with catalog + delegation + stage attachments; skip
`["build"]`.

**Assertions**: rebuilt document's `assistants` is the same object
(`is`), `delegation` is the same object, non-skipped stages keep their
attachment lists.

**Sufficiency**: a rebuild that dropped them would silently disable
collaboration for skip-driven runs.

---

### Negative Tests

#### `test_parse_assistants_error_table`

One parametrized case per row of the parser catalog (exact `match=`):

| input fragment | expected message |
|---|---|
| `assistants: {a: 1}` | `non-list assistants block in workflow` |
| `assistants: [x]` | `non-mapping assistant entry in workflow.assistants` |
| `assistants: [{prompt: p}]` | `name is required in workflow.assistants entry` |
| `assistants: [{name: r, gate: true}]` | `unknown key in workflow.assistants.r: gate; valid keys: name, prompt, skills, agent, delegate, env` |
| `assistants: [{name: r, when: start}]` | `unknown key in workflow.assistants.r: when; …` |
| `assistants: [{name: r, agent: c}]` | `assistant r requires at least one of prompt or skills` |
| `assistants: [{name: "a b", prompt: p}]` | `invalid assistant name: a b` |
| `assistants: [{name: assistant, prompt: p}]` | `assistant name is reserved` |
| catalog `r` + stage declaration `r` | `duplicate assistant name: r` |
| `delegation: [1]` | `non-mapping delegation block in workflow` |
| `delegation: {x: 1}` | `unknown key in workflow.delegation: x; valid keys: depth, max_tasks` |
| `delegation: {depth: -1}` | `depth must be >= 0 in workflow.delegation` |
| `delegation: {depth: true}` | `non-int value in workflow.delegation.depth` |
| `delegation: {max_tasks: 0}` | `max_tasks must be >= 1 in workflow.delegation` |
| `stages: {b: {assistants: {}}}` | `non-list assistants in workflow.stages.b` |
| `stages: {b: {assistants: [42]}}` | `invalid assistant entry in workflow.stages.b.assistants` |
| `stages: {b: {assistants: [{gate: true}]}}` | `name is required in workflow.stages.b.assistants entry` |
| `stages: {b: {assistants: [{name: r, when: later}]}}` | `when must be one of: start, checkpoints, finish in workflow.stages.b.assistants.r` |
| `stages: {b: {assistants: [{name: r, gate: "x"}]}}` | `non-bool value in workflow.stages.b.assistants.r.gate` |
| `extend: {n: {assistants: [], before: [b]}}` | `assistants is forbidden in workflow.extend.n` |
| catalog `{name: r, prompt: 42}` | non-str prompt (house style, unpinned) |
| catalog `{name: r, prompt: p, skills: x}` | non-list-of-str skills (house style, unpinned) |
| catalog `{name: r, prompt: p, delegate: "yes"}` | non-bool delegate (house style, unpinned) |
| catalog `{name: r, prompt: p, env: [1]}` | non-mapping assistant env (house style, unpinned) |
| catalog `{name: r, prompt: p, env: {K: 1}}` | non-str value in the assistant env (house style, unpinned) |
| `{}` | the extended empty-workflow message |
| unknown top key | the eight-key valid-keys message |

**Sufficiency**: the complete structural surface, message text pinned
(regression protection for the user-facing errors documented in
`assistants.md`).

#### `test_compile_unknown_reference_raises`

**Input**: stage attaches `"ghost"`; no catalog/declaration.

**Trace**: `_collaboration_emission` — `ghost` is not a declaration and not
in the namespace → first check fires.

**Assertions**: `StructuralError`, message
`unknown assistant reference in workflow.stages.build: ghost`.

#### `test_compile_duplicate_same_stage_raises`

**Input**: `assistants: [reviewer, reviewer]` on one stage (reference +
reference; also reference + declaration variant).

**Assertions**: `duplicate assistant in workflow.stages.build: reviewer`.

**Sufficiency**: afm rejects a profile appearing twice per stage; goga
surfaces it at compile time.

#### `test_compile_script_and_planning_only_rejected`

**Input**: stage body with `script: echo hi` + attachment →
`assistant is forbidden on a script stage in workflow.stages.build: r`;
stage with `roles: [planner]` + attachment →
`assistant is forbidden on a planning-only stage in workflow.stages.build: r`
(also `roles: [planning]` authored directly — same message, proving the
translated comparison).

#### `test_compile_authored_assistants_key_in_stage_body_rejected`

**Input**: pipeline-file stage body carrying `assistants: [...]` directly.

**Assertions**: `assistants key is forbidden in stage body; use assistants in workflow.stages`.

#### `test_afm_config_illegal_env_key_before_any_file`

**Input**: catalog assistant with `env={"BAD-KEY": "v"}`; `_AFM_CONFIG_PATH`
and `_CLOSURE_BASE` under `tmp_path`.

**Assertions**: `ValueError` with
`invalid environment variable name in the reviewer assistant env: 'BAD-KEY'`;
the config path does not exist; the closure directory contains no files.

**Sufficiency**: the "before writing any file" guarantee — no partial
plumbing reaches a launch.

#### `test_afm_config_no_agent_pre_run_error_names_site`

**Input**: `agent=None`; catalog assistant without `agent` (variant: with
`env`).

**Assertions**: `ValueError` matching
`assistant reviewer at workflow.assistants resolved no agent: set its agent or a global agent`
(env variant carries `declares env but`); no config file written.

#### `test_run_pipeline_collaboration_error_fires_no_events`

**Setup**: wiring fakes with a workflow whose assistant resolves no agent
and `config.pipeline.agent is None`.

**Assertions**: `ValueError` propagates; no `run_created` fact recorded; the
launch function never called.

---

### Edge Case Tests

#### `test_parse_assistants_only_workflow_is_valid`

**Input**: `assistants: [{name: r, prompt: p}]` alone → parses; team of one
emitted at compile.

#### `test_parse_delegation_only_workflow_is_valid`

**Input**: `delegation: {}` alone → `WorkflowDelegation(None, 50)`; empty
rule does not fire.

#### `test_parse_empty_assistants_list_equals_absence`

**Input**: `stages: {b: {assistants: []}}` → `doc.stages["b"].assistants is
None`; `assistants: []` top-level → empty dict (and does not rescue an
otherwise-empty workflow).

#### `test_parse_empty_env_and_empty_skills_forms`

**Input**: declaration with `env: {}` → `env is None`; declaration with
`skills: []` + no prompt → still a declaration (presence rule) and passes
at-least-one.

#### `test_parse_delegation_depth_zero_survives_to_max_depth_zero`

**Input**: `delegation: {depth: 0}` (+ one stage so the file is non-empty);
compile with the workflow.

**Trace**: `_build_delegation` → `WorkflowDelegation(depth=0, max_tasks=50)`
(0 is a valid authored int, not an absence); `FlowCollaboration(max_depth=0)`;
`serialize_flow` keeps the key — the omission rule is `is None`, never
truthiness.

**Assertions**: `doc.delegation.depth == 0`; the flow-file text contains
`max_depth: 0` inside the collaboration block.

**Sufficiency**: the falsy-zero trap — a truthiness check anywhere in the
chain (parse, emission, or serialization) would silently drop the authored
"no helper creation" bound (ADR engine assumption 3).

#### `test_compile_skipped_stage_attaches_nothing_and_leaves_no_profile`

**Setup**: workflow with catalog `{reviewer}`, stage `build` (attachment)
skipped via CLI skip; stage `verify` (attachment, not skipped).

**Trace**: skip removal precedes the emission → `build` never checked, never
in the flow; config write materializes `goga-reviewer` for `verify`'s (and
the team's) reference only.

**Assertions**: flow-file has no `build` stage; its `assistants:` appear
only under `verify`; config profiles == `["goga-reviewer"]` (team member +
attachment collapse to one id).

**Sufficiency**: the no-dead-profile invariant end to end.

#### `test_compile_reference_to_inline_declaration_of_another_stage`

**Input**: stage `a` declares `security` inline; stage `b` references
`security`.

**Assertions**: both stages carry `goga-security` entries taking the
declaration's prompt/skills; config locates the declaration at
`workflow.stages.a`.

**Sufficiency**: the namespace is document-wide, not per-stage.

#### `test_compile_collaboration_free_workflow_byte_identical_except_mode`

**Setup**: an existing golden pipeline+workflow pair without collaboration.

**Assertions**: serialized output equals the stored golden with exactly the
`collaboration:\n  mode: assistants\n` block inserted after
`description`/`memory`.

**Sufficiency**: the deliberate-change boundary — nothing else moves.

#### `test_overlay_passthrough_unchanged_and_no_contributions`

**Input**: base with collaboration fields, `contributions=[]`.

**Assertions**: the same object returns (passthrough); with contributions,
inline-declaration drops keep the merged namespace duplicate-free,
including a tool catalog entry colliding with another tool's inline
declaration and the same inline name contributed to two stages.

#### `test_overlay_catalog_entry_displaces_earlier_inline_declaration`

**Setup**: contribution A appends an inline declaration `sec` (prompt
authored) to stage `build`; contribution B carries a catalog entry `sec`.
No authored collaboration content.

**Trace**:
```
seed = {} (nothing authored)
4a: B's catalog "sec" accepted (not in seed) → namespace = {sec}
5a: stage "build" — A's declaration "sec": not on the stage, but "sec" IS in
    the evolving namespace → dropped silently
```

**Assertions**: `merged.assistants.keys() == ["sec"]` and
`merged.assistants["sec"] is B's entry object`;
`merged.stages["build"].assistants` is `None` (the declaration was dropped
— the assistant no longer attaches to the stage); the merged namespace
carries `sec` exactly once.

**Sufficiency**: pins the cross-kind collision outcome of the 4a → 5a pass
order (Trace 4 step 3) — without this test an implementer could flip the
survivor (dropping B's catalog entry instead) with no failing assertion,
silently changing which content reaches the run.

#### `test_write_afm_config_repeated_invocation_safe`

**Input**: two consecutive writes with the same arguments.

**Assertions**: second write replaces the first wholesale (same content);
closures regenerated (same path, truncated content).

**Sufficiency**: the per-launch rewrite contract.

#### `test_kill_switch_never_touched`

**Assertions**: `AFM_COLLABORATION` is never read (`monkeypatch.delenv`
+ no `os.environ` access in the module under test beyond none); the written
config contains no `enabled` key under `collaboration`.

---

## Additional Instructions for the Implementation Agent

1. **Order**: workflow → compiler → hooks → pipeline (per Entity
   Dependencies). Run `pytest tests/pipeline/workflow` per cell before
   moving on; finish with the full suite and `goga lint`.
2. **Existing tests that MUST be updated in the same change** (they pin the
   old surface and will fail otherwise):
   - `tests/pipeline/test_afm_config.py` — `test_write_afm_config_signature_matches_contract`
     asserts `parameters == ["agent"]`; extend to
     `["agent", "flow", "workflow"]` with `None` defaults.
   - `tests/pipeline/test_run_pipeline.py` — the fake
     `_write_afm_config(agent)` (≈ line 1125) must accept the two new
     parameters; add threading assertions.
   - `tests/pipeline/workflow/test_workflow_stage_contract.py`,
     `test_workflow_document_contract.py`,
     `test_parse_workflow_contract.py`/`_logic.py` — field/key-set/empty-rule
     enumerations gain the new values.
   - `tests/pipeline/compiler/test_flow_document_contract.py`,
     `test_compile_flow.py` goldens — the collaboration block is inserted;
     regenerate deliberately and keep the byte-identity assertion of this
     design.
3. **Do not** add public API beyond the contract: no `is_declaration`
   helper on the models, no new exports in any `__init__` beyond the five
   new types, no shared closure module — private one-liners per cell.
4. **Do not** thread attachments through step bodies (the notes/memory
   precedent: companion maps only) — the body-key prohibition depends on it.
5. **Preserve `_effective_overrides`** — the merged branch must pass
   `assistants=stg.assistants` (the silent-drop defect this design guards).
6. Error messages are contractual (catalog above + `assistants.md`); if any
   message must change during implementation, change the practice file in
   the same commit and record the reason.
7. Engine assumptions to verify at implementation time (from the ADR, with
   the `v2.0.9` binary in the image): profile ids tolerate `goga-<name>`;
   `limits.max_tasks` follows project > global precedence; `max_depth: 0`
   suppresses helper creation but not team members. Verify by `afm validate`
   on a compiled fixture, and record deviations in the topic's `todo.md` —
   do not silently widen this design.
8. `docs/features/pipelines/workflows.md` is already updated
   (apply-architecture artifact 5); no documentation change belongs to the
   implementation stage.
9. `stage_env_wrappers.py` — the command-insertion anchor tuple
   `_KEYS_AFTER_COMMAND` gains `"assistants"` (last, after `memory_use`).
   Without it, an env-declaring stage that carries attachments but neither a
   `command` line nor any present anchor key gets its generated `command`
   inserted before `depends_on` — i.e. AFTER `assistants` — breaking the
   canonical key order of the patched flow-file (afm is order-agnostic; the
   invariant is goga's own generated-artifact consistency). The stage-block
   span detection and the `  command:` rewrite are unaffected (assistant
   entries nest at ≥ 4 spaces; block-literal instructions indent deeper
   still).
