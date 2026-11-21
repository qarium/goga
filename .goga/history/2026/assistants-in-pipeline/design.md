# Design Document: `assistants-in-pipeline`

The code-level design for the topic `assistants-in-pipeline`: a pipeline-file
author declares a stage's helper assistants in the stage body itself, every
declaration attaches to its own stage on every run (with a workflow-file or
without one), and the workflow governs the shipped assistants through
origin-aware `stages.<stage>.assistants.<name>` entries (skip veto or additive
extension). This document specifies **what to implement and how** — every
signature, algorithm, error text, and test is elaborated. No implementation
code is written at this stage.

Inputs consumed: the materialized contracts (`goga/pipeline/workflow`,
`goga/pipeline/compiler`, `goga/pipeline/hooks`, `goga/pipeline` CODEMANIFESTs
and their `.usages/` files), `adr.md`, `prd.md`, `task.md`, and `arch.md` in
this topic directory.

User decisions taken at design time (stage dialog, question q1):

- **D1** — the `write_afm_config` profile-gating defect is fixed in the
  contract (applied; see [Applied Fixes](#applied-fixes)).
- **D2** — pipeline-sourced **compile- and delivery-time** errors use
  **dotted site forms symmetric with the workflow side**:
  `pipeline.<stage>` for stage sites and
  `pipeline.<stage>.assistants.<name>` for declaration sites;
  pipeline-sourced **parse-time** errors keep the contract's
  `stage <name>[.assistants.<name>]` form (fixed by `parse_dsl` 4a in the
  compiler CODEMANIFEST). Workflow-sourced messages keep their exact
  existing texts (non-regression).

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/pipeline/workflow/CODEMANIFEST` — `WorkflowAssistant` becomes the
  absence-preserving gate/when/skip model; `parse_workflow` step 6.7 is
  rewritten around the skip-entry form and optional `when`; step 6.5's
  cross-surface duplicate-name rule moves to compilation; `WorkflowStage` /
  `WorkflowDocument` annotations re-describe the stage entries map.
- `goga/pipeline/compiler/CODEMANIFEST` — new entity `PipelineAssistant`
  (`pipeline_assistant.py`); `PhaseStep`/`StageStep` gain the typed
  `assistants` field; `parse_dsl` step 4a (stage-body assistants extraction);
  `compile_flow` step 4.10 rewritten (two-surface namespace, origin-aware
  assembly, extension merge, veto), step 5 (extend-only prohibition), step 6
  (team emission from two sources); header paragraphs for the carriage and
  emission model.
- `goga/pipeline/hooks/CODEMANIFEST` — `merge_workflow_overlay` step 5.1 and
  header describe the form-blind append rule over the new entry forms; the
  overlay stays pipeline-blind.
- `goga/pipeline/CODEMANIFEST` — `PipelineDocument` added to the compiler
  Imports; `write_afm_config` signature gains the `pipeline` parameter with
  steps 3.2/3.3 extended to three-artifact delivery resolution; `run_pipeline`
  step 17 threads the parsed pipeline document; the "Collaboration delivery"
  header paragraph covers the pipeline declarations.

### New Entities

- **`PipelineAssistant`** — `goga/pipeline/compiler/pipeline_assistant.py`.
  Data model of one pipeline-file stage-declared helper:
  `PipelineAssistant(name: str, prompt: str | None = None, skills: list[str] | None = None, when: str, gate: bool = False)`
  — `@dataclass(kw_only=True)`, field order fixed: name, prompt, skills, when,
  gate. `when` has **no default** (no compiler-side engagement default);
  `gate` defaults to `False` (materialized advisory). No delivery fields.

### Changed Entities

- **`WorkflowAssistant`** (`goga/pipeline/workflow/workflow_assistant.py`) —
  `gate: bool = False` → `gate: bool | None = None`;
  `when: str = "checkpoints"` → `when: str | None = None`; new trailing field
  `skip: bool | None = None`. Field order: name, prompt, skills, agent,
  delegate, env, gate, when, skip. Absence stays distinguishable from every
  authored value.
- **`PhaseStep`** / **`StageStep`** (`goga/pipeline/compiler/phase_step.py`,
  `stage_step.py`) — new trailing field
  `assistants: dict[str, PipelineAssistant] | None = None`; the verbatim
  `body` excludes the extracted `assistants` key.
- **`parse_workflow`** (`goga/pipeline/workflow/parse_workflow.py`) — stage
  entry grammar (6.7): skip form, optional `when`, empty-entry rejection;
  6.5: per-map name rules only; `_validate_assistant_namespace` deleted.
- **`parse_dsl`** (`goga/pipeline/compiler/parse_dsl.py`) — step 4a: the
  stage-body `assistants` map extracted into the typed step field.
- **`compile_flow`** (`goga/pipeline/compiler/compile_flow.py`) — step 4.10
  assembly over two surfaces; team emission from catalog + attached pipeline
  declarations; the workflow-less path gains the attachment walk.
- **`write_afm_config`** (`goga/pipeline/afm_config.py`) — new `pipeline`
  parameter; three-artifact delivery resolution; profile gating
  `flow` + (`workflow` or `pipeline`).
- **`run_pipeline`** (`goga/pipeline/run_pipeline.py`) — step 17 passes
  `pipeline_doc` to `write_afm_config`.
- **`merge_workflow_overlay`** (`goga/pipeline/hooks/overlay.py`) — **no
  functional change**; the existing presence-based declaration discriminator
  already yields the form-blind append rule over the new entry forms; only
  docstrings/comments are updated to state it.

### Deleted Entities

- None. (`_validate_assistant_namespace` — an internal parse helper — is
  deleted; it is not a contract entity.)

### Usages and Annotations Changes

Performed by the apply-architecture stage (verified consistent at this stage;
no further changes required):

- `goga/pipeline/workflow/.usages/assistants.md` — governance surface
  (skip veto, extension table, visibility, updated error tables).
- `goga/pipeline/workflow/.usages/parse-workflow.md` — accepted-structure and
  override-key rows.
- `goga/pipeline/compiler/.usages/parse-dsl.md` — "The stage-body
  `assistants` map" section.
- `goga/pipeline/compiler/.usages/collaboration-emission.md` — two-surface
  emission, origin-aware resolution, checks, invariants.
- `goga/pipeline/compiler/.usages/compile-flow.md` — collaboration emission
  section.
- `goga/pipeline/hooks/.usages/checkpoints.md` — form-blind append note.
- `goga/pipeline/.usages/collaboration-delivery.md` — three artifacts,
  delivery-source resolution ladder.
- `goga/pipeline/.usages/run-pipeline.md` — step 17 threading.
- `docs/features/pipelines/workflows.md`, `docs/features/pipelines/pipeline-file.md`
  — rider documentation.

---

## Applied Fixes

### Fixed CODEMANIFEST Defects

- `goga/pipeline/CODEMANIFEST` → `write_afm_config` (defect type:
  **interface ↔ interface consistency — an un-propagated gating condition**;
  the plan added the `pipeline` artifact without widening the materialization
  gate, contradicting SC1, the entity's own header paragraph, the `pipeline`
  parameter annotation, and `.usages/collaboration-delivery.md`):
  - Requirements: "the profiles and the task budget join it only when both
    `flow` and `workflow` are given" → "the profiles join it when `flow` is
    given with `workflow` or `pipeline` (either completes the delivery
    resolution); the task budget joins it only when `workflow` is given".
  - Algorithm step 3: "When `flow` and `workflow` are both not None" → "When
    `flow` is not None and at least one of `workflow` and `pipeline` is not
    None"; the same sentence's "authored workflow plumbing" → "authored
    plumbing" (aligned with the already-updated header paragraph).
  - `workflow` parameter annotation: "None writes no collaboration profiles
    (the section head still writes)" → "None when no workflow resolved — the
    pipeline declarations remain the sole profile source and the task budget
    stays unwritten".
  - Verified after the edit: `goga lint` → 93 cells, 0 errors; the manifest
    still parses as exactly 3 YAML documents.

No other contract defects were found: `goga lint` passes; every `Imports`
resolves; the dependency map is unchanged
(workflow ← compiler ← pipeline; workflow ← hooks ← pipeline) with no cycles;
entity signatures, field orders, and annotations are internally consistent;
the `.usages/` files match the contracts.

---

## Entity Interaction and Data Flow

### Interaction Diagram

```
 pipeline-file (stage bodies carry assistants:)          workflow-file
        │                                                      │
        ▼                                                      ▼
  parse_dsl ──(4a)──► PipelineAssistant ──► PhaseStep/StageStep.assistants
        │                                                      │
        │                                                parse_workflow
        │                                                      │
        │                                     WorkflowAssistant (gate/when/skip
        │                                     absence-preserving; skip veto)
        │                                                      │
        ▼                                                      ▼
        └──────────────────► compile_flow ◄─────────────────────┘
                              (step 4.10 — the ONLY place both documents meet)
                              │  namespace: catalog ∪ inline ∪ pipeline decls
                              │  per stage: pipeline decls first, then wf entries
                              │  veto / extension / reference / inline resolution
                              ▼
                    FlowDocument { collaboration, team, stages[].assistants }
                              │                       │
                              │                       ▼
                              │              serialize_flow → flow-file
                              ▼
                       PipelineDocument (ORIGINAL body — declarations carried)
                              │
   run_pipeline (step 17) ────┤  write_afm_config(agent, flow, workflow, pipeline)
                              ▼
                    afm config: collaboration.profiles.goga-<name>, limits
                              │
   workflow amendment (hooks) │  merge_workflow_overlay — form-blind append,
                              ▼  pipeline-blind; collisions surface at compile
```

### Data Flows

**Flow 1 — authoring (pipeline side).** `parse_dsl` splits header/body, builds
steps; step 4a extracts each step's `assistants` map into
`dict[str, PipelineAssistant]` (deep-copied), excludes the key from the
verbatim body. Declarations ride `PipelineDocument.body` untouched to every
consumer.

**Flow 2 — authoring (workflow side).** `parse_workflow` builds
`WorkflowAssistant` entries with `gate`/`when`/`skip` carried as authored or
`None`. The parser performs NO origin classification and NO cross-surface
uniqueness check.

**Flow 3 — amendment.** `merge_workflow_overlay` merges tool contributions
into the workflow document; every stage-entry form (veto, when-less extension,
reference, declaration) rides the append rule; entries addressing pipeline
names pass through unresolved.

**Flow 4 — compilation.** `compile_flow` builds the working body (deep copy →
extend embed → skip removal → overrides → loop expansion; copies carry the
declarations), then step 4.10 assembles per-stage attachments (pipeline
declarations first, workflow entries second), detects namespace collisions,
enforces the origin-aware `when` check, applies veto/extension, and emits the
team list (catalog then attached pipeline declarations) and the per-stage
`assistants` lists. Output-side only — `PipelineDocument` is never mutated.

**Flow 5 — delivery.** `run_pipeline` step 17 calls `write_afm_config` with
the effective agent, the compiled flow, the effective (overlay) workflow, and
the parsed pipeline document. For each flow-referenced `goga-<name>` id the
delivery source resolves across the workflow namespace and the pipeline
declarations; a pipeline-declared name takes delivery fields from its workflow
extension entry, else the global agent.

### Entity Dependencies

Implementation order (bottom-up; matches the contract dependency map):

1. `goga/pipeline/workflow` — `WorkflowAssistant` model, then `parse_workflow`
   (no dependencies).
2. `goga/pipeline/compiler` — `PipelineAssistant`, `PhaseStep`/`StageStep`,
   `parse_dsl` 4a, then `compile_flow` 4.10 (imports workflow).
3. `goga/pipeline/hooks` — docstring updates only (imports workflow).
4. `goga/pipeline` — `afm_config`, then `run_pipeline` step 17 (imports all).

---

## Code Stack Trace

### Trace: `parse_workflow` (stage entries — contract 6.7)

#### Chain

1. **Input**: the rendered workflow-file text; `_build_stage_assistants(stage,
   value)` receives the raw `assistants` map of `workflow.stages.<stage>`.
2. **Step**: non-mapping value → `WorkflowSyntaxError("non-mapping assistants
   in workflow.stages.<stage>; author the map form keyed by assistant name")`;
   an empty map → `None` (absence). → checkpoint: unchanged behavior ✓.
3. **Step** (per entry): non-mapping entry value → `"non-mapping assistant
   attachment in workflow.stages.<stage>.<name>"` (existing text) ✓.
4. **Step** — skip-form discrimination: `"skip" in entry_value`:
   - any other key present → `"skip cannot be combined with extension keys in
     workflow.stages.<stage>.assistants.<name>"`;
   - value not strictly bool → `"non-bool value in
     workflow.stages.<stage>.assistants.<name>.skip"` (design D2, mirrors the
     `gate` convention);
   - `skip: false` → `"skip: false requires an extension field in
     workflow.stages.<stage>.assistants.<name>"`;
   - `skip: true` → name rules, then `WorkflowAssistant(name=<key>, skip=True)`
     (every other field `None`). → checkpoint: exactly-one-instruction rule ✓.
5. **Step** — empty entry (`{}`) → `"empty assistant entry in
   workflow.stages.<stage>.assistants.<name>"` ✓.
6. **Step** — every other form: the seven-key loop (`prompt`, `skills`,
   `agent`, `delegate`, `env`, `gate`, `when`); unknown key → `"unknown key in
   workflow.stages.<stage>.assistants.<name>: <key>; valid keys: prompt,
   skills, agent, delegate, env, gate, when"`; `gate` strictly bool carried as
   `None` when absent; `when` validated against
   {start, checkpoints, finish, message} **only when authored**, carried as
   `None` when absent; the five declaration fields follow the catalog rules
   verbatim (empty `skills`/`env` preserved as explicit overrides;
   `delegate` absent → `None`). → checkpoint: absence preserved ✓.
7. **Step**: name rules (`[A-Za-z0-9._-]`, reserved `assistant`) — unchanged
   texts (`"invalid assistant name: <name>"`, `"assistant name is
   reserved"`).
8. **Output**: `dict[str, WorkflowAssistant] | None` — **no `when` requirement,
   no cross-surface uniqueness check** (`_validate_assistant_namespace`
   deleted; its call site and the 6.5 duplicate-name wording already updated
   in the contract).

#### Checkpoint Summary

- Entry-form discrimination vs. origin classification: the parser
  discriminates only the syntactic skip form; origin (veto/extension/
  reference/inline) is NOT decided here — matches the workflow cell's
  "pipeline-blind" contract ✓.
- `WorkflowAssistant(gate=..., when=...)` construction sites in the overlay
  (`_override_entry`) compose `None` gate/when safely — the model accepts
  them ✓.

### Trace: `parse_dsl` (step 4a — stage-body assistants)

#### Chain

1. **Input**: `_extract_phase_step(item)` / `_extract_stage_step(name, value)`
   — one parsed step item of either body format.
2. **Step**: `_extract_step_assistants(stage, item)` reads
   `item.get("assistants")`:
   - key absent → `None`;
   - non-mapping → `StructuralError("non-mapping assistants in stage <stage>;
     author the map form keyed by assistant name")`;
   - empty map → `None` (absence).
3. **Step** (per entry): non-mapping entry → `"non-mapping assistant
   declaration in stage <stage>.assistants.<name>"`; then **`when` presence
   first** (mirrors the workflow parser's check-first convention): absent →
   `"when is required in stage <stage>.assistants.<name>"`.
4. **Step** — the four-key loop: `prompt` strictly str (`"non-str value in
   stage <s>.assistants.<a>.prompt"`); `skills` list of str
   (`"non-list-of-str skills in stage <s>.assistants.<a>"`); `when` in the
   four-value domain (`"when must be one of: start, checkpoints, finish,
   message in stage <s>.assistants.<a>"`); `gate` strictly bool
   (`"non-bool value in stage <s>.assistants.<a>.gate"`); any other key →
   `"unknown key in stage <s>.assistants.<a>: <key>; valid keys: prompt,
   skills, when, gate; agent, env, delegate are workflow-file territory"`
   (the delivery-keys clause is contractual — parse-dsl 4a).
5. **Step** — name rules: `"invalid assistant name in stage
   <s>.assistants.<a>: <name>"`; the reserved name keeps the cross-surface
   text `"assistant name is reserved"`.
6. **Step** — content resolution: `prompt is None and skills is None` →
   `"assistant declaration <a> in stage <s> resolves neither prompt nor
   skills"`.
7. **Step**: build `PipelineAssistant(name=<key>, prompt=..., skills=...,
   when=..., gate=<authored or False>)`; the whole map deep-copied
   (`copy.deepcopy`) into the step.
8. **Output**: the step's `assistants` field; the verbatim `body` excludes the
   key (`_PHASE_STEP_KEYS` / `_STAGE_STEP_KEYS` gain `"assistants"`).

#### Checkpoint Summary

- Type flow into `PhaseStep`/`StageStep.assistants` —
  `dict[str, PipelineAssistant]` matches the contract signatures ✓.
- The delivery-key rejection lands at parse time (strictly before any run) ✓;
  delivery keys never enter the model ✓.
- `_deep_copy_without` still deep-copies bodies; declarations deep-copied
  separately — later working-body mutation cannot reach `PipelineDocument` ✓.

### Trace: `compile_flow` (step 4.10 — assembly and emission)

#### Chain

1. **Input**: `compile_flow(pipeline_path, flow_path, workflow=None, ...)`;
   `parse_dsl` → steps carrying `assistants`; empty-body guard; step 4.0.
2. **Step**: workflow path — `_reconstruct_body` (deep copy → extend embed →
   name validation → skip removal → per-stage overrides → loop expansion).
   `_make_expanded_copy` now also deep-copies `assistants` onto every copy;
   extend-embedded steps construct with `assistants=None` (their verbatim
   bodies may still carry a raw `assistants` key — caught by
   `_reject_authoring_output_keys` unchanged, the defensive re-check).
   Workflow-less path — `reconstructed = list(body.steps)` and
   `identity_ids = {step.name: [step.name] for step in reconstructed}`;
   `_collaboration_emission(None, {}, reconstructed, identity_ids)`.
   → checkpoint: pipeline declarations reach the emission on BOTH paths ✓.
3. **Step** — namespace build (`_assistant_namespace(workflow)`): catalog
   (site `workflow.assistants.<name>`) then inline declarations (site
   `workflow.stages.<s>.assistants.<name>`); a repeat within workflow sources
   raises `StructuralError("duplicate assistant name: <name> (<site1>,
   <site2>)")` — the parse-time guarantee is gone, compile owns it now.
4. **Step** — pipeline declaration index: walk `expanded_ids` in order;
   `pipeline_decls[base] = <any produced copy's assistants>`;
   a pipeline name already indexed or present in the workflow namespace →
   the same collision error with the pipeline site
   `pipeline.<s>.assistants.<name>`. → checkpoint: one global uniqueness
   domain; reference resolution below uses the **workflow namespace only**
   (a pipeline declaration stays invisible to other stages) ✓.
5. **Step** — content check: every **workflow** namespace member resolves
   `prompt` or `skills` (existing message `assistant <name> at <site>
   resolves neither prompt nor skills`); pipeline declarations excluded
   (parse-time content rule) ✓.
6. **Step** — per-stage assembly (see Algorithm Design →
   `_assemble_stage_attachments`): pipeline declarations first (veto /
   extension merge), then workflow entries (skip-target error, unknown
   reference, origin-aware `when` check, reference/inline resolution);
   `_reject_attachment_body(site, name, body)` runs per assembled attachment
   per produced id with `site = f"pipeline.{base}"` or
   `f"workflow.stages.{base}"` (workflow messages byte-identical to today).
7. **Output**: `assistants_by_id[produced_id] = [FlowAssistant, ...]` (the
   same list for every loop-expanded copy); attached-pipeline records
   `(name, effective_prompt, effective_skills)` collected in working-body
   order feed `_team_members`.

#### Checkpoint Summary

- Type flow: `PipelineAssistant` → `FlowAssistant`/`FlowTeamMember`
  materialization — every field maps (prompt→instruction with `""` default,
  skills→list with `[]` default, gate→mode, when+gate→trigger) ✓.
- Byte-exactness: with no step carrying `assistants` and no workflow
  collaboration, every new branch is data-empty — output byte-identical ✓.
- `PipelineDocument(header, fmt, body)` still built from the ORIGINAL body ✓.

### Trace: `merge_workflow_overlay` (hooks — form-blind append)

#### Chain

1. **Input**: authored base workflow + committed tool contributions.
2. **Step**: `_authored_namespace` seeds declaration names (catalog + inline);
   `_merge_stage_assistants` appends per stage: name-on-stage drop (any form),
   declaration-shaped append drop vs. the workflow-side namespace
   (`_is_assistant_declaration` — presence of the five declaration fields),
   else append. A `{skip: true}` entry and a gate/when-only entry are not
   declaration-shaped → always append (subject only to the name-on-stage
   drop). → checkpoint: the existing discriminator already implements the
   contracted form-blind rule — **no functional change**; only the docstrings
   and the module comment are updated to state the new forms and the
   pipeline-blind posture ✓.
3. **Output**: merged `WorkflowDocument`; entries addressing pipeline names
   pass through; their collisions surface at compilation with the
   effective-namespace errors ✓.

### Trace: `write_afm_config` (delivery — three artifacts)

#### Chain

1. **Input**: `write_afm_config(agent, flow=None, workflow=None,
   pipeline=None)`; `run_pipeline` step 17 passes all four
   (`pipeline_doc` from `compile_flow`'s return).
2. **Step**: gating — `flow is not None and (workflow is not None or pipeline
   is not None)` → `_collaboration_section(agent, flow, workflow, pipeline)`;
   else the bare static head (fixed contract, D1).
3. **Step**: `_referenced_names(flow)` — unchanged (team members then stage
   attachments, ordered-unique; the flow stays the single source of truth).
4. **Step** — `_resolve_profiles`: for each name, the workflow namespace
   (`_assistant_namespace(workflow)`) first; else the pipeline declaration
   index `_pipeline_declaring_stages(pipeline)` (name → declaring stage from
   `pipeline.body.steps`); delivery =
   `(entry.agent, entry.delegate, entry.env)` of the workflow extension entry
   `workflow.stages[<declaring stage>].assistants.get(name)` (all `None` when
   absent or no workflow); site = `pipeline.<stage>` (D2). A name resolving to
   nothing → the defensive strict pre-run error (existing text).
5. **Step**: command resolution unchanged (non-empty effective env → legal-key
   validation → sh closure; else declaration agent → global agent →
   `"assistant <name> at <site> resolved no agent: set its agent or a global
   agent"`); delegate materializes `False` when `None`.
6. **Output**: `collaboration.profiles.goga-<name> = {title, command,
   delegate}`, `limits.max_tasks` only from the workflow delegation block,
   `command_names` labels — the `{title, command, delegate}` shape unchanged.

#### Checkpoint Summary

- A pipeline-declared name has at most one workflow entry addressing it (its
  own stage's — cross-stage entries die at compile), so the extension lookup
  is unambiguous ✓.
- A vetoed declaration never appears in the flow → never referenced → no
  profile ✓ (no dead profiles).

---

## Algorithm Design

### `WorkflowAssistant` (model)

**Responsibility**: one assistant authoring entry on every workflow surface —
declaration, reference, extension, or veto parameters — with absence preserved
on every attachment parameter.

**Algorithm** (construction only — pure data):

```
1. parse_workflow constructs:
   - catalog entry   → name, prompt?, skills?, agent?, delegate?, env?
                        (gate/when/skip stay None — catalog rejects the keys)
   - skip entry      → name, skip=True (every other field None)
   - other entry     → the seven authored fields; gate/when None when absent
2. consumers discriminate by PRESENCE (never truthiness):
   declaration ⇔ any of prompt/skills/agent/delegate/env is not None
   veto        ⇔ skip is True
```

**Errors**: none (the model validates nothing — parse owns the vocabulary).

**Edge Cases**: `skills: []` / `env: {}` are authored values (explicit
overrides that clear); `delegate`/`gate`/`when`/`skip` absent are `None` —
absence and authored `false` stay distinguishable.

### `parse_workflow` step 6.7 (rewrite)

**Responsibility**: validate the stage-entry map syntactically and build the
entries; decide nothing about origins.

**Algorithm**:

```
1. IF the stage's assistants value is not a mapping
   → raise "non-mapping assistants in workflow.stages.NAME; author the map
     form keyed by assistant name"
2. IF the map is empty → return None
3. FOR each (name, entry_value) in authored order:
   a. IF entry_value is not a mapping
      → raise "non-mapping assistant attachment in workflow.stages.NAME.name"
   b. IF "skip" in entry_value:
      - IF any other key present
        → raise "skip cannot be combined with extension keys in
          workflow.stages.NAME.assistants.name"
      - IF the value is not strictly bool
        → raise "non-bool value in workflow.stages.NAME.assistants.name.skip"
      - IF the value is False
        → raise "skip: false requires an extension field in
          workflow.stages.NAME.assistants.name"
      - validate the name rules; append WorkflowAssistant(name, skip=True)
      - CONTINUE
   c. IF entry_value is empty
      → raise "empty assistant entry in workflow.stages.NAME.assistants.name"
   d. FOR each key of entry_value (seven-key set):
      - gate  → strictly bool, else "non-bool value in … .gate"
      - when  → validated domain (only when authored — the key is here, so
                authored), else "when must be one of: … in …"
      - prompt/agent → str; skills → list[str]; delegate → bool;
        env → str→str map (empty preserved) — catalog rules verbatim
      - any other key → "unknown key in workflow.stages.NAME.assistants.name:
        KEY; valid keys: prompt, skills, agent, delegate, env, gate, when"
   e. validate the name rules
   f. append WorkflowAssistant(name, <fields>, gate=None-or-bool,
      when=None-or-str)
4. RETURN the map  — and DELETE _validate_assistant_namespace + its call
```

**Errors**: listed above; all `WorkflowSyntaxError`.

**Edge Cases**: a gate-only entry (`{gate: true}`) parses (reference form,
`when=None` — the compile-time origin check decides); a when-less entry
addressing nothing fails at compilation, not here; the catalog (6.5) keeps its
five-key set — `gate`/`when`/`skip` are unknown keys there.

### `PipelineAssistant` (model)

**Responsibility**: one pipeline-file stage-declared helper — content and
engagement only.

**Algorithm** (pure data): fields `name, prompt=None, skills=None,
when=<required>, gate=False`; `@dataclass(kw_only=True)` (kw_only keeps the
required `when` after defaulted parameters legal).

**Errors**: none.

**Edge Cases**: `skills: []` is a value (a declaration resolving content);
`gate` materializes `False` when not authored; no default `when` exists.

### `parse_dsl` step 4a

**Responsibility**: extract and validate the stage-body `assistants` map into
the typed step field.

**Algorithm**:

```
1. FOR each parsed step item (both formats):
   a. raw = item.get("assistants")
   b. IF the key is absent → assistants = None; GOTO f
   c. IF raw is not a mapping
      → raise "non-mapping assistants in stage NAME; author the map form
        keyed by assistant name"
   d. IF raw is empty → assistants = None; GOTO f
   e. FOR each (name, entry) in authored order:
      - IF entry is not a mapping
        → raise "non-mapping assistant declaration in stage NAME.assistants.name"
      - IF "when" not in entry
        → raise "when is required in stage NAME.assistants.name"
      - FOR each key (prompt, skills, when, gate):
          prompt → strictly str; skills → list[str];
          when → one of the four values; gate → strictly bool
        any other key → raise "unknown key in stage NAME.assistants.name:
          KEY; valid keys: prompt, skills, when, gate; agent, env, delegate
          are workflow-file territory"
      - name rules → "invalid assistant name in stage NAME.assistants.name:
        name" / "assistant name is reserved"
      - IF prompt is None and skills is None
        → raise "assistant declaration name in stage NAME resolves neither
          prompt nor skills"
      - build PipelineAssistant(name, prompt, skills, when,
        gate=authored-or-False)
   f. assistants = deepcopy(the built map)
   g. body = _deep_copy_without(item, reserved ∪ {"assistants"})
2. RETURN the step carrying (name, title, [depends_on,] body, assistants)
```

**Errors**: all `StructuralError`, texts above (D2).

**Edge Cases**: an empty map equals absence; `when` presence is checked
before the key loop (an empty entry dies as "when is required"); the reserved
name keeps the cross-surface message; the delivery-key clause in the
unknown-key message is contractual.

### `compile_flow` step 4.10 — collaboration emission

**Responsibility**: assemble every stage's effective attachments over the two
authoring surfaces and emit the collaboration block, the team list, and the
per-stage `assistants` lists; the single place both documents meet.

**Algorithm** (`_collaboration_emission(workflow, effective, expanded,
expanded_ids)` and helpers):

```
A. Build the workflow namespace (reference resolution AND the content check):
   ns = {}
   FOR (name, entry) of workflow.assistants            → site
   "workflow.assistants.name"
       IF name in ns → collision error (both sites)
       ns[name] = (entry, site)
   FOR each stage, each entry of stage.assistants
       IF declaration(entry):
           site = "workflow.stages.S.assistants.name"
           IF name in ns → collision error (both sites)
           ns[name] = (entry, site)
B. Build the pipeline declaration index (base stage → map) walking
   expanded_ids in working-body order (loop copies collapse: every copy of
   one base shares the map):
   FOR (base, produced_ids) of expanded_ids:
       decls = <the base's step>.assistants or {}
       IF decls: pipeline_decls[base] = decls
       FOR (name) of decls:
           site = "pipeline.base.assistants.name"
           IF name in ns or name in pipeline_name_sites
             → collision error (both sites)
           pipeline_name_sites[name] = site
C. Content check — every ns member resolves prompt or skills
   (existing message; pipeline declarations are NOT ns members)
D. Per-stage assembly — _assemble_stage_attachments(base, produced_ids):
   wf_entries = effective[base].assistants or {}   ({} without a workflow)
   decls      = pipeline_decls.get(base) or {}
   bodies     = {produced_id → working body}
   assembled  = []; attached_pipeline = []
   1. FOR (name, decl) of decls in authored order:        # pipeline first
      entry = wf_entries.get(name)
      IF entry is not None and entry.skip is True:
          CONTINUE                                        # the veto
      eff_when  = entry.when  if entry and entry.when  is not None else decl.when
      eff_gate  = entry.gate  if entry and entry.gate  is not None else decl.gate
      eff_prompt= join_prompt(decl.prompt, entry.prompt if entry else None)
                  # both authored → "pipeline-text\n\nworkflow-text";
                  # single-sided → that text alone; neither → None
      eff_skills= expand_skills(decl.skills, entry.skills if entry else None)
                  # declaration entries first, then entry entries,
                  # deduplicated by value preserving first occurrence
      FOR pid of produced_ids:
          _reject_attachment_body("pipeline.base", name, bodies[pid])
          # "assistant is forbidden on a script stage in pipeline.base: name"
          # "assistant is forbidden on a planning-only stage in pipeline.base: name"
      assembled.append(FlowAssistant(
          profile="goga-"+name, title=name,
          instruction=eff_prompt or "", mode=_GATE_MODE[eff_gate],
          trigger=_attachment_trigger(eff_gate, eff_when)))
      attached_pipeline.append((name, eff_prompt, eff_skills))
   2. FOR (name, entry) of wf_entries in authored order:  # workflow second
      IF name in decls: CONTINUE                          # consumed above
      IF entry.skip is True
        → raise "skip targets a pipeline-declared assistant in
          workflow.stages.base.assistants.name"
      source = entry if declaration(entry) else ns.get(name)
      IF source is None
        → raise "unknown assistant reference in workflow.stages.base: name"
          # a name pipeline-declared by ANOTHER stage lands here: ns excludes
          # pipeline declarations — the visibility rule
      IF entry.when is None
        → raise "when is required in workflow.stages.base.assistants.name"
          # the origin-aware check: legal only as an extension (consumed in 1)
      IF name in seen → duplicate guard (programmatic defense)
      FOR pid of produced_ids:
          _reject_attachment_body("workflow.stages.base", name, bodies[pid])
          # messages byte-identical to today
      gate = entry.gate if entry.gate is not None else False   # materialize
      IF source.skills is not None and name not in catalog and not warned:
          warn once: inline declaration skills have no engine channel
      assembled.append(FlowAssistant(profile="goga-"+name, title=name,
          instruction=source.prompt or "", mode=_GATE_MODE[gate],
          trigger=_attachment_trigger(gate, entry.when)))
   3. IF assembled: for pid of produced_ids → assistants_by_id[pid] = assembled
E. Team emission — catalog members in authored order (existing
   _team_members), then one member per attached_pipeline record in collection
   order (pipeline body stage order; authored order within a stage):
   FlowTeamMember(id=title=name, profile="goga-"+name,
                  instruction=eff_prompt or "", skills=eff_skills or [])
   # vetoed and stage-skipped records never collected; a name joins exactly
   # once (the namespace uniqueness guarantees it)
F. Block — FlowCollaboration(mode="assistants",
   max_depth=workflow.delegation.depth or None)  (every compilation)
```

**Errors**: the collision error `duplicate assistant name: <name> (<site1>,
<site2>)`; skip-target; unknown-reference (existing text); when-required
(existing text, new location); script/planning rejections (parameterized
site, D2); the duplicate-in-one-stage defense (existing text); the content
check (existing text).

**Edge Cases**:
- Workflow-less compile: `workflow=None` → empty ns, empty wf_entries, no
  content check; steps' declarations still assemble (SC1).
- A vetoed declaration produces no attachment, no team member, no profile —
  the stage still runs (SC2).
- Loop-expanded copies share one assembled list; the team counts each base
  once (first occurrence) (SC3).
- Extend-embedded steps carry `assistants=None`; a raw `assistants` key in an
  extend body still dies in `_reject_authoring_output_keys` (defensive
  re-check, unchanged message).
- `gate: false` authored on an extension downgrades a gated declaration
  (absence inherits) — the model's `None` vs `False` distinction carries the
  semantics.
- `join_prompt` joins by PRESENCE, not truthiness: an authored empty
  pipeline `prompt: ""` participates in the join (the plain two-segment
  text results, leading blank line included); empty texts are NOT dropped
  here — unlike the overlay's prompt merge — so `None` stays the only
  non-joining side.

### `write_afm_config` — delivery resolution

**Responsibility**: materialize the engine's collaboration plumbing from the
three artifacts.

**Algorithm**:

```
1. wrapper = resolve_wrapper_path(agent) if agent is not None else None
2. base content: client (when wrapper), five static fields, observer hook
3. IF flow is not None and (workflow is not None or pipeline is not None):
      collaboration = _collaboration_section(agent, flow, workflow, pipeline)
   ELSE: the bare static head; profile_command_names = {}
4. _resolve_profiles:
   ns = workflow namespace (catalog + inline declarations; delivery sources)
   pd = {name → declaring stage} built from pipeline.body.steps
        (each step's assistants field keys; the step name is the site)
   FOR name of _referenced_names(flow):
     IF name in ns: (declaration, site) = ns[name]
     ELIF name in pd:
         stage = pd[name]
         ext = workflow.stages[stage].assistants.get(name) if workflow else None
         delivery = (ext.agent, ext.delegate, ext.env)  # Nones when absent
         site = "pipeline." + stage
     ELSE: raise (defensive) "unknown assistant reference in the compiled
           flow: name"
     validate the env keys of a non-empty effective env map (existing error)
     target_agent = delivery.agent else agent
     IF target_agent is None
       → raise "assistant name at site resolved no agent: set its agent or a
         global agent"
     delegate = delivery.delegate if not None else False
5. profiles["goga-"+name] = {title, command, delegate}; env → owner-only sh
   closure path as the command; command_names labels
6. limits.max_tasks only when workflow carries a delegation block
7. write the whole file; return the fixed path
```

**Errors**: illegal env key (existing text); no-agent resolution (existing
text, site parameterized with `pipeline.<stage>` — D2); the defensive
unknown-reference.

**Edge Cases**: `workflow=None` + pipeline declarations → every
pipeline-declared profile resolves through the global agent (SC1); `pipeline`
given but a name pipeline-declared on a stage the flow no longer carries
(skipped) — the name is not flow-referenced, never resolved; an explicitly
cleared env (`{}`) is no env (no closure).

### `run_pipeline` step 17

**Responsibility**: thread the parsed pipeline document into the
configuration write.

**Algorithm**: replace the call with
`write_afm_config(effective_agent, flow_doc, overlay.workflow, pipeline_doc)`
— `pipeline_doc` is the `compile_flow` return already in scope at step 13.
No other step changes.

### `merge_workflow_overlay` (hooks)

**Responsibility**: unchanged merge; the contract now documents the
form-blind append.

**Algorithm**: unchanged. Update the module/`_merge_stage_assistants`/
`_is_assistant_declaration` docstrings to state: a skip entry and a
gate/when-only entry append like every other entry (never dropped by the
namespace rule); an entry shaped as a declaration (any key beyond
gate/when/skip — i.e. any of the five declaration fields present) whose name
is in the merged workflow-side namespace is dropped; the overlay never
resolves a name beyond the workflow document.

**Errors**: none new.

**Edge Cases**: a tool-contributed extension entry addressing a
pipeline-declared name appends (the pipeline namespace is invisible here);
its collision with a workflow declaration of the same name surfaces at
compilation.

---

## Cross-cutting Concerns

- **Error handling**: two existing channels, unchanged — `WorkflowSyntaxError`
  (parse-time, workflow) and `StructuralError` (parse/compile-time, compiler)
  both subclass `ValueError` and surface as clean pre-run errors; delivery
  failures raise `ValueError` before any file is written. The `when`-required
  error moves from parse to compile **keeping its exact text** (constraint:
  wording within existing message conventions). All new texts follow D2.
- **Logging**: one WARNING site — the inline-declaration skills warning
  (once per name, `extra={"stage", "assistant"}`), unchanged wording and
  trigger, now explicitly excluding pipeline declarations (they have a team
  channel). The `compile_flow` info line and the `write_afm_config` profiles
  info line are unchanged.
- **Validation**: parse-time = vocabulary and types (both parsers);
  compile-time = cross-document semantics (namespace uniqueness, origin-aware
  `when`, skip targets, body prohibitions, content of workflow declarations);
  delivery-time = agent/env resolvability (strict, pre-run). Nothing else
  validates — the engine strict-parses its own inputs.
- **Caching**: none (single-pass compilation and per-launch configuration
  rewrite, unchanged).
- **Concurrency**: no thread-safety requirements (pure dataclasses, no shared
  mutable state beyond the established deep-copy discipline: working-body
  copies never alias `PipelineDocument`).

---

## Usages Analysis

### `convention` (`.goga/usages/conventions.md`)

- **What it provides**: code style, docstring format, test organization,
  REPL development cycle.
- **Where used**: every touched module and test file.
- **Why chosen**: the project-wide Python practice (contract-mandated).
- **How exactly**: `@dataclass(kw_only=True)` models, module docstrings,
  pytest suites mirroring the source tree, ruff-clean code.

### `beautiful_yaml` (`.goga/usages/cooks/beautiful_yaml.md`)

- **What it provides**: PyYAML serialization parameters for the written
  artifacts.
- **Where used**: `serialize_flow`, `write_afm_config` (both unchanged in
  their serialization calls — new emission rides the existing structures).
- **Why chosen**: byte-exactness of the compiled flow and the engine config.
- **How exactly**: the existing dump calls; no new serialization sites.

### `afm` (`.goga/usages/cooks/afm.md`)

- **What it provides**: the engine contract — profile shape, stage
  attachment strict-parsing (five keys only), mode/trigger vocabularies,
  limits, config layers.
- **Where used**: `FlowAssistant` (no `skills` key), `_GATE_MODE` /
  `_WHEN_TRIGGER` / `_attachment_trigger`, `write_afm_config` profiles.
- **Why chosen**: the engine is the consumer of everything emitted.
- **How exactly**: unchanged mappings; the extension's effective gate/when
  feed the same mapping; every trigger written explicitly.

### Imported Usages

- `assistants` from `goga/pipeline/workflow` — the authoring vocabulary of
  the workflow surface and the governance forms (skip/extension) the
  compiler resolves. Path:
  `goga/pipeline/workflow/.usages/assistants.md`. Consumed by
  `compile_flow` (origin resolution) and `write_afm_config` (delivery
  expectations).
- `parse-workflow` from `goga/pipeline/workflow` — the parsed model's shape
  and guarantees the compiler relies on (absence-preserving fields, skip
  carriage). Path: `goga/pipeline/workflow/.usages/parse-workflow.md`.
- `collaboration-emission` from `goga/pipeline/compiler` (imported by
  `goga/pipeline`) — the compiled surface the profile ids are read from.
  Path: `goga/pipeline/compiler/.usages/collaboration-emission.md`.
- `compile-flow`, `parse-dsl`, `checkpoints` — consulted for the respective
  surfaces; no new obligations.

---

## `.usages/` Update

### Cell: `goga/pipeline/workflow`

#### Existing Files — Consistency

- **`assistants.md`** → `goga/pipeline/workflow/.usages/assistants.md`
  - Status: current (updated by apply-architecture; verified against this
    design — the governance tables, visibility rule, and error tables match).
  - Additions needed: none.
  - Updates needed: none.
- **`parse-workflow.md`** — current; no changes.

### Cell: `goga/pipeline/compiler`

- **`parse-dsl.md`** (stage-body assistants section), **`collaboration-emission.md`**,
  **`compile-flow.md`** — current; verified against the algorithms above; no
  changes. (The error tables in these files use generic placeholders exactly
  where the contract does not fix texts; the D2 texts do not contradict any
  stated text.)

### Cell: `goga/pipeline/hooks`

- **`checkpoints.md`** — current; no changes.

### Cell: `goga/pipeline`

- **`collaboration-delivery.md`**, **`run-pipeline.md`** — current; the
  delivery ladder and the step-17 threading match this design; no changes.

No new `.usages/` files: every change falls inside existing functional
domains (decision rule: changes within an existing domain supplement the
existing file — already done by apply-architecture).

---

## Test Stack Trace

### General Setup

- pytest with `tmp_path`; pipeline-files written as
  `tmp_path/"pipeline.yml"`, workflows as `tmp_path/"workflow.yml"`, compiled
  via the `_compile` helper pattern of
  `tests/pipeline/compiler/test_compile_flow_collaboration.py`; delivery
  tested through `write_afm_config` with monkeypatched closure/env
  foundations per `tests/pipeline/test_afm_config_collaboration.py`.
- No network, no subprocess. `parse_workflow`/`parse_dsl` tested on plain
  strings.

### Source File Registry

- `goga/pipeline/workflow/workflow_assistant.py`, `parse_workflow.py`
- `goga/pipeline/compiler/pipeline_assistant.py` (new), `parse_dsl.py`,
  `phase_step.py`, `stage_step.py`, `compile_flow.py`
- `goga/pipeline/hooks/overlay.py`
- `goga/pipeline/afm_config.py`, `run_pipeline.py`
- Test files: `tests/pipeline/workflow/test_parse_workflow_assistants.py`,
  `tests/pipeline/workflow/test_workflow_assistant_contract.py`,
  `tests/pipeline/workflow/test_workflow_assistant_logic.py` (the model
  contract tests move to the absence-preserving model: nine fields in the
  fixed order name…skip, `gate`/`when`/`skip` defaulting `None`,
  annotations `bool | None` / `str | None` / `bool | None`),
  `tests/pipeline/compiler/test_parse_dsl.py`,
  `tests/pipeline/compiler/test_data_models.py`,
  `tests/pipeline/compiler/test_compile_flow_collaboration.py`,
  `tests/pipeline/hooks/test_overlay_assistants.py` (or the existing overlay
  assistant test module),
  `tests/pipeline/test_afm_config_collaboration.py`,
  `tests/pipeline/test_run_pipeline_workflow.py`.

---

### Positive Tests

#### `test_stage_body_assistant_parses_into_typed_field`

**Setup**: a STAGES-format pipeline whose `build` stage body carries
`assistants: {auditor: {prompt: "Audit.", skills: [code-audit], when: finish,
gate: true}}`.

**Input**: `parse_dsl(text)`.

**Trace**:
```
parse_dsl(text)
  → _build_body → _extract_stage_step("build", value)
    → _extract_step_assistants("build", value)     # step 4a
      → entry loop: when present, four keys valid, name valid, content ok
      returns: {"auditor": PipelineAssistant(name="auditor", prompt="Audit.",
                skills=["code-audit"], when="finish", gate=True)}
    → _deep_copy_without(value, _STAGE_STEP_KEYS ∪ {"assistants"})
      returns: body without the assistants key
  returns: (header, STAGES, StagesBody(steps=[StageStep(..., assistants={...})]))
→ assert step.assistants["auditor"].when == "finish"
→ assert "assistants" not in step.body
```

**Assertions**: the typed field carries the declaration with every value;
the verbatim body excludes the key; both body formats produce the same
shape.

**Sufficiency**: guards the carriage contract (R1) — declarations must reach
the compiler through the typed field, never the verbatim body.

#### `test_phases_format_stage_assistants_compile_without_workflow` (SC1)

**Setup**: PHASES-format pipeline, two stages; stage `review` carries
`assistants: {watcher: {prompt: "Watch.", skills: [lint], when: checkpoints}}`;
no workflow-file.

**Input**: `compile_flow(pipeline_path, flow_path, workflow=None)`.

**Trace**:
```
compile_flow
  → parse_dsl → steps carrying assistants
  → workflow-less branch: reconstructed = list(body.steps);
    identity_ids = {"discover": ["discover"], "review": ["review"]}
  → _collaboration_emission(None, {}, reconstructed, identity_ids)
    → ns = {}; pipeline_decls = {"review": {watcher}}
    → assembly D.1: no wf entry → attach as declared
      eff_when="checkpoints", eff_gate=False, eff_prompt="Watch."
    → attached_pipeline=[("watcher","Watch.",["lint"])]
  → FlowDocument(collaboration={mode: assistants}, team=[watcher member],
    stages=[…, review with assistants=[entry]])
→ assert flow text contains the stage entry
  {profile: goga-watcher, title: watcher, instruction: "Watch.",
   mode: advisory, trigger: checkpoints}
→ assert team == [{id: watcher, title: watcher, profile: goga-watcher,
  instruction: "Watch.", skills: [lint]}]
```

**Assertions**: the compiled flow carries the attachment with every field
materialized; the team member carries the skills; no workflow was needed.

**Sufficiency**: SC1's compile half — immediate attachment on a workflow-less
run.

#### `test_sc1_profile_generated_without_workflow` (SC1 — delivery)

**Setup**: the compiled flow above; `write_afm_config("claude", flow=doc,
workflow=None, pipeline=pipeline_doc)` with the closure base redirected to
tmp.

**Input**: the four-artifact call.

**Trace**:
```
write_afm_config
  → gating: flow not None and pipeline not None → _collaboration_section
  → _referenced_names → ["watcher"]
  → ns empty; pd = {"watcher": "review"} → pipeline branch
    ext = None (no workflow) → delivery (None, None, None)
    site = "pipeline.review"; target_agent = "claude"
  → profiles["goga-watcher"] = {title: watcher, command: <claude wrapper>,
    delegate: false}
→ assert the written config carries collaboration.profiles.goga-watcher
```

**Assertions**: the profile exists with the global-agent wrapper command;
`limits` absent (no delegation block).

**Sufficiency**: SC1's delivery half — the fixed gating (D1) proven
behaviorally.

#### `test_sc2_skip_veto_removes_attachment_team_and_profile` (SC2)

**Setup**: the same pipeline; a workflow with
`stages: {review: {assistants: {watcher: {skip: true}}}}`.

**Input**: `compile_flow(..., workflow=parse_workflow(wf))`, then
`write_afm_config("claude", flow, workflow, pipeline)`.

**Trace**:
```
parse_workflow → entry skip=True (parse accepts; no when needed)
compile_flow → assembly D.1: entry.skip is True → CONTINUE (veto)
  → no attachment, attached_pipeline empty for the name
→ flow: review carries no assistants key; team empty (no catalog)
write_afm_config → _referenced_names → [] → profiles {}
```

**Assertions**: the stage still compiles and runs (present in stages); no
`assistants` key on it; no team member; no `goga-watcher` profile.

**Sufficiency**: SC2 — the veto removes exactly the assistant, not the stage.

#### `test_sc3_extension_merge_and_ordering` (SC3)

**Setup**: pipeline `build` declares
`sec: {prompt: "Base audit.", skills: [audit, deps], when: finish, gate: true}`;
the workflow catalog declares `reviewer` (prompt/skills) and
`build.assistants` carries `sec: {prompt: "Also the lockfile.", skills:
[deps, lock], when: checkpoints, gate: false, agent: codex}` plus a reference
`reviewer: {when: start}`; a second stage `review` (loop: 2 via the workflow)
declares `noter: {prompt: "Note.", when: message}`.

**Input**: `compile_flow(..., workflow)`.

**Trace**:
```
assembly for build:
  D.1 sec: eff_when=checkpoints, eff_gate=False (explicit downgrade),
     eff_prompt="Base audit.\n\nAlso the lockfile.",
     eff_skills=[audit, deps, lock]   # dedup keeps first occurrence
  D.2 reviewer: reference → ns["reviewer"]; when=start
  build attachments: [sec, reviewer]          # pipeline first
assembly for review-1/review-2: noter uniform on both copies
team: [reviewer (catalog), sec (pipeline), noter (pipeline)]  # catalog first;
  loop copies collapse — noter joins once
```

**Assertions** (exact expected values):
- `instruction == "Base audit.\n\nAlso the lockfile."` (exactly one blank
  line);
- `skills == ["audit", "deps", "lock"]`;
- `mode == "advisory"` (downgraded), `trigger == "checkpoints"`;
- the stage's list orders `sec` before `reviewer`;
- the team list is `[reviewer, sec, noter]`;
- both `review-1`/`review-2` carry the same `noter` entry.

**Sufficiency**: SC3 — the merge rules and both ordering laws in one
executable specification.

#### `test_extension_delivery_fields_reach_the_profile` (SC3 — delivery)

**Setup**: the SC3 flow and workflow; `write_afm_config("claude", flow,
workflow, pipeline)`.

**Trace**: `sec` resolves via `pd` → `ext = build.assistants["sec"]` →
`target_agent = "codex"`, `delegate` from the entry; `reviewer` resolves via
`ns` as today.

**Assertions**: `profiles["goga-sec"].command` is the codex wrapper;
`reviewer`'s profile unchanged from the current behavior.

**Sufficiency**: delivery configuration flows through the extension entry
(R4).

#### `test_sc6_existing_workflow_only_behavior_unchanged` (SC6)

**Setup**: the current suite's catalog/reference/inline scenarios
(`test_compile_flow_collaboration.py` cases: full materialization, reference
field split, inline warning, delegation depth, override-style content check).

**Input**: unchanged fixtures.

**Trace**: the assembly D.2 path is the old `_assistants_by_id` logic with
`entry.gate` materialized `False` and `entry.when` validated present —
identical entries.

**Assertions**: all existing assertions hold unchanged (the WARNING text and
once-per-name behavior included).

**Sufficiency**: non-regression of the workflow-only model (R5/C9).

#### `test_sc5_byte_identical_compile_without_assistants` (SC5)

**Setup**: an assistant-free pipeline + a collaboration-free workflow;
compile before and after the change (golden text from the current suite).

**Assertions**: the serialized flow-file is byte-identical to the recorded
golden output (collaboration mode key excepted as today).

**Sufficiency**: the non-regression guarantee that constrains serialization.

---

### Negative Tests

#### `test_delivery_key_in_stage_declaration_rejected`

**Setup**: a stage body declaring `auditor: {prompt: "X", when: start, agent:
codex}`.

**Input**: `parse_dsl(text)`.

**Trace**: the four-key loop meets `agent` → the unknown-key error with the
delivery-keys clause.

**Assertions**: `StructuralError` matching
`unknown key in stage build.assistants.auditor: agent; valid keys: prompt,
skills, when, gate; agent, env, delegate are workflow-file territory`.

**Sufficiency**: SC4 — the vocabulary boundary is enforced at parse time,
strictly before any run.

#### `test_content_free_stage_declaration_rejected`

**Input**: `auditor: {when: start}` in a stage body.
**Assertions**: `"assistant declaration auditor in stage build resolves
neither prompt nor skills"`.
**Sufficiency**: SC4 — every declaration resolves content (R1).

#### `test_pipeline_declaration_vocabulary_rejections` (parametrized)

**Setup**: a STAGES-format pipeline whose `build` stage body carries one
`auditor` declaration (plus the per-case variants below).

**Input** (cases): `{prompt: "X", when: start, gate: "yes"}`;
`{prompt: "X", when: daily}`; `{prompt: "X", when: start, env: {A: B}}`;
`bad name!: {prompt: "X", when: start}`; `assistant: {prompt: "X", when:
start}`; `auditor: "not a map"`; `assistants:` authored as a list.

**Trace**: `parse_dsl(text)` → step 4a → each case dies in its branch —
the gate type check, the `when` domain check, the unknown-key check with
the delivery-keys clause, the name-grammar check, the reserved-name
check, the entry-mapping check, the top-level mapping check — strictly
before any `PipelineAssistant` is built.

**Assertions**: `StructuralError` with the exact texts:
- `"non-bool value in stage build.assistants.auditor.gate"`
- `"when must be one of: start, checkpoints, finish, message in stage build.assistants.auditor"`
- `"unknown key in stage build.assistants.auditor: env; valid keys: prompt, skills, when, gate; agent, env, delegate are workflow-file territory"`
- `"invalid assistant name in stage build.assistants.bad name!: bad name!"`
- `"assistant name is reserved"`
- `"non-mapping assistant declaration in stage build.assistants.auditor"`
- `"non-mapping assistants in stage build; author the map form keyed by assistant name"`

**Sufficiency**: SC4 — the vocabulary of the new authoring surface is
guarded character-for-character (invalid `when`, invalid/reserved names,
non-bool `gate`, unknown keys, both non-mapping forms).

#### `test_pipeline_declaration_when_missing_rejected`

**Setup**: a STAGES-format pipeline whose `build` stage carries
`auditor: {prompt: "X"}` (no `when`) and, in a second case,
`auditor: {}`.

**Input**: `parse_dsl(text)` per case.

**Trace**: step 4a — the `when` presence check runs before the key loop,
so both the field-less entry and the empty entry die on the same branch.

**Assertions**: `StructuralError("when is required in stage
build.assistants.auditor")` in both cases.

**Sufficiency**: SC4 + the "an empty entry dies as when is required"
edge rule gets an executable confirmation.

#### `test_when_missing_on_workflow_reference_raises_at_compile`

**Setup**: workflow catalog `reviewer` with prompt; stage entry
`reviewer: {gate: true}` (no `when`) — parses cleanly under the new grammar.

**Input**: `compile_flow`.

**Trace**: parse OK (`when=None` carried) → assembly D.2 → `entry.when is
None` → the error.

**Assertions**: `StructuralError("when is required in
workflow.stages.build.assistants.reviewer")` — the exact former parse-time
text, now from the compiler.

**Sufficiency**: SC4 + the moved check (the deliberate ADR cost) — the error
text survives the relocation.

#### `test_skip_targeting_non_pipeline_name_rejected`

**Input**: workflow `build.assistants.reviewer: {skip: true}` where
`reviewer` is a catalog entry.
**Assertions**: `"skip targets a pipeline-declared assistant in
workflow.stages.build.assistants.reviewer"`.
**Sufficiency**: SC4 — the veto governs only what the pipeline ships.

#### `test_cross_stage_pipeline_reference_is_unknown`

**Setup**: pipeline declares `watcher` on `build`; the workflow attaches
`watcher` on `review`.
**Assertions**: `"unknown assistant reference in workflow.stages.review:
watcher"`.
**Sufficiency**: the stage-scoped visibility rule (R4).

#### `test_namespace_collision_names_both_sites`

**Setup**: catalog `auditor` + pipeline `build` declaring `auditor`.
**Input**: `compile_flow`.
**Assertions**: `"duplicate assistant name: auditor (workflow.assistants.auditor,
pipeline.build.assistants.auditor)"`; the inline-vs-catalog and
pipeline-vs-pipeline variants raise the same shape with their site pairs.
**Sufficiency**: the global uniqueness domain (R4/C-constraints).

#### `test_parse_time_skip_grammar_errors`

**Input** (workflow, four cases): `{skip: true, when: start}`;
`{skip: false}`; `{}`; `{skip: "yes"}`.
**Assertions**: the four contract/design texts (combined keys; lone false;
empty entry; non-bool skip).
**Sufficiency**: SC4 — the exactly-one-instruction rule.

#### `test_pipeline_declaration_on_script_stage_rejected`

**Setup**: a pipeline stage carrying `script` and an assistants declaration.

**Input**: `compile_flow(..., workflow=None)`.

**Trace**: assembly D.1 → `_reject_attachment_body("pipeline.build", ...)`
over the working body without a workflow.

**Assertions**: `"assistant is forbidden on a script stage in
pipeline.build: auditor"`; the planning-only variant analogously.
**Sufficiency**: the prohibitions apply to the pipeline surface on every run
(including workflow-less).

#### `test_stage_level_skip_removes_declarations_too`

**Setup**: workflow `stages.build.skip: true` over a pipeline declaring an
assistant on `build`.
**Assertions**: `build` absent from the compiled stages; no team member; no
error.
**Sufficiency**: the stage-skip removes the stage and its declarations
together (R2).

---

### Edge Case Tests

#### `test_empty_stage_assistants_map_equals_absence`

**Input**: `assistants: {}` in a stage body.
**Assertions**: `step.assistants is None`; compile output has no stage
`assistants` key and no team entries.
**Sufficiency**: absence normalization (R1).

#### `test_extension_absence_inheritance_and_explicit_false`

**Setup**: pipeline `gate: true, when: finish`; workflow extensions: (a)
`{prompt: "X"}` — inherits `when: finish`, `gate: true` →
`mode: required, trigger: pre_completion`; (b) `{gate: false}` alone →
`mode: advisory, trigger: on_completion` (gate false, when still finish —
an ungated finish keeps the `on_completion` row; `pre_completion` is
gated-only per `_attachment_trigger`).
**Assertions**: the exact mode/trigger pairs.
**Sufficiency**: absence vs. authored `false` — the model distinction made
observable (C: the extension must preserve field absence).

#### `test_single_sided_prompt_and_skills_stand_alone`

**Setup**: pipeline declaration without prompt (skills only) + extension
with prompt only.
**Assertions**: `instruction == "<extension text>"` (no leading separator);
skills = the declaration's list.
**Sufficiency**: byte-exact join rules.

#### `test_team_loop_collapse_and_authored_empty_skills`

**Setup**: a loop: 2 stage declaring `noter` with `skills: []`.
**Assertions**: one team member; `skills: []` in the member; both copies
attach.
**Sufficiency**: ordering law + explicit-empty-as-value.

#### `test_overlay_appends_skip_and_extension_forms_form_blind`

**Setup**: base workflow stage with an authored entry; a contribution
carrying on the same stage a `{skip: true}` entry (new name) and on another
stage a when-less `{agent: codex}` entry addressing a pipeline name; a
contribution declaration colliding with an authored catalog name.
**Input**: `merge_workflow_overlay`.
**Assertions**: the skip entry and the when-less extension append verbatim;
the colliding declaration drops silently; no error, no resolution.
**Sufficiency**: the overlay contract — pipeline-blind, form-blind (C8).

#### `test_write_afm_config_bare_head_without_artifacts`

**Input**: `write_afm_config("claude")` and `write_afm_config("claude",
flow=doc)` (no workflow, no pipeline).
**Assertions**: the collaboration section carries only `runtime_context` and
`hide_attach_helpers`; no profiles.
**Sufficiency**: the fixed gating's negative half (D1).

#### `test_run_pipeline_threads_pipeline_document`

**Setup**: a run-level test per `test_run_pipeline_workflow.py` conventions
with a pipeline-declared assistant.
**Assertions**: the written engine config carries the `goga-<name>` profile
(the threading through step 17 is exercised end-to-end).
**Sufficiency**: R4's delivery wiring.

---

## Additional Instructions for the Implementation Agent

- Implement in the dependency order of [Entity
  Dependencies](#entity-dependencies); after each cell, run `ruff check
  goga/pipeline/` and the cell's test module before moving on.
- **Error texts are part of the contract**: the D2 message set above is
  normative for this implementation; the pre-existing messages quoted in the
  algorithms must not change by a character (SC5 covers outputs; the
  unchanged wording covers errors).
- Delete `_validate_assistant_namespace` and its call; do not leave the
  parse-time duplicate-name or when-required checks behind as dead code —
  their assertions move to the compiler tests.
- Rework `test_compile_flow_collaboration.py::
  test_authored_assistants_key_in_stage_body_rejected`: after the
  parse-time extraction its current fixture (a list-form `assistants:` in
  a pipeline stage body) dies at parse with `"non-mapping assistants in
  stage build; author the map form keyed by assistant name"` (covered by
  `test_pipeline_declaration_vocabulary_rejections`), and a mapping-form
  `assistants:` in a pipeline stage body is now the valid declaration
  surface. Move the pinned compile-side prohibition test onto an embedded
  extend body (or a programmatic body) — the pinned text `"assistants key
  is forbidden in stage body; use assistants in workflow.stages"` stays
  byte-identical.
- Update `test_workflow_assistant_contract.py` /
  `test_workflow_assistant_logic.py` to the absence-preserving model
  before anything else in the workflow cell — they pin the eight-field
  signature with `gate=False` / `when="checkpoints"` defaults and fail
  on the first model edit.
- `_make_expanded_copy` must deep-copy `assistants` (deep copies of the
  declarations, never aliases); `_embed_extend_stages_*` construct steps
  without assistants (the default).
- Keep `_reject_authoring_output_keys`'s `assistants` branch exactly as is —
  after the parse-time extraction it fires only for embedded extend bodies
  (the defensive re-check the contract keeps).
- Do not touch `serialize_flow`, `FlowAssistant`, `FlowTeamMember`,
  `FlowCollaboration` — the emission rides the existing structures
  unchanged.
- The overlay cell is documentation-plus-tests only; resist any functional
  edit.
- After everything: `goga lint` (0 errors), `goga schema` (unchanged map),
  `ruff check goga/pipeline/`, and `pytest tests/pipeline -q` green; SC5's
  golden-file comparison must pass byte-exactly.
- The parsed pipeline document mirrors the authored source: never mutate
  `PipelineDocument` or its steps during compilation; the extension applies
  output-side only.
