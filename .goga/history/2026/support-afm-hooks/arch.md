# Architecture Plan — afm lifecycle hooks bridge

Support the afm lifecycle-hooks mechanism from the goga side: register goga's
own observer hook with afm on every pipeline run (global layer of the written
`~/.afm/config.yaml`, always on) and bridge afm's per-event invocations onto
the internal hooks platform as 15 new soft actions of the `pipeline` domain —
the 13 `stage_*` transitions under their afm names plus `run_resumed`
(afm `flow_resumed`) and `run_interrupted` (afm `flow_interrupted`), normalized
to goga's vocabulary. Decision record: `task.md`, `prd.md`, `adr.md` in this
directory.

## Topic

**afm lifecycle hooks bridge** — plan file:
`.goga/history/2026/support-afm-hooks/arch.md`

Key decisions (approved in the prototype dialog):

- **Bridge placement (q1=A)** — the afm-facing bridge (stdin payload, `AFM_*`
  env, curated filter, vocabulary mapping, context formation) lives in
  `goga/pipeline` beside the afm configuration authorship; the
  platform-facing vocabulary, contexts, and emission live in
  `goga/pipeline/hooks`; the 15 addresses live in `goga/hooks/catalog`.
- **Context shape (q2=1)** — two contexts (`RunEvent`, `StageEvent`) with
  nested fact records (`RunIdentity`, `StageTransition`).

## Implementation Order

1. **`goga/hooks/catalog`** (modified) — leaf cell, no Imports; the 15 records
   must exist before any bridged emission resolves an address.
2. **`goga/pipeline/hooks`** (modified) — depends on `goga/hooks` (facade) and
   `goga/pipeline/workflow` (both unchanged); provides the four records and
   the two emission methods the bridge imports.
3. **`goga/pipeline`** (modified) — depends on `goga/pipeline/hooks` (existing
   edge, +4 imported types); owns the registration, the bridge module, and the
   CLI dispatch. Implementation module: `goga/pipeline/hook_bridge.py`.
4. **Documentation surface** — `docs/features/pipelines/hooks.md` extended
   after the contracts are fixed (see Documentation deliverable below).

## Artifacts

Marking per the artifact resolution: all three cells are **modified**; no new
cells are created. Each artifact below carries a modification summary and the
complete final content (current state, not a changelog).

---

### Cell 1: `goga/hooks/catalog` [MODIFIED]

**Modification summary (CODEMANIFEST):**
- ADD three `Requirements` bullets to `declared_actions` (the 13 stage-transition
  actions grouped in one bullet; `run_resumed`; `run_interrupted`), placed
  after the run-completion bullet to keep the pipeline-domain records adjacent.
- CHANGE nothing else; header, `Action`, footer byte-preserved.

**CODEMANIFEST** (`goga/hooks/catalog/CODEMANIFEST`) — complete final content:

```yaml
Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  This cell owns the action catalog — the map of subscription addresses of
  the domains, each carrying its error class. The catalog is the single
  source of known addresses: a registration envelope is validated against
  it and an emitted address resolves through it. The catalog is data only —
  no package enumeration, no subscription state, no delivery. A domain
  opening an action extends the catalog additively; published records are
  never rewritten. The error class of a record states how a failing hook of
  the action is treated — soft failures are skipped with a warning, hard
  failures stop the command. Use relative imports.

---

"Action(domain: str, name: str, error_class: str)":
  location: catalog.py
  annotations: |
    One catalog record — a named subscription address with its error class.

    `domain`: the semantic owner of the action — the domain whose
              checkpoint emits the event
    `name`: the action name within its domain
    `error_class`: the failure treatment of the action's hooks — soft or hard

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - `domain` and `name` are non-empty; the pair is unique in the catalog
    - `error_class` is exactly soft or hard
    - The record carries no behavior — the context form and the event
      moment belong to the contract of the owner domain
  properties:
    "domain -> str": |
      The semantic owner domain of the action.
    "name -> str": |
      The action name within its domain.
    "error_class -> str": |
      The failure treatment of the action's hooks — soft or hard.

"declared_actions() -> actions: list[Action]":
  location: catalog.py
  annotations: |
    The declared action catalog — the single source of known addresses.

    `actions`: every declared record, ordered by domain then by name

    Apply the `convention` practice for docstring style and intra-package
    imports.

    Algorithm:
    1. Return the catalog records ordered by domain, then by name

    Requirements:
    - Deterministic — the same records in the same order on every call
    - Complete — no filtering and no partial views
    - The catalog carries the statuses action — the record
      domain="statuses", name="register_statuses", error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the onboarding session-declaration action — the
      record domain="onboarding", name="declare_session", error_class="soft":
      a failing hook of the action is skipped with a warning and the sequence
      continues
    - The catalog carries the onboarding config-amendment action — the
      record domain="onboarding", name="amend_config", error_class="soft": a
      failing hook of the action is skipped with a warning and the sequence
      continues
    - The catalog carries the topics creation-notification action — the
      record domain="topics", name="topic_created", error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the topics publication-notification action — the
      record domain="topics", name="topic_published", error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the topics switch-notification action — the
      record domain="topics", name="topic_switched", error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the topics todo-entry-notification action — the
      record domain="topics", name="topic_todo_entered", error_class="soft":
      a failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the topics deletion-notification action — the
      record domain="topics", name="topic_deleted", error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the topics creation-amendment action — the record
      domain="topics", name="amend_creation", error_class="soft": a failing
      hook of the action is skipped with a warning and the command continues
    - The catalog carries the topics todo-entry-amendment action — the
      record domain="topics", name="amend_todo_entry", error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the pipeline workflow-amendment action — the
      record domain="pipeline", name="amend_workflow", error_class="hard":
      the first failing hook of the action stops the command with a clean
      error naming the tool
    - The catalog carries the pipeline run-creation notification action —
      the record domain="pipeline", name="run_created", error_class="soft":
      a failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the pipeline run-completion notification action —
      the record domain="pipeline", name="run_completed", error_class="soft":
      a failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the thirteen pipeline stage-transition
      notification actions — records domain="pipeline", names
      stage_planning_started, stage_plan_ready, stage_approved,
      stage_revision_started, stage_execution_started,
      stage_question_asked, stage_question_answered,
      stage_retry_scheduled, stage_retry_started, stage_paused,
      stage_resumed, stage_finished, stage_failed, error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the pipeline run-resumed notification action —
      the record domain="pipeline", name="run_resumed", error_class="soft":
      a failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the pipeline run-interrupted notification action
      — the record domain="pipeline", name="run_interrupted",
      error_class="soft": a failing hook of the action is skipped with a
      warning and the command continues
    - The catalog carries the build validation-gate action — the record
      domain="build", name="validate_build", error_class="hard": a veto
      stops the build before any pass with one merged error; the domain's
      delivery walk runs every subscribed tool's hooks to completion — a
      deliberate domain-local deviation from the stop-at-first-failure hard
      semantics
    - The catalog carries the build start-notification action — the record
      domain="build", name="build_started", error_class="soft": a failing
      hook of the action is skipped with a warning and the run continues
    - The catalog carries the build pass-start notification action — the
      record domain="build", name="pass_started", error_class="soft": a
      failing hook of the action is skipped with a warning and the pass
      launches
    - The catalog carries the build pass-completion notification action —
      the record domain="build", name="pass_completed", error_class="soft":
      a failing hook of the action is skipped with a warning; the completion
      fact is already delivered
    - The catalog carries the build completion notification action — the
      record domain="build", name="build_completed", error_class="soft": a
      failing hook of the action is skipped with a warning; the run's exit
      code is unaffected
    - The catalog carries the config amendment action — the record
      domain="config", name="amend_config", error_class="hard": the first
      failing tool of the action stops the command with a clean error
      naming the tool and the action; a structurally malformed
      contribution of the delivery is treated identically
    - The catalog carries the schema cell-amendment action — the record
      domain="schema", name="amend_cell", error_class="hard": the first
      failing hook of the action — a crashed hook or a structurally
      malformed contribution — stops the command with a clean error
      naming the tool, the action, and the failing cell path
    - The catalog carries the schema validation-gate action — the
      record domain="schema", name="validate_schema",
      error_class="hard": a veto or a crashed hook of the action stops
      the schema command; the walk runs every subscribed tool's hooks
      to completion and collects one violation per tool
    - The catalog carries the usages sync-start notification action —
      the record domain="usages", name="sync_started", error_class="soft":
      a failing hook of the action is skipped with a warning and the
      operation continues
    - The catalog carries the usages sync-completion notification action
      — the record domain="usages", name="sync_completed",
      error_class="soft": a failing hook of the action is skipped with a
      warning; the completion facts are already delivered
    - The catalog carries the usages status-start notification action —
      the record domain="usages", name="status_started", error_class="soft":
      a failing hook of the action is skipped with a warning and the
      operation continues
    - The catalog carries the usages status-completion notification action
      — the record domain="usages", name="status_completed",
      error_class="soft": a failing hook of the action is skipped with a
      warning; the completion facts are already delivered
    - The catalog carries the topics update-notification action — the
      record domain="topics", name="topic_updated", error_class="soft": a
      failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the topics propagate-notification action — the
      record domain="topics", name="topic_propagated", error_class="soft":
      a failing hook of the action is skipped with a warning and the
      command continues
    - The catalog carries the contract amendment action — the record
      domain="contract", name="amend_contract", error_class="hard": the
      first failing hook of the action — a crashed hook, a structurally
      malformed contribution, or a contribution addressed to a type the
      cell does not declare — stops the command with a clean error naming
      the tool, the action, and the failing cell path, and the offending
      type name for a bad address
    - The catalog carries the codegraph node-amendment action — the record
      domain="codegraph", name="amend_node", error_class="hard": the first
      failing hook of the action — a crashed hook or a structurally
      malformed contribution — stops the command with a clean error naming
      the tool, the action, and the failing node cell path
    - The catalog carries the codegraph validation-gate action — the
      record domain="codegraph", name="validate_graph",
      error_class="hard": a veto or a crashed hook of the action stops the
      codegraph command; the walk runs every subscribed tool's hooks to
      completion and collects one violation per tool
    - The catalog carries the drift run-start notification action — the
      record domain="drift", name="run_started", error_class="soft": a
      failing hook of the action is skipped with a warning and the run
      continues
    - The catalog carries the drift run-completion notification action —
      the record domain="drift", name="run_completed", error_class="soft":
      a failing hook of the action is skipped with a warning; the
      completion facts are already delivered
    - The catalog carries the drift report-amendment action — the record
      domain="drift", name="amend_report", error_class="hard": the first
      failing hook of the action — a crashed hook or a malformed
      adjustment (an entry not of the closed kind/cell/types shape) —
      stops the command with a clean error naming the hook, the tool, the
      action, and the reason
    - The catalog carries the drift entry-facts amendment action — the
      record domain="drift", name="amend_entry", error_class="hard": the
      first failing hook of the action — a crashed hook or a structurally
      malformed contribution — stops the command with a clean error naming
      the tool, the action, and the failing entry

    Constraints:
    - Do not derive records from installed packages or imports — the
      catalog is maintained data, not discovery

---

Author: Goga
CreatedAt: 31/08/26
Description: |
  Owner of the action catalog — the subscription addresses of the domains
  with their error classes.
```

**.usages/ files:** none (the cell ships no practices; consumers are served
by `goga/hooks/.usages/declaring-actions.md` and the pipeline docs).

---

### Cell 2: `goga/pipeline/hooks` [MODIFIED]

**Modification summary (CODEMANIFEST):**
- ADD four types after `RunCompleted`: `RunIdentity`, `StageTransition`,
  `RunEvent`, `StageEvent` (all `location: contexts.py`).
- ADD two methods to `PipelineHooks`: `emit_run_event`, `emit_stage_event`;
  CHANGE its type annotation (ownership sentence + per-event-process
  requirement bullet).
- CHANGE the global `Annotations` (bridged-vocabulary ownership paragraph).
- CHANGE the footer `Description` (current state).
- Header `Imports` and `Usages` byte-preserved.

**CODEMANIFEST** (`goga/pipeline/hooks/CODEMANIFEST`) — complete final content:

```yaml
Imports:
  - Types:
      - HookRegistry
      - wrap_context
      - build_hook_arguments
      - emit_hook_event
      - declared_actions
    Usages:
      - declaring-actions
      - per-tool-delivery
      - registering-hooks
    From: goga/hooks
  - Types:
      - WorkflowDocument
    From: goga/pipeline/workflow

Usages:
  convention: .goga/usages/conventions.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and
    testing in the project

  This cell owns the hooks zone of the pipeline domain: the fact
  vocabulary of the run events, the read-and-contribute amendment
  context with its per-tool staged commit, the authored-wins workflow
  overlay, and the checkpoint surface that delivers the amendment and
  emits the two run notifications over the platform facade. The zone
  additionally carries the bridged mid-run events: the passthrough run
  and stage contexts of the run interior and their soft emission over
  the same facade — a short-lived process composes the contexts, one
  event per process, and the surface emits them; the curated filtering
  and the vocabulary mapping stay with the caller. One registry per run
  carries every checkpoint of a command — and one registry per event
  process serves a bridged emission; the checkpoints never multiply the
  package enumeration. Every context is built from the operation data
  the caller passes — no repository reads happen here. The amendment
  action is hard: the first failing tool stops the command with a clean
  error naming the tool and the action, and the tool's whole
  contribution is discarded. The notifications are soft — a failing
  hook warns naming the tool, the action, and the reason, and the
  command's exit code is unaffected. Tools are mutually blind — every
  amendment view reads the original authored workflow, never a staged
  state.
  Use the `per-tool-delivery` practice for the staged delivery loop of
  the amendment checkpoint — its loop skeleton, primitives, and
  tool-grouped commit apply as written.
  Use the `declaring-actions` practice for the emission contract of
  the notification checkpoints.
  Use the `registering-hooks` practice for the hook signature and the
  failure handling behind every checkpoint.
  Use relative imports.

---

"PipelineIdentity(name: str, display_name: str = \"\", description: str, source: str)":
  location: identity.py
  annotations: |
    The identity vocabulary of every pipeline event — the discovered
    name, the authored header facts, and the source of the
    pipeline-file.

    `name`: the discovered pipeline name — the file stem without the
             .yml extension
    `display_name`: the authored pipeline name from the DSL header; may
                     differ from the discovered stem; empty when the
                     header names none
    `description`: the pipeline description from the DSL header
    `source`: the origin of the pipeline-file — exactly project or user

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - `name` is non-empty and carries no path separators and no .yml
      suffix
    - `source` is exactly project or user
    - Pure facts — the constructing operation passes resolved values;
      nothing is read here
  properties:
    "name -> str": |
      The discovered pipeline name — the file stem without the .yml
      extension.
    "display_name -> str": |
      The authored pipeline name from the DSL header; may differ from
      the discovered stem.
    "description -> str": |
      The pipeline description from the DSL header.
    "source -> str": |
      The origin of the pipeline-file — project or user.

"WorkflowDecision(kind: str, workflow_name: str | None)":
  location: identity.py
  annotations: |
    The workflow decision of one composition — the outcome of the
    resolution and the resolved name.

    `kind`: exactly one of disabled, explicit, auto-match, silent-miss
    `workflow_name`: the resolved workflow name — present for explicit
                      and auto-match, None otherwise

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - `kind` is exactly one of the four fixed values
    - Pure facts — the decision mirrors the resolution the operation
      already made
  properties:
    "kind -> str": |
      The outcome of the workflow resolution — disabled, explicit,
      auto-match, or silent-miss.
    "workflow_name -> str | None": |
      The resolved workflow name, or None when no name resolved.

"WorkIdentity(branch: str, slug: str | None = None, year: str | None = None)":
  location: identity.py
  annotations: |
    The topics-shaped identity of the current work — the branch, with
    the topic slug and year when the branch hosts a topic.

    `branch`: the current branch name as resolved by the operation
    `slug`: the normalized topic slug — present when the branch hosts a
             topic
    `year`: the resolved year as four digits — present when the branch
             hosts a topic

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - The hosting decision and every resolution happen in the
      constructing operation — nothing is read here
    - The branch-only form — `slug` and `year` None — serves a branch
      hosting no topic
  properties:
    "branch -> str": |
      The current branch name as resolved by the operation.
    "slug -> str | None": |
      The normalized topic slug, or None in the branch-only form.
    "year -> str | None": |
      The resolved year as four digits, or None in the branch-only form.

"CompositionStage(id: str, title: str)":
  location: contexts.py
  annotations: |
    One row of the final composition — the stage identity and its
    display title, as the card shows them.

    `id`: the stage identifier
    `title`: the stage display title

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "id -> str": |
      The stage identifier.
    "title -> str": |
      The stage display title.

"ToolContribution(tool: str, document: WorkflowDocument)":
  location: overlay.py
  annotations: |
    The committed contribution of one tool — the pairing of the tool
    identity with its declarative document.

    `tool`: the tool identity assigned by the platform
    `document`: the committed contribution — a `WorkflowDocument`-shaped
                 set of instructions

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "tool -> str": |
      The tool identity assigned by the platform.
    "document -> WorkflowDocument": |
      The committed contribution of the tool.

"WorkflowOverlay(workflow: WorkflowDocument | None, provenance: list[str])":
  location: overlay.py
  annotations: |
    The result of the amendment layer — the effective workflow and its
    provenance.

    `workflow`: the final effective workflow — None only in the
                 passthrough case: no authored workflow and no committed
                 contribution
    `provenance`: the tools whose contributions committed, in
                   enumeration order

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - A None workflow with a non-empty provenance never occurs — a
      committed contribution always yields a document
  properties:
    "workflow -> WorkflowDocument | None": |
      The final effective workflow, or None in the passthrough case.
    "provenance -> list[str]": |
      The tools whose contributions committed, in enumeration order.

"WorkflowAmendment(pipeline: PipelineIdentity, decision: WorkflowDecision, workflow: WorkflowDocument | None, work: WorkIdentity)":
  location: amendments.py
  annotations: |
    The read-and-contribute view of one tool — the delivered facts of
    the amendment checkpoint and the buffer of one tool's contribution.

    `pipeline`: the identity of the pipeline being composed
    `decision`: the workflow decision of the operation
    `workflow`: the original authored workflow — post decision, post
                 runner-skip merge, pre-layer; read-only and identical
                 for every tool; None when no workflow resolved
    `work`: the current work identity

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `registering-hooks` practice for the hook signature that
    receives this view.

    Requirements:
    - The reads deliver the original facts — no staged-application
      state exists; a tool never sees another tool's contribution
    - The buffered contribution belongs to this tool alone
  properties:
    "pipeline -> PipelineIdentity": |
      The identity of the pipeline being composed.
    "decision -> WorkflowDecision": |
      The workflow decision of the operation.
    "workflow -> WorkflowDocument | None": |
      The original authored workflow, read-only and identical for every
      tool; None when no workflow resolved.
    "work -> WorkIdentity": |
      The current work identity.
  methods:
    "contribute(document: WorkflowDocument)": |
      Buffer one declarative contribution of this tool.

      `document`: the complete contribution — a `WorkflowDocument`-shaped
                  set of instructions (prompt, stages, extend, memory)
                  using the same vocabulary an authored workflow-file
                  uses

      Requirements:
      - The call buffers into the buffer of this tool alone and changes
        nothing until the delivery commits it
      - The replacement is whole — a later call replaces the earlier
        buffered document
      - A document with no prompt, no stages, no extend, and no memory
        is an empty contribution — the delivery discards it with a
        warning

      Constraints:
      - Do not cancel, redirect, or defer the operation — a
        contribution transforms the workflow layer only

"merge_workflow_overlay(base: WorkflowDocument | None, contributions: list[ToolContribution]) -> overlay: WorkflowOverlay":
  location: overlay.py
  annotations: |
    The authored-wins overlay merge — compose the effective workflow
    from the authored base and the committed tool contributions.

    `base`: the authored workflow after the decision and the
             runner-skip merge; None is the empty base — a silent
             auto-match miss keeps the layer active
    `contributions`: the committed contributions in enumeration order
    `overlay`: the effective workflow with its provenance

    Apply the `convention` practice for docstring style and
    intra-package imports.

    Algorithm:
    1. Take `base` as the authored layer — None is the empty base
    2. prompt: place the authored prompt first, then append the prompt
       of every committed contribution in enumeration order; with no
       authored prompt the first tool text becomes the prompt
    3. memory: keep the authored block when present — it is unbeatable;
       otherwise the block of the later contributing tool wins; no
       field-level merging
    4. stages: for each stage name take the authored entry as the
       ground — an authored field is never overwritten; a field the
       author left unset takes the value of the later contributing tool
       that sets it; a stage with no authored entry is fully defined by
       the tools. The per-stage field merge covers the FULL declared
       field set of WorkflowStage, including env: an authored env is
       unbeatable exactly like every other authored stage field; an
       unset env takes the value of the later contributing tool that
       sets it. The merge is field-set-complete, never a named-subset
       copy — a new stage field flows through without touching this
       cell again
    5. skip is an ordinary stage field: an authored skip — from the
       workflow-file or the merged runner skip — is unbeatable; an
       unset skip takes a contributing skip; skip=False overrides
       nothing
    6. extend: keep the authored entries; a contribution entry under an
       authored name is not applied; among contributing tools the later
       entry wins per name
    7. Compose the provenance from the identities of the committed
       contributions in enumeration order
    8. Return the `WorkflowOverlay` — the workflow None only when the
       base is None and no contribution committed; the final document
       assembly carries the profile and build fields of `base`
       verbatim (exactly as memory survives the rebuild) —
       workflow-level instructions never vanish in the overlay

    Requirements:
    - Pure — the inputs stay unmutated; the result is a new document
    - The prompt concatenation joins the non-empty texts with a single
      blank line between consecutive texts — the authored prompt first,
      then each committed contribution text in enumeration order; no other
      separators, prefixes, or suffixes are added
    - Deterministic — the same inputs give the same overlay
    - The result stays declarative — it passes the same compilation
      validation an authored workflow passes
    - The rebuilt `WorkflowDocument` preserves every workflow-level field
      of the base (profile, build verbatim; memory as today) and
      the stage merge is over the complete WorkflowStage field set
      (including env)

    Constraints:
    - Do not read or write the filesystem
    - Do not invent instructions absent from the inputs
    - Do not mutate `base`, the contributions, or their maps

"RunCreated(pipeline: PipelineIdentity, decision: WorkflowDecision, workflow: WorkflowDocument | None, composition: list[CompositionStage], provenance: list[str], work: WorkIdentity, statuses: list[str], runtime_dir: str)":
  location: contexts.py
  annotations: |
    The read-only context of the run-creation notification — the facts
    of the composition at the moment immediately before the runner
    launch.

    `pipeline`: the identity of the running pipeline
    `decision`: the workflow decision of the operation
    `workflow`: the final effective workflow — the authored instructions
                 plus the committed tool contributions
    `composition`: the ordered stages of the final composition — one row
                    per compiled stage, as the card shows
    `provenance`: the tools whose contributions committed, in
                   enumeration order
    `work`: the current work identity
    `statuses`: the maximal present statuses of the work's topic at the
                 moment — both axes, built-in and tool
    `runtime_dir`: the run's runtime directory as a posix string

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of the composed moment — a hook observes and
      cannot alter
  properties:
    "pipeline -> PipelineIdentity": |
      The identity of the running pipeline.
    "decision -> WorkflowDecision": |
      The workflow decision of the operation.
    "workflow -> WorkflowDocument | None": |
      The final effective workflow — authored instructions plus the
      committed tool contributions.
    "composition -> list[CompositionStage]": |
      The ordered stages of the final composition, as the card shows
      them.
    "provenance -> list[str]": |
      The tools whose contributions committed, in enumeration order.
    "work -> WorkIdentity": |
      The current work identity.
    "statuses -> list[str]": |
      The maximal present statuses of the work's topic at the moment.
    "runtime_dir -> str": |
      The run's runtime directory as a posix string.

"RunCompleted(pipeline: PipelineIdentity, decision: WorkflowDecision, workflow: WorkflowDocument | None, composition: list[CompositionStage], provenance: list[str], work: WorkIdentity, statuses: list[str], runtime_dir: str, exit_code: int)":
  location: contexts.py
  annotations: |
    The read-only context of the run-completion notification — the same
    facts recomputed at the completion moment, plus the outcome of the
    launch attempt.

    `pipeline`: the identity of the running pipeline
    `decision`: the workflow decision of the operation
    `workflow`: the final effective workflow the run executed
    `composition`: the ordered stages of the executed composition
    `provenance`: the tools whose contributions committed
    `work`: the current work identity
    `statuses`: the maximal present statuses recomputed at the
                 completion moment
    `runtime_dir`: the run's runtime directory as a posix string
    `exit_code`: the actual exit code of the launch attempt — zero,
                  non-zero, or a spawn failure (126/127)

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts of the completed attempt — completion is a fact,
      not a success claim
  properties:
    "pipeline -> PipelineIdentity": |
      The identity of the running pipeline.
    "decision -> WorkflowDecision": |
      The workflow decision of the operation.
    "workflow -> WorkflowDocument | None": |
      The final effective workflow the run executed.
    "composition -> list[CompositionStage]": |
      The ordered stages of the executed composition.
    "provenance -> list[str]": |
      The tools whose contributions committed, in enumeration order.
    "work -> WorkIdentity": |
      The current work identity.
    "statuses -> list[str]": |
      The maximal present statuses recomputed at the completion moment.
    "runtime_dir -> str": |
      The run's runtime directory as a posix string.
    "exit_code -> int": |
      The actual exit code of the launch attempt.

"RunIdentity(run_id: str, run_dir: str, root_dir: str, resumed: bool)":
  location: contexts.py
  annotations: |
    The run identity carried by every bridged mid-run event — passthrough
    values under goga-idiomatic names; the raw event payload stays out of
    the zone.

    `run_id`: the run identity of the executing run
    `run_dir`: the run's state directory as a posix string
    `root_dir`: the flow's root directory as a posix string
    `resumed`: whether the run resumed earlier state

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Pure passthrough facts — the constructing operation passes
      resolved values; nothing is read here
  properties:
    "run_id -> str": |
      The run identity of the executing run.
    "run_dir -> str": |
      The run's state directory as a posix string.
    "root_dir -> str": |
      The flow's root directory as a posix string.
    "resumed -> bool": |
      Whether the run resumed earlier state.

"StageTransition(id: str, name: str, from_status: str, to_status: str, phase: str)":
  location: contexts.py
  annotations: |
    The stage facts of one bridged stage event — the transition of a
    single stage.

    `id`: the stage identifier
    `name`: the stage name
    `from_status`: the lifecycle status the stage left
    `to_status`: the lifecycle status the stage entered
    `phase`: the stage phase at the event moment

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - `from_status` / `to_status` carry the lifecycle statuses under
      idiomatic names — the raw names are reserved words and cannot serve
      as attribute names
  properties:
    "id -> str": |
      The stage identifier.
    "name -> str": |
      The stage name.
    "from_status -> str": |
      The lifecycle status the stage left.
    "to_status -> str": |
      The lifecycle status the stage entered.
    "phase -> str": |
      The stage phase at the event moment.

"RunEvent(pipeline: str, run: RunIdentity, event_id: str, occurred_at: str, reason: str = \"\")":
  location: contexts.py
  annotations: |
    The read-only context of a run-level bridged event — the facts a tool
    needs to react without knowledge of the event source.

    `pipeline`: the pipeline name of the running flow
    `run`: the run identity of the event
    `event_id`: the stable event identity — the idempotency key of the
                 emission
    `occurred_at`: the event moment as an ISO-8601 UTC string
    `reason`: the free-text cause of the event; empty when the source
               names none

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts — a hook observes and cannot alter
    - No raw payload exposure — only the curated facts under idiomatic
      names
  properties:
    "pipeline -> str": |
      The pipeline name of the running flow.
    "run -> RunIdentity": |
      The run identity of the event.
    "event_id -> str": |
      The stable event identity — the idempotency key of the emission.
    "occurred_at -> str": |
      The event moment as an ISO-8601 UTC string.
    "reason -> str": |
      The free-text cause of the event; empty when the source names none.

"StageEvent(pipeline: str, run: RunIdentity, stage: StageTransition, event_id: str, occurred_at: str, reason: str = \"\")":
  location: contexts.py
  annotations: |
    The read-only context of a stage-level bridged event — the run facts
    plus the transition of one stage.

    `pipeline`: the pipeline name of the running flow
    `run`: the run identity of the event
    `stage`: the stage transition of the event
    `event_id`: the stable event identity — the idempotency key of the
                 emission
    `occurred_at`: the event moment as an ISO-8601 UTC string
    `reason`: the free-text cause of the event; empty when the source
               names none

    Apply the `convention` practice for the data-model rules and
    intra-package imports.

    Requirements:
    - Read-only facts — a hook observes and cannot alter
    - No raw payload exposure — only the curated facts under idiomatic
      names
  properties:
    "pipeline -> str": |
      The pipeline name of the running flow.
    "run -> RunIdentity": |
      The run identity of the event.
    "stage -> StageTransition": |
      The stage transition of the event.
    "event_id -> str": |
      The stable event identity — the idempotency key of the emission.
    "occurred_at -> str": |
      The event moment as an ISO-8601 UTC string.
    "reason -> str": |
      The free-text cause of the event; empty when the source names none.

"PipelineHooks()":
  location: events.py
  annotations: |
    The checkpoint surface of the pipeline domain — the amendment
    delivery, the run notifications, and the bridged mid-run events over
    the platform facade.

    Apply the `convention` practice for the code style and
    intra-package imports.
    Use the `per-tool-delivery` practice for the staged delivery loop of
    the amendment checkpoint.
    Use the `declaring-actions` practice for the emission contract of
    the notification checkpoints.
    Use the `registering-hooks` practice for the registration contract
    behind every checkpoint.

    Requirements:
    - Cheap construction — no enumeration and no imports happen at
      construction
    - One `HookRegistry` per run carries every checkpoint of a command
      — the assembly runs once per run whatever the number of
      checkpoints; a bridged emission builds its registry once per
      event process
    - Every context is built from the values the caller passes — no
      repository reads happen at a checkpoint
  methods:
    "amend_workflow(pipeline: PipelineIdentity, decision: WorkflowDecision, workflow: WorkflowDocument | None, work: WorkIdentity) -> overlay: WorkflowOverlay": |
      Deliver the workflow-amendment checkpoint and return the
      effective workflow with its provenance.

      `pipeline`: the identity of the pipeline being composed
      `decision`: the workflow decision of the operation
      `workflow`: the authored workflow after the decision and the
                   runner-skip merge; None when no workflow resolved
      `work`: the current work identity
      `overlay`: the effective workflow and the contributing tools

      Use the `per-tool-delivery` practice for the delivery loop.

      Algorithm:
      1. Resolve the address domain="pipeline", action="amend_workflow"
         against `declared_actions`
      2. Walk the subscriptions of the address per tool in enumeration
         order: build the tool's `WorkflowAmendment` view over the
         delivered facts — every tool reads the same original
         `workflow` — wrap it via `wrap_context`, project the call
         arguments via `build_hook_arguments` with the tool's own
         context, and call each hook of the tool
      3. A tool whose every hook returned without raising and whose
         buffer carries a non-empty contribution commits as one
         `ToolContribution`
      4. A tool with a raising hook is a hard failure: a clean error
         naming the tool and the action stops the command at the first
         failure; the tool's contribution is discarded
      5. A tool whose buffered document is empty — no prompt, no
         stages, no extend, no memory — is a content no-op: a warning
         naming the tool, the action, and the reason, the contribution
         discarded, the walk continues
      6. Merge the committed contributions onto `workflow` via
         `merge_workflow_overlay` and return the overlay

      Requirements:
      - The commit granularity is the tool — a tool's whole
        contribution commits only after every hook of the tool succeeds
      - An address without subscriptions returns the passthrough
        overlay — the workflow passed in, an empty provenance
      - The merged result passes the same compilation validation an
        authored workflow passes

      Constraints:
      - Do not apply any contribution outside the single merge after
        the walk
      - Do not skip a subscriber of the address
      - Do not read repositories or the filesystem at the checkpoint
    "emit_run_created(pipeline: PipelineIdentity, decision: WorkflowDecision, overlay: WorkflowOverlay, composition: list[CompositionStage], work: WorkIdentity, statuses: list[str], runtime_dir: str)": |
      Emit the run-creation notification — the facts of the composition
      immediately before the runner launch.

      `pipeline`: the identity of the running pipeline
      `decision`: the workflow decision of the operation
      `overlay`: the amendment result — the effective workflow and the
                  provenance
      `composition`: the ordered stages of the final composition
      `work`: the current work identity
      `statuses`: the maximal present statuses at the moment
      `runtime_dir`: the run's runtime directory as a posix string

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `RunCreated` context from the values — the effective
         workflow and the provenance read from `overlay`
      2. Emit the address domain="pipeline", action="run_created" via
         `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - A failing hook is skipped with a warning under the soft error
        class of the action — the launch proceeds
    "emit_run_completed(pipeline: PipelineIdentity, decision: WorkflowDecision, overlay: WorkflowOverlay, composition: list[CompositionStage], work: WorkIdentity, statuses: list[str], runtime_dir: str, exit_code: int)": |
      Emit the run-completion notification — the recomputed facts of
      the finished launch attempt.

      `pipeline`: the identity of the running pipeline
      `decision`: the workflow decision of the operation
      `overlay`: the amendment result of the run
      `composition`: the ordered stages of the executed composition
      `work`: the current work identity
      `statuses`: the maximal present statuses recomputed at the
                   completion moment
      `runtime_dir`: the run's runtime directory as a posix string
      `exit_code`: the actual exit code of the launch attempt

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Build the `RunCompleted` context from the values
      2. Emit the address domain="pipeline", action="run_completed"
         via `emit_hook_event`

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - The emission happens on every launch-attempt return path —
        zero, non-zero, and spawn failures alike
      - A failing hook warns under the soft error class — the exit code
        of the run is never affected
    "emit_run_event(action: str, context: RunEvent)": |
      Emit a run-level bridged event — the soft notification of the run
      interior.

      `action`: the run-level action name within the pipeline domain
      `context`: the read-only facts of the event

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Emit the address domain="pipeline", action=`action` with
         `context` over the platform facade

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - One shared read-only context instance — every subscribed tool
        reads the same facts
      - A failing hook warns under the soft error class — nothing outside
        the emission is affected
    "emit_stage_event(action: str, context: StageEvent)": |
      Emit a stage-level bridged event — the soft notification of a stage
      transition of the run interior.

      `action`: the stage-level action name within the pipeline domain
      `context`: the read-only facts of the event

      Use the `declaring-actions` practice for the emission contract.

      Algorithm:
      1. Emit the address domain="pipeline", action=`action` with
         `context` over the platform facade

      Requirements:
      - Fire-and-forget — nothing is collected and no value returns
      - One shared read-only context instance — every subscribed tool
        reads the same facts
      - A failing hook warns under the soft error class — nothing outside
        the emission is affected

---

Author: Goga
CreatedAt: 18/09/26
Description: |
  Owner of the pipeline domain hooks zone — the run-event facts, the
  workflow amendment with its overlay, the checkpoint surface over the
  hooks platform, and the bridged mid-run events with their passthrough
  contexts. The overlay merge preserves the full workflow model —
  per-stage `env` instructions and the workflow-level `profile` and
  `build` fields.
```

**.usages file** (`goga/pipeline/hooks/.usages/checkpoints.md`) —
complete final content:

**Modification summary:** ADD the section "Emit the bridged run-interior
events" at the end; existing sections byte-preserved.

````markdown
# pipeline — amending workflows and emitting run checkpoints

How the pipeline flows consume the hooks zone of the pipeline domain:
delivering the workflow amendment before compilation and emitting the two
run notifications around the runner launch. For the run coordination and
the card over the pipeline facade.

## The checkpoint surface

One `PipelineHooks` object serves every checkpoint of a command — the
surface shares one registry per run, so a command that reaches several
checkpoints enumerates the tool packages once.

```python
from goga.pipeline.hooks import PipelineHooks

hooks = PipelineHooks()
```

## Resolve the facts in the operation

Every context is built from the values the caller passes — the checkpoint
reads no repository. Resolve the facts before the delivery:

- `PipelineIdentity` — the discovered pipeline name, the authored header
  name and description, and the source (`project` or `user`).
- `WorkflowDecision` — the outcome of the workflow resolution: `disabled`,
  `explicit`, `auto-match`, or `silent-miss`, with the resolved workflow
  name when applicable.
- `WorkIdentity` — the current branch with the topic slug and year when
  the branch hosts a topic; the branch-only form otherwise.

## Amend before compilation

Deliver the amendment after the runner-skip merge and before
`compile_flow`; compile the effective workflow the delivery returns.

```python
overlay = hooks.amend_workflow(
    pipeline=identity,
    decision=decision,
    workflow=merged_workflow,  # None is valid — a silent miss keeps the layer active
    work=work,
)
compile_flow(overlay.workflow, ...)
```

- A tool contributes one declarative `WorkflowDocument`; authored intent
  wins per slot — the prompt appends, the memory block is whole, stage
  fields fill only what the author left unset, extend entries add.
- The amendment action is hard: the first failing tool stops the command
  with a clean error naming the tool and the action; the tool's whole
  contribution is discarded.
- An address without subscriptions returns the passthrough overlay — the
  workflow stays what was passed, the provenance is empty. With no tool
  packages installed every run composes exactly what was passed.

## Emit around the launch

Emit the creation immediately before the runner launch (after compilation
and prompt materialization) and the completion on every launch-attempt
return — zero, non-zero, and spawn failures alike.

```python
hooks.emit_run_created(
    pipeline=identity,
    decision=decision,
    overlay=overlay,
    composition=stages,
    work=work,
    statuses=statuses,
    runtime_dir=runtime_dir,
)
exit_code = run_flow(...)
statuses = resolve_topic_status(topic_dir, scale)  # recompute at the moment
hooks.emit_run_completed(
    pipeline=identity,
    decision=decision,
    overlay=overlay,
    composition=stages,
    work=work,
    statuses=statuses,
    runtime_dir=runtime_dir,
    exit_code=exit_code,
)
```

- Both notifications are fire-and-forget: a failing hook warns naming the
  tool, the action, and the reason; the run's exit code is unaffected.
- `composition` carries the ordered stages as the card shows them; build
  it from the compiled stages of the same compilation the run executes.

## The card form

The card composes through the same amendment with the same precedence and
reports `overlay.provenance` as the contributing tools. No run events fire
in card form.

## Emit the bridged run-interior events

How the bridge command of a run feeds one lifecycle event into the zone —
for the in-container hook entry of the run interior.

The lifecycle mechanism spawns a fresh short-lived process per event: the
event arrives as a JSON object on stdin with the event facts in the process
environment. Each process is its own command — build the surface, emit once,
exit.

```python
from goga.pipeline.hooks import (
    PipelineHooks,
    RunEvent,
    RunIdentity,
    StageEvent,
    StageTransition,
)

hooks = PipelineHooks()

# run-level event
hooks.emit_run_event(
    action="run_resumed",
    context=RunEvent(
        pipeline=pipeline_name,
        run=RunIdentity(run_id=..., run_dir=..., root_dir=..., resumed=...),
        event_id=...,
        occurred_at=...,
    ),
)

# stage-level event
hooks.emit_stage_event(
    action="stage_execution_started",
    context=StageEvent(
        pipeline=pipeline_name,
        run=run_identity,
        stage=StageTransition(
            id=..., name=..., from_status=..., to_status=..., phase=...
        ),
        event_id=...,
        occurred_at=...,
    ),
)
```

- Resolve the event name to the action name before touching the platform —
  an event outside the curated vocabulary emits nothing; the process exits
  0 without building the registry.
- The contexts are pure passthrough facts — carry the payload values under
  the idiomatic names, never the raw payload; `reason` defaults to an empty
  string when the source names none.
- One `PipelineHooks` object per event process — the registry builds once
  per process, at the first emission.
- Both emissions are fire-and-forget: a failing hook warns naming the tool
  and the action; nothing is collected and the exit code never changes.
- Delivery is live best-effort with no replay — an event not delivered
  before a crash is gone; subscribers are documented to tolerate gaps.
````

---

### Cell 3: `goga/pipeline` [MODIFIED]

**Modification summary (CODEMANIFEST):**
- ADD `RunIdentity`, `StageTransition`, `RunEvent`, `StageEvent` to the
  `goga/pipeline/hooks` Imports block (Types).
- CHANGE the inline `argparse` practice (three subcommands incl. `hook`).
- ADD a global-annotations paragraph (the afm-facing bridge ownership)
  after the run-coordination/subprocess paragraph.
- ADD four routines after `apply_stage_env_wrappers` (`run_hook`,
  `map_event_action`, `build_run_event`, `build_stage_event`;
  `location: hook_bridge.py`).
- CHANGE `write_afm_config` annotation (observer-hook entry).
- CHANGE `pipeline_cli` annotation (five operations, three subcommands,
  hook dispatch, hook requirements bullet).
- CHANGE the footer `Description` (current state).
- All other declarations byte-preserved.

**CODEMANIFEST** (`goga/pipeline/CODEMANIFEST`) — complete final content:

```yaml
Imports:
  - Types:
      - compile_flow
      - translate_role
      - parse_dsl
      - StructuralError
      - PipelineRoles
      - FlowStage
    Usages:
      - compile-flow
      - parse-dsl
      - serialize-flow
      - memory-emission
    From: goga/pipeline/compiler
  - Types:
      - run_flow
    Usages:
      - run-flow
    From: goga/afm
  - Types:
      - ensure_in_docker
      - decode_extra_env
      - decode_home_profiles
    Usages:
      - ensure-in-docker
      - extra-env-carriage
      - home-profiles-carriage
    From: goga/docker
  - Types:
      - load_workflow
      - WorkflowDocument
      - WorkflowStage
      - LoadedWorkflow
      - WorkflowSyntaxError
    Usages:
      - parse-workflow
      - memory
      - load-workflow
      - profiles
    From: goga/pipeline/workflow
  - Types:
      - resolve_project_name
      - load_project_config
    Usages:
      - project-configuration
    From: goga/config
  - Types:
      - ConfigHooks
      - ConfigOverlay
    From: goga/config/hooks
  - Types:
      - resolve_wrapper_path
    Usages:
      - resolve-wrapper-path
    From: goga/agents
  - Types:
      - PipelineHooks
      - PipelineIdentity
      - WorkflowDecision
      - WorkIdentity
      - WorkflowOverlay
      - CompositionStage
      - RunIdentity
      - StageTransition
      - RunEvent
      - StageEvent
    Usages:
      - checkpoints
    From: goga/pipeline/hooks
  - Types:
      - resolve_current_branch_name
      - resolve_topic_dir
      - resolve_topic_status
      - assemble_status_scale
    Usages:
      - topic-paths
      - topic-statuses
    From: goga/history

Usages:
  convention: .goga/usages/conventions.md
  afm: .goga/usages/cooks/afm.md
  argparse: |
    Use the standard library argparse module for in-container CLI parsing.
    Three subcommands: list (with an optional --info flag), run (a required
    name, an optional --info flag, the workflow flags -w/--workflow NAME and
    --no-workflow, the profile flag -p/--profile NAME, a repeatable
    -s/--skip NAME — all four available with and without --info, --port
    required only without --info, and an optional --parallel N), and hook
    (no options — the afm-facing machinery entry receiving the event through
    the process environment and stdin).
  cli_entrypoint: |
    The in-container CLI is launched through the package runpy entrypoint
    (python -m goga.pipeline). The package __main__ module MUST stay a thin
    wrapper: it imports `pipeline_cli` from the local cli module and calls
    it with process argv under the standard __main__ guard. The
    `pipeline_cli` implementation itself MUST live in the cli module —
    never in the __main__ module — so that importing the goga.pipeline
    package does not pull __main__ into sys.modules and trigger a runpy
    RuntimeWarning about __main__ being pre-imported. The single piece of
    logic permitted in __main__.py besides the runpy delegation is the
    in-container docker guard (`ensure_in_docker`, per the
    `ensure-in-docker` practice): it is invoked as the very first
    statement of the __main__ guard block, before `pipeline_cli` is called,
    so host-side invocations of python -m goga.pipeline fail loudly before
    any pipeline work. The guard does NOT move into `pipeline_cli` itself
    — `pipeline_cli` stays a pure parse-and-dispatch routine whose
    contract is unchanged by the guard. The guard invocation MUST be
    covered by tests for both branches: the success path (GOGA_DOCKER=1)
    proceeds to `pipeline_cli`, and the refusal path (marker unset or not
    "1") writes to stderr and exits with code 1 before `pipeline_cli` is
    reached.
  default_prompts: |
    The four default agent prompt files ship inside the installed goga
    package at
    goga/assets/afm/prompts/{planning,implementation,review,summary}.md.
    The directory contains exactly four files; the file stem matches the
    canonical afm agent name. Three of them (planning, implementation,
    review) correspond to the overridable DSL roles planner/executor/
    reviewer (the role-field-name → stem mapping is resolved via
    `translate_role`, imported from goga/pipeline/compiler); summary
    is NOT overridable from the DSL — summary.md is always materialized
    from the default. Resolution from the installed package location is an
    implementation detail — the consumer may use any standard mechanism
    (e.g. importlib.resources or Path(__file__) composition) that yields
    the absolute path to the package's goga/assets/afm/prompts/
    directory at runtime. All four files are expected to exist in a
    properly installed image — when a default is missing AND no inline
    override is supplied for the corresponding role, materialization
    fails with a readable error before launch.

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  This cell owns the pipeline workflow surface: discovery of *.yml pipeline
  files across the project and user pipeline directories, the pipeline-file
  entity model, the informational surface (overview and card), run
  coordination, and the in-container CLI entrypoint `pipeline_cli`.
  Subprocess execution is delegated to `run_flow` — afm run is invoked inside
  the container, never directly.

  The run interior arrives through afm-facing machinery of this cell: the
  afm configuration write registers goga's own observer hook on every
  launch, and the hook entry of the in-container CLI bridges the lifecycle
  events onto the platform — one short-lived process per event, the
  curated vocabulary mapped in one place, the emission delivered through
  the pipeline hooks zone. The bridging is observer-only: no bridge
  outcome ever changes the run. Use `afm` for the lifecycle-hooks
  mechanism — the payload, the `AFM_*` environment, the execution model,
  the failure semantics, and the registration stance.

  Build the data models `PipelineEntry`, `PipelineSummary`, `PipelineCard`,
  and `CardStage` with the standard library dataclasses module (kw_only=True
  per `convention`); `PipelineSource` with the standard library enum module
  (str-backed). Use pathlib.Path for directory and path resolution.

  The pipeline directories are <cwd>/.goga/pipelines/ (project-level,
  user-authored) and ~/.goga/pipelines/ (user-level, populated by goga
  connect). On a name conflict, the project source wins. The workflow
  directory is <cwd>/.goga/workflows/ (project-level).

  Workflow resolution is one rule set shared by run coordination and the
  card: an explicit workflow name, forced disabling, and the basename
  auto-match of the pipeline name are resolved by `resolve_workflow`, so the
  card always reflects the workflow a run with the same flags would apply.
  Use `parse-workflow` for the accepted workflow-file structure.

  The CLI skip names arrive as an explicit parameter of run coordination and
  the card: applied in-memory onto the resolved workflow before compilation.
  The CLI performs no stage-name validation — unknown names surface as the
  compiler's structural error.

  The run coordination and the card compose through the pipeline hooks zone:
  the workflow amendment is delivered after the runner-skip merge and before
  compilation, the run notifications fire around the runner launch, and the
  card reports the contributing tools. An explicit workflow disable turns
  the layer off — the raw authored DSL composes and no amendment delivers;
  a silent auto-match miss keeps the layer active onto the empty base. The
  branch, topic, and status facts resolve in the operation before the
  delivery — the checkpoints read nothing. With no tool packages installed
  the overlay is the passthrough — every form behaves exactly as with the
  amendment layer absent.
  Use the `checkpoints` practice for the checkpoint surface of the zone.
  Use the `topic-paths` practice for the topic directory resolution behind
  the work identity and the `topic-statuses` practice for the status facts
  of the run events.

  The run coordination owns the in-container run parameters: the opening
  load-and-amend of the project configuration (the effective configuration
  feeds everything downstream), the afm configuration authorship, and the
  launch environment composition around the afm launch. The config amendment
  delivery of the load moment follows the one-action-two-moments rule — the
  same action, vocabulary, and semantics as the host delivery; each side
  consumes only the fields it owns. Use `project-configuration` for the
  authored load, `afm` for the written
  configuration-file contract, `resolve-wrapper-path` for the agent command
  resolution, and `extra-env-carriage` for the CLI entries carriage of the
  launch layer.

  The listing, overview, and card forms load no configuration and deliver no
  checkpoint — only the run form performs the load-and-amend. Docker-level
  fields of the effective configuration (image, proxy, hosts) are
  applied-but-unconsumed in-container — silently, summary lines only.

  The cell runs inside the goga Docker image when invoked through
  python -m goga.pipeline; the host-side launcher lives in
  goga/commands/pipeline (docker runtime boundary — no Python Imports).

  Use the `argparse` practice for the in-container CLI parsing and the
  `cli_entrypoint` practice for the thin __main__ delegation with the
  in-container docker guard (`ensure-in-docker`).

  Compilation step: run coordination invokes `compile_flow` (see
  `compile-flow`) to transform the discovered pipeline-file into an afm
  flow-file at runtime inside the container; use `parse-dsl` and
  `serialize-flow` for the intermediate stages when a lower-level view is
  required. Use `memory-emission` for the compiled memory surface of the
  flow-file — the top-level memory block and the per-stage memory keys.

  Prompt materialization step: after compilation, run coordination
  materializes the four default agent prompt files (per `default_prompts`)
  into <AFM_DIR>/prompts/ and applies per-role inline overrides.

  Informational surface: the overview lists every discovered pipeline with
  its description from the DSL header; the card reports the name, the
  description, and the post-workflow stage composition produced by the same
  compilation machine a run uses. The card applies the CLI skip names through the same in-memory merge a run
  applies, and workflow-file skip directives arrive through the shared
  compilation machine — both are part of the composition a run with the same
  flags executes. The card writes nothing into the project or
  runtime directories.

  Per-stage environment delivery: the stages.<name>.env instruction is
  delivered by a generated per-stage closure wrapper the afm stage
  command points at (the absolute-executable-path convention; Use `afm`
  for the command-field contract). The wrapper exports the stage env,
  then execs the stage agent's wrapper, else the extend-entry agent's
  wrapper for the stage, else the effective global
  agent's wrapper (resolved the same way for both consumers), else
  fails strictly before the run. Wrappers live in a container-local
  temp directory — never under /workspace; per-stage values layer
  above all global env layers.

  The stage command rewrite runs AFTER compilation as a targeted patch
  of the flow-file `compile_flow` already wrote: the compiler's direct
  serialization for env-free stages is untouched, keeping the flow
  output byte-identical for runs that declare no stage env (wrappers
  are generated and the file is patched only for stages that declare
  env; with none, the file is neither read nor rewritten).

  Activation: the run coordination and the card apply the profile
  through one channel set — the CLI --profile flag value, the
  GOGA_PROFILE value, and the decoded GOGA_HOME_PROFILES bundle; the
  card keeps reflecting what a run with the same flags would apply.
  When a profile resolves, the run coordination exports its name into
  the afm launch layer as GOGA_PROFILE — pipeline stages (and builds
  invoked inside the runtime) inherit the effective profile with no
  additional options. Use `load-workflow` and `profiles` for the
  loading chain and the activation rules.

  Launch feedback: the run coordination prints one stdout line —
  Pipeline running with workflow "<w>" and profile "<p>" — when a
  workflow resolved; without an effective profile the line names the
  workflow only; without a workflow no line prints.

---

"PipelineEntry(name: str, source: PipelineSource)":
  location: pipeline_entry.py
  annotations: |
    Describe a single pipeline-file discovered by `list_pipelines`: its `name`
    and where it comes from (`source`).

    `name`: pipeline name without extension (e.g. "deploy"); the .yml extension
            is implied and never stored here
    `source`: origin of the pipeline — `PipelineSource` enum value

    Build the data model with the standard library dataclasses module (NOT
    pydantic, per project convention; pydantic is treated as tech debt). Use
    @dataclass(kw_only=True) and validate `name` at construction time
    (raising ValueError on invalid input).

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - `name` must not contain path separators ("/", "\\") or the .yml extension
    - `name` must not be empty

  properties:
    "name -> str": |
      Pipeline name without extension.
    "source -> PipelineSource": |
      Origin of the pipeline: `PipelineSource`.PROJECT for project-level
      <cwd>/.goga/pipelines/, `PipelineSource`.USER for user-level ~/.goga/pipelines/.

"PipelineSource()":
  location: pipeline_entry.py
  annotations: |
    str-backed Enum declaring the origin of a pipeline-file.

    Modeled via the standard library enum module; str-mixin so values
    serialize as plain strings (per the `convention` practice).

  properties:
    "PROJECT = \"project\"": |
      Origin = project-level <cwd>/.goga/pipelines/.
    "USER = \"user\"": |
      Origin = user-level ~/.goga/pipelines/.

"PipelineSummary(name: str, source: PipelineSource, description: str, display_name: str = \"\")":
  location: pipeline_summary.py
  annotations: |
    Describe one row of the overview: the discovered pipeline name, its
    origin, its DSL header description, and the authored header name.

    `name`: pipeline name without extension
    `source`: origin of the pipeline — `PipelineSource` value
    `description`: pipeline description taken from the DSL header
    `display_name`: authored pipeline name from the DSL header; may differ
                    from `name`; defaults to an empty string

    Build with the standard library dataclasses module and
    @dataclass(kw_only=True) (per `convention`).

    Requirements:
    - Use @dataclass(kw_only=True)
    - `name` follows the `PipelineEntry` validation rules — non-empty, no
      path separators, no .yml suffix
    - `display_name` defaults to an empty string — constructions without it
      remain valid

  properties:
    "name -> str": |
      Pipeline name without extension.
    "source -> PipelineSource": |
      Origin of the pipeline.
    "description -> str": |
      Description from the DSL header.
    "display_name -> str": |
      Authored pipeline name from the DSL header; may differ from the
      discovered stem.

"PipelineCard(name: str, description: str, stages: list[CardStage], provenance: list[str] = [])":
  location: pipeline_card.py
  annotations: |
    Describe the card of a single pipeline: the authored name and
    description, the ordered stage rows, and the tools whose contributions
    shaped the composition.

    `name`: pipeline name from the DSL header
    `description`: pipeline description from the DSL header
    `stages`: stage rows in execution order — one per compiled stage
    `provenance`: the tools whose contributions committed into the
                  composition, in enumeration order; empty when none
                  contributed

    Build with the standard library dataclasses module and
    @dataclass(kw_only=True) (per `convention`).

    Requirements:
    - Use @dataclass(kw_only=True)
    - `provenance` defaults to an empty list — constructions without it
      remain valid

  properties:
    "name -> str": |
      Pipeline name from the DSL header.
    "description -> str": |
      Pipeline description from the DSL header.
    "stages -> list[CardStage]": |
      Stage rows in execution order; loop-expanded copies appear as
      separate rows.
    "provenance -> list[str]": |
      The tools whose contributions committed into the composition, in
      enumeration order; empty when none contributed.

"CardStage(id: str, title: str)":
  location: pipeline_card.py
  annotations: |
    Describe one stage row of the card.

    `id`: stage identifier
    `title`: stage display title

    Build with the standard library dataclasses module and
    @dataclass(kw_only=True) (per `convention`).

    Requirements:
    - Use @dataclass(kw_only=True)

  properties:
    "id -> str": |
      Stage identifier.
    "title -> str": |
      Stage display title — the display name of the compiled `FlowStage`.

"list_pipelines(project_dir: Path, user_dir: Path) -> entries: list[PipelineEntry]":
  location: list_pipelines.py
  annotations: |
    Discover pipeline files across two source directories and return them as
    `entries`: a list of `PipelineEntry`-s.

    `project_dir`: project-level pipelines directory (typically <cwd>/.goga/pipelines/)
    `user_dir`: user-level pipelines directory (typically ~/.goga/pipelines/)
    `entries`: list of `PipelineEntry`-s, one per unique pipeline name

    Algorithm:
    1. Scan flat *.yml files (non-recursive) in `project_dir`; for each valid
       stem, record a `PipelineEntry` with the name set to the stem and source
       set to `PipelineSource`.PROJECT. Skip stems that fail `PipelineEntry`
       validation (invalid chars, .yml suffix, empty) silently.
    2. Scan flat *.yml files (non-recursive) in `user_dir`; for each valid stem
       not already present from step 1, record a `PipelineEntry` with source
       set to `PipelineSource`.USER.
    3. Return the combined `entries` list.

    Apply the `convention` practice for the filesystem scanning code
    (relative imports, logging, docstring style).

    Requirements:
    - Scan only the top level of each directory — do not descend into subdirectories
    - Drop the .yml extension when forming the entry name
    - A missing source directory is treated as empty (no error)
    - Skip stems that fail `PipelineEntry` validation silently — they are not pipelines

    Constraints:
    - Do not parse or validate the contents of pipeline files — only their names
      matter here
    - When a name exists in both sources, the project source wins (no duplicate
      entries)

"describe_pipelines(project_dir: Path, user_dir: Path) -> summaries: list[PipelineSummary]":
  location: describe_pipelines.py
  annotations: |
    Compose the overview of every discovered pipeline: each entry paired with
    the authored name and description from its DSL header.

    `project_dir`: project-level pipelines directory (absolute)
    `user_dir`: user-level pipelines directory (absolute)
    `summaries`: one `PipelineSummary` per discovered pipeline, in discovery
                 order

    Apply `convention` for filesystem reading, logging, and docstring style.

    Algorithm:
    1. Discover entries via `list_pipelines`
    2. For each entry: compose the pipeline-file path inside its source
       directory, read the file, parse it via `parse_dsl`, and take the header
       name and description
    3. Build a `PipelineSummary` from the entry name, entry source, the
       header description, and the authored header name (the summary
       display_name field)
    4. Return the summaries in discovery order

    Requirements:
    - The description and the authored header name (summary display_name
      field) come from the DSL header; the name is the discovered stem
    - A damaged pipeline file (unreadable or structurally invalid) aborts the
      whole overview with a readable error — no partial list, no silent
      skips, no placeholder markers
    - Read the filesystem only; write nothing

    Constraints:
    - Do not sort or filter the summaries — discovery order is preserved
    - Do not compile pipeline files — the overview reads headers only
    - Do not extend the discovery contract — names and sources come from
      `list_pipelines` unchanged

"resolve_workflow(pipeline_name: str, workflow_name: str | None, no_workflow: bool, cli_profile: str | None = None, env_profile: str | None = None, home_profiles: dict[str, dict[str, Any]] | None = None) -> workflow: LoadedWorkflow | None":
  location: resolve_workflow.py
  annotations: |
    Resolve the optional workflow for a pipeline: the single rule set shared
    by run coordination and the card.

    `pipeline_name`: pipeline name without extension (the basename auto-match
                     key)
    `workflow_name`: optional explicit workflow name (without the .yml
                     extension)
    `no_workflow`: when True, workflow application is disabled
    `cli_profile`: the CLI activation channel value (the --profile flag),
                   or None
    `env_profile`: the environment activation channel value (the
                   GOGA_PROFILE engine variable), or None
    `home_profiles`: the decoded home bundle (decode_home_profiles result),
                     or None (treated as empty)
    `workflow`: the loaded `LoadedWorkflow` — the parsed `WorkflowDocument`
                plus the active profile — or None when no workflow applies

    Apply `load-workflow` for the loading chain and the parse contract.
    Apply `profiles` for the activation rules.
    Apply `convention` for docstring style.

    Algorithm:
    1. When `no_workflow` is True — return None
    2. Compose the workflow-file path under <cwd>/.goga/workflows/: named
       `workflow_name`.yml when provided (an empty string counts as not
       provided), otherwise the pipeline basename `pipeline_name`.yml
    3. Containment guard: when the composed path resolves outside the
       <cwd>/.goga/workflows/ directory (a ".." segment or an absolute
       prefix in the name) — return None (silent miss; workflow files are
       project-only, never resolved into the wider filesystem)
    4. When the composed file exists — load it via the workflow-cell
       loading chain (per `load-workflow`) with
       the activation channels (`cli_profile`, `env_profile`,
       `home_profiles`) and return the resulting `LoadedWorkflow`;
       structural errors propagate with their readable messages
    5. Otherwise — return None (silent miss; an absent workflow-file is not an
       error)

    Requirements:
    - The resolution rules are exactly: disabled → None; explicit name → that
      file (an empty string counts as no name — the basename auto-match
      applies); otherwise basename auto-match; a name escaping the workflows
      directory → None; missing file → None
    - Workflow files are project-only — the directory resolves from the
      current working directory, and a composed path outside it is a silent
      miss, never a traversal into the wider filesystem
    - Consumers read the loaded value's parts: .document (amendment
      machinery, compilation) and .profile (the feedback line)

    Constraints:
    - Do not treat a missing workflow-file as an error — the auto-match is
      opt-in
    - Do not validate workflow contents beyond what the loading chain
      enforces
    - Do not read environment variables — callers own their flag and
      activation sources

"order_stages(stages: list[FlowStage]) -> ordered: list[FlowStage]":
  location: order_stages.py
  annotations: |
    Order flow stages for execution: a topological sort over the depends_on
    references of each `FlowStage`.

    `stages`: flow stages in declaration order
    `ordered`: the same stages ordered for execution

    Apply `convention` for docstring style.

    Algorithm:
    1. Build the ordering graph from the depends_on references of each
       `FlowStage`
    2. Repeatedly emit, among the stages whose references are all already
       emitted, the one earliest in declaration order
    3. Treat a reference naming no stage in the list as satisfied — dangling
       references are the flow executor's concern, not an ordering error
    4. When no remaining stage qualifies (a reference cycle), append the
       remaining stages in declaration order

    Requirements:
    - Deterministic — declaration order is the tie-break at every step and
      the fallback under cycles
    - The result contains every input stage exactly once — none dropped,
      none duplicated
    - Pure — the input list and its stages are not mutated

    Constraints:
    - Do not validate references for dangling ids, cycles, or duplicates
    - Do not rewrite depends_on — ordering only

"describe_pipeline(name: str, project_dir: Path, user_dir: Path, workflow: str | None, no_workflow: bool, profile: str | None = None, skip: list[str] | None = None) -> card: PipelineCard":
  location: describe_pipeline.py
  annotations: |
    Compose the card of a single pipeline: name, description, the
    post-workflow stage composition as it would execute, and the tools
    that contributed to it.

    `name`: pipeline name without extension
    `project_dir`: project-level pipelines directory (absolute)
    `user_dir`: user-level pipelines directory (absolute)
    `workflow`: optional explicit workflow name (without the .yml extension)
    `no_workflow`: when True, workflow application is disabled
    `profile`: the CLI activation channel value (the --profile flag), or
               None; the card applies the profile through the same channels
               a run applies (the same environment reads)
    `skip`: stage names to skip — merged exactly as a run with the same flags
            merges them; None and an empty list both mean no skip
    `card`: `PipelineCard` — the pipeline name and description from the DSL
            header, one `CardStage` per stage in execution order, and the
            provenance of the amendment

    Apply `compile-flow` for the compilation contract and the documents tuple.
    Apply `checkpoints` for the amendment delivery of the pipeline hooks
    zone.
    Apply `topic-paths` for the work identity resolution behind the
    amendment facts.
    Apply `convention` for docstring style and intra-package imports.

    Algorithm:
    1. Discover entries via `list_pipelines` and locate the matching name;
       on no match report the missing pipeline with a readable error
    2. Resolve the workflow via `resolve_workflow` with the pipeline name,
       the workflow flags, and the activation channels (the `profile`
       parameter, the GOGA_PROFILE value, and the decoded home bundle)
    3. Apply the `skip` names via `apply_skip_stages` onto the resolved
       workflow (None/empty — no skip)
    4. Resolve the amendment facts (the `PipelineIdentity` — the authored
       header name and description read via `parse_dsl` from the
       pipeline-file text; the `WorkflowDecision`; and the `WorkIdentity` —
       the current branch via `resolve_current_branch_name`, the literal
       "unknown" when it resolves None; the hosting topic slug and year via
       `resolve_topic_dir` when its directory exists, the branch-only form
       otherwise) and, unless the decision is disabled, deliver the
       amendment via the `PipelineHooks` checkpoint surface with the merged
       workflow — receiving the overlay result; a disabled decision delivers
       nothing and the overlay is the passthrough `WorkflowOverlay` of the
       merged workflow
    5. Compile the pipeline-file via `compile_flow` into a temporary flow-file
       located in a system temporary directory — outside the project
       directory and outside every runtime directory — with the overlay
       workflow, and receive the documents tuple
    6. Order the compiled stages via `order_stages`
    7. Build the card: name and description from the parsed pipeline document
       header; one `CardStage` per ordered stage — id from the `FlowStage`
       id, title from the `FlowStage` name (the display label); the card
       provenance from the overlay
    8. Discard the temporary flow-file and return the card

    Requirements:
    - The stage composition equals the composition a run of the same pipeline
      with the same workflow, profile, and skip flags would execute — the
      same amendment layer with the same precedence and the same compilation
      machine produce both; the composition reflects the per-stage env
      wrappers — an env-declaring stage appears in the card exactly as it
      composes in a run with the same flags
    - The card applies the profile through the same channels a run applies
      — the same environment reads (GOGA_PROFILE, GOGA_HOME_PROFILES) feed
      the resolution; no feedback line prints in card form
    - The card names the contributing tools — the provenance is empty when
      nothing contributed
    - An explicit workflow disable turns the layer off — no delivery
      happens and the raw authored DSL composes
    - A silent auto-match miss keeps the layer active — the delivery runs
      onto the empty base
    - Loop-expanded stage copies appear as separate stages
    - The CLI skip names apply through the same in-memory merge a run applies
      and are reflected in the stage list; workflow-file skip directives
      apply through the shared compilation machine — both compose exactly
      as a run with the same flags
    - The temporary flow-file lives outside the project and runtime
      directories and is removed afterwards
    - The card name and description are the authored DSL header values

    Constraints:
    - Do not launch afm and do not run any stage — the card is read-only
    - Do not emit run events in card form
    - Do not write into the project directory or any runtime directory
    - Do not re-parse the pipeline-file for the card fields — the card's
      name and description come from the documents tuple; the single early
      `parse_dsl` read of step 3 serves the amendment facts only
    - Do not reorder stages beyond `order_stages`

"run_pipeline(name: str, project_dir: Path, user_dir: Path, port: int, workflow: str | None = None, no_workflow: bool = False, profile: str | None = None, skip: list[str] | None = None, parallel: int | None = None) -> exit_code: int":
  location: run_pipeline.py
  annotations: |
    Load and amend the project configuration, resolve a pipeline name to an
    absolute file path via `list_pipelines`, resolve an optional workflow via
    `resolve_workflow` from the CLI-provided decision under the profile
    activation context, merge the CLI skip
    names via `apply_skip_stages`, deliver the workflow amendment through the
    pipeline hooks zone, compile the pipeline-file (extended by the effective
    workflow) into an afm flow-file at runtime via `compile_flow`, apply the
    per-stage env wrappers as a targeted post-compile patch of the written
    flow-file, materialize
    the four agent prompt files (the defaults plus the inline overrides of
    the resolved `PipelineRoles`) into the
    runtime prompts directory, write the afm configuration file via
    `write_afm_config`, emit the run-creation facts, launch afm through
    `run_flow` with the composed launch environment layer, and emit the
    run-completion facts on its return. This is the run coordination routine
    — it performs the configuration load-and-amend, discovery, workflow
    resolution, path resolution, fact resolution, amendment delivery,
    compilation, wrapper application, prompt materialization, and afm
    configuration authorship;
    the actual subprocess execution lives in `run_flow`.

    `name`: pipeline name without extension
    `project_dir`: project-level pipelines directory (same meaning as in `list_pipelines`)
    `user_dir`: user-level pipelines directory (same meaning as in `list_pipelines`)
    `port`: TCP port forwarded to afm run --port via `run_flow`
            (allocated by the host-side caller)
    `workflow`: optional explicit workflow name (without the .yml extension) —
                the CLI decision from the -w flag; None with `no_workflow`
                unset resolves the basename auto-match
    `no_workflow`: when True, workflow application is disabled — the CLI
                   decision from the --no-workflow flag
    `profile`: the CLI activation channel value — the -p/--profile flag
               decision; composes with the GOGA_PROFILE value and the
               workflow default per the shared activation precedence
    `skip`: stage names to skip — the CLI decision from the repeatable -s
            flags; None and an empty list both mean no skip
    `parallel`: optional cap on concurrently executing stages, forwarded to
                `run_flow` as its max_parallel argument. When None (default) —
                afm runs unbounded (run_flow omits --max-parallel). Read from
                the in-container CLI --parallel flag
    `exit_code`: 0 on success, non-zero on error (missing pipeline, missing
                 binary, afm failure, structural DSL error, workflow parse
                 error, materialization error, configuration load or delivery
                 failure). 127 means afm is not on PATH inside the container.

    Apply `convention` for error-handling style and docstring formatting.
    Apply `project-configuration` for the authored configuration load.
    Apply `checkpoints` for the workflow amendment delivery and the two
    emissions of the pipeline hooks zone.
    Apply `parse-workflow` for the workflow-file contract consumed through
    `resolve_workflow`.
    Apply `compile-flow` for the compilation step contract and the documents
    tuple.
    Apply `default_prompts` for resolving the packaged default prompt files.
    Apply `afm` for the written afm configuration-file contract.
    Apply `resolve-wrapper-path` for the agent command resolution inside
    `write_afm_config`.
    Apply `run-flow` for the subprocess launch contract and its environment
    layer parameter.
    Apply `extra-env-carriage` for the CLI entries carriage of the launch
    layer.
    Apply `topic-paths` for the work identity resolution and
    `topic-statuses` for the status facts of the run events.

    Algorithm:
    1. Load the authored project configuration via `load_project_config` —
       a load failure returns with a clean error before any work; no events
       fire
    2. Deliver the config amendment via the `ConfigHooks` checkpoint surface
       with the authored configuration — the first failing tool stops the
       run with a clean error naming the tool and the action (no events
       fire, afm never launches); print the amendment summary lines of the
       `ConfigOverlay` to stderr; every downstream step consumes the
       effective configuration of the `ConfigOverlay`
    3. Discover pipelines via `list_pipelines` and find the entry whose name
       matches
    4. If no match — report that the pipeline is missing and return a
       non-zero exit code
    5. Build the absolute pipeline path from the matching entry's source
       directory and the pipeline name
    6. Resolve the in-container runtime directory from the AFM_DIR
       environment variable; when unset raise a readable "AFM_DIR not set"
       error; resolve the value to an absolute path
    7. Compose the output flow path inside that directory
    8. Resolve the workflow via `resolve_workflow` with the pipeline name and
       the `workflow` / `no_workflow` parameters — the CLI decision arrives
       as explicit arguments, never from the environment — under the
       activation context: decode the home bundle via `decode_home_profiles`
       from the GOGA_HOME_PROFILES engine variable (per
       `home-profiles-carriage`; a damaged bundle is one clean error here —
       no events fire, afm never launches) and read the GOGA_PROFILE value
       once; both feed the resolution together with the `profile` parameter
    9. Print the launch feedback line to stdout when a workflow resolved —
       Pipeline running with workflow "<name>" and profile "<profile>" when
       the loaded workflow carries an effective profile, Pipeline running
       with workflow "<name>" without one; without a workflow no line
       prints
    10. Apply the `skip` names via `apply_skip_stages` onto the resolved
        workflow's document (None/empty — no skip)
    11. Resolve the amendment facts from the operation's own data: the
        `PipelineIdentity` (discovered name; authored header name and
        description read via `parse_dsl` from the pipeline-file text; entry
        source), the `WorkflowDecision` (disabled /
        explicit / auto-match / silent-miss with the resolved name), and the
        `WorkIdentity` (current branch via `resolve_current_branch_name`,
        the literal "unknown" when it resolves None; the hosting topic slug
        and year via `resolve_topic_dir` when its
        directory exists, the branch-only form otherwise)
    12. Unless the decision is disabled, deliver the amendment via the
        `PipelineHooks` checkpoint surface with the authored workflow after
        the skip merge — receiving the overlay result; a disabled decision
        delivers nothing (the layer is off) and the overlay is the
        passthrough `WorkflowOverlay` of the merged workflow
    13. Resolve the in-container project name via `resolve_project_name`
        (None when the git origin remote is unavailable). Compile via
        `compile_flow` with the overlay workflow (the resolved workflow when
        the layer is off), the in-container project root (Path.cwd()) as
        root_dir, and the project name; receive the documents tuple;
        structural errors propagate unchanged
    14. Apply the per-stage env wrappers via `apply_stage_env_wrappers`
        over the compiled stages — the overlay workflow document, the
        effective pipeline agent, and the composed flow path — a
        post-compile command rewrite of exactly the env-declaring stages in
        the flow-file `compile_flow` already wrote; a no-op that touches no
        file when none declare env
    15. Materialize agent prompts atomically (validate-all, then wipe, then
        write): resolve the default prompts directory per `default_prompts`;
        for each overridable role (planner, executor, reviewer) require an
        inline override from the documents tuple or an existing default file
        (stem via `translate_role`); require the summary default; then reset
        <AFM_DIR>/prompts/ and write exactly four files — overrides where
        present, defaults otherwise, summary always from the default
    16. Write the afm configuration file via `write_afm_config` with the
        effective pipeline agent — the whole file at the fixed in-container
        home path, before the launch
    17. Order the compiled stages via `order_stages` and build one
        `CompositionStage` per ordered stage — id from the `FlowStage` id,
        title from the `FlowStage` name
    18. Resolve the work statuses — the maximal present statuses of the
        hosting topic via `assemble_status_scale` and `resolve_topic_status`;
        an empty list in the branch-only form
    19. Compose the afm launch environment layer per `extra-env-carriage`:
        decode the CLI entries payload via `decode_extra_env` from the
        dedicated engine variable; apply the decoded entries above the
        effective pipeline.env task env layer; add
        GOGA_PROFILE=<effective profile name> when a profile resolved — the
        afm subprocess and its stages inherit it, so a build invoked inside
        the pipeline runtime picks the same profile up through its env
        channel with no additional options (the workflow travels via
        GOGA_WORKFLOW of the launch environment; the launcher env-file line
        stays ambient-only); drop the keys of pipeline.env and the CLI
        entries colliding with the engine set — GOGA_PROFILE, GOGA_WORKFLOW,
        GOGA_HOME_PROFILES, GOGA_EXTRA_ENV, AFM_DIR, AFM_DOCKER_FILE_ROOTS,
        HTTP_PROXY, HTTPS_PROXY, NO_PROXY — silently, the inherited launch
        values stand. A damaged payload is one clean
        error here — no events fire, afm never launches
    20. Emit the run-creation facts via the checkpoint surface immediately
        before the launch: the identity, the decision, the overlay, the
        composition, the work identity, the statuses, and the runtime dir as
        a posix string
    21. Launch afm via `run_flow` with the compiled flow-file path, `port`,
        max_parallel=`parallel`, and the composed layer as its env parameter
        — the process environment of the container stays untouched
    22. On every return of `run_flow` — zero, non-zero, and spawn failures
        alike — recompute the work statuses at the completion moment and
        emit the run-completion facts with the actual exit code
    23. Return the exit code returned by `run_flow`

    Requirements:
    - The environment reads are exactly four: AFM_DIR, the CLI entries
      payload engine variable, GOGA_PROFILE, and GOGA_HOME_PROFILES
      (decoded via `decode_home_profiles`; a damaged bundle is one clean
      error before events) — the workflow decision, the profile flag, and
      the skip names arrive as parameters
    - Print the launch feedback line to stdout when a workflow resolved —
      with the profile name when one resolved, without it otherwise;
      without a workflow no line prints
    - After `compile_flow`, the per-stage env wrappers apply as a targeted
      post-compile patch of the written flow-file — only for env-declaring
      stages; an env-free run keeps the flow-file byte-identical (neither
      read nor rewritten)
    - When a profile resolved, the afm launch layer carries
      GOGA_PROFILE=<effective profile name> — the afm subprocess and its
      stages inherit the effective profile; keys of pipeline.env and the
      CLI entries colliding with the engine set (GOGA_PROFILE,
      GOGA_WORKFLOW, GOGA_HOME_PROFILES, GOGA_EXTRA_ENV, AFM_DIR,
      AFM_DOCKER_FILE_ROOTS, HTTP_PROXY, HTTPS_PROXY, NO_PROXY) are dropped
      silently from the layer, the inherited launch values stand
    - Always pass the absolute pipeline path to `compile_flow` — never the
      bare name
    - Always pass the absolute compiled flow path to `run_flow` — never the
      bare name or the DSL path
    - Always forward `port` to `run_flow`; forward `parallel` (None
      propagates — no --max-parallel flag)
    - A configuration load failure and a configuration delivery failure fire
      no events — the return happens before the pipeline checkpoints; afm
      never launches on a delivery failure
    - The amendment summary lines of the config delivery print to stderr
      (nothing when empty)
    - Docker-level fields of the effective configuration (image, proxy,
      hosts) are consumed nowhere in-container — applied-but-unconsumed,
      silently, no warning
    - `no_workflow` takes precedence over `workflow` (the host-side launcher
      rejects the combined use; the precedence is defensive)
    - Workflow resolution and parsing go through `resolve_workflow` — one
      rule set shared with the card
    - The amendment delivery and its precedence are the same rule set the
      card applies — the same flags compose the same overlay in both forms
    - A missing workflow-file is a silent miss, not an error; the layer
      stays active onto the empty base
    - An explicit disable turns the layer off — no delivery happens and the
      raw authored DSL composes
    - Skip merges onto any resolved workflow and applies to a workflow-less
      pipeline; unknown skip names surface as the compiler's structural
      error
    - The branch, topic, and status facts resolve in the operation before
      the delivery — the checkpoints read nothing
    - The "run_created" action fires immediately before the runner launch;
      the "run_completed" action fires on every launch-attempt return path
      — no exit path skips the completion emission
    - A missing pipeline, a structural composition error, and a
      configuration load or delivery failure fire no events — the return
      happens before the checkpoints
    - A damaged CLI entries payload is one clean error before the
      run-creation facts — no events fire, afm never launches
    - The runtime dir fact is the resolved AFM_DIR path as a posix string
    - With no tool packages installed the overlay is the passthrough — the
      compiled workflow, the prompts, and the output behave exactly as with
      the amendment layer absent
    - <AFM_DIR>/prompts/ contains exactly four files after step 13 succeeds;
      validation precedes any wipe or write — atomicity guarantees no
      partial state on disk
    - The afm configuration file is written exactly once per run, before
      the launch, via `write_afm_config`
    - The launch layer applies to the afm subprocess only, through the env
      parameter of `run_flow` — engine-variable keys never enter the layer,
      and the container's process environment is never mutated
    - Inline prompt overrides come exclusively from the documents tuple
      header roles; the override is a full file replacement — no merge, no
      concatenation
    - Default prompt files resolve from the installed package location per
      `default_prompts` — never from AFM_DIR, CWD, or an environment
      variable
    - root_dir resolution is CWD-based (Path.cwd() resolves to /workspace
      inside the goga container); project_name resolves in-container via
      `resolve_project_name`
    - Do not mutate the documents tuple returned by `compile_flow` — read
      the inline prompt overrides as-is

    Constraints:
    - Do not load the configuration outside `load_project_config` followed
      by the checkpoint delivery — one load, one delivery, one effective
      configuration
    - Do not invoke afm directly outside `run_flow`
    - Do not invoke the compiler outside `compile_flow`
    - Do not invoke the workflow loading chain outside `load_workflow`
    - Do not allocate the port — the caller allocates it
    - Do not default `parallel` — None means unbounded
    - Do not accept relative `project_dir` or `user_dir`
    - Do not mask or wrap exceptions from `compile_flow` or the workflow
      chain — structural errors (`StructuralError`,
      `WorkflowSyntaxError`) propagate with their readable messages
    - Do not resolve git or topic facts inside a hook delivery — the
      operation owns the resolution
    - Do not skip the completion emission on any launch-attempt return path
    - Do not write prompts inside the project directory or /workspace —
      always <AFM_DIR>/prompts/
    - Do not write the afm configuration anywhere but the fixed in-container
      home path — never in the project directory, never in the afm state
      directory
    - Do not write inline prompt overrides into the compiled flow-file
    - Do not delete skipped stages or rewrite depends_on — `compile_flow`
      does both
    - Do not write or generate a workflow-file for skip — the merge is
      in-memory only
    - Do not mutate the process environment — composed layers travel only
      through the env parameter of `run_flow`
    - Do not print configuration values — summary lines carry the tool, the
      path, set or forced only

"write_afm_config(agent: str | None) -> config_path: Path":
  location: afm_config.py
  annotations: |
    Write the whole afm configuration file in-container before the afm
    launch: the agent client command resolved from the effective pipeline
    agent, the four static launcher-side fields, and goga's own observer
    hook entry.

    `agent`: the effective pipeline agent — the authored pipeline.agent as
             amended by the config delivery; None when no agent resolves
    `config_path`: the fixed in-container path of the written file

    Apply `convention` for docstring style and intra-package imports.
    Apply `afm` for the configuration-file contract — the field set, the
    fixed home path, the per-stage override relationship, and the
    lifecycle-hooks registration of the observer hook entry.
    Apply `resolve-wrapper-path` when resolving the agent command.

    Algorithm:
    1. Resolve the absolute wrapper path via `resolve_wrapper_path` — only
       when `agent` is not None
    2. Compose the content: the client command carrying the resolved
       absolute wrapper path (never a bare agent name) — written only when
       an agent resolved, omitted otherwise so per-stage workflow agents or
       the binary's own defaults cover the absent global default; the four
       static fields — the dashboard theme, the disabled browser launch,
       the disabled internal proxy provider, and the in-container prompts
       directory; and the observer hook entry — the stable id goga, the
       in-container hook command of this package's CLI, the all-events
       subscription, the inherited environment, and the afm default
       timeout and retries
    3. Write the whole file to the fixed in-container home configuration
       path — the path is independent of the afm state directory variable
    4. Return the written path

    Requirements:
    - The whole file is rewritten on every run — a repeated invocation
      stays safe
    - The four static fields and the hook entry are constants — never
      configurable through the project configuration or the CLI
    - The hook entry declares no secret environment references of its own
    - The content is serialized programmatically — never hand-escaped as a
      string
    - The file lands only at the fixed home configuration path — never in
      the project directory, never in the afm state directory

    Constraints:
    - Do not write a bare agent name as the client command — always the
      resolved absolute wrapper path
    - Do not derive the prompts directory value from an argument or a
      configuration field — the value is fixed
    - Do not derive the hook entry values from arguments or configuration
      fields — the entry is fixed
    - Do not create or manage the prompts directory — the run coordination
      materializes it
    - Do not print any part of the written content

"apply_skip_stages(workflow: WorkflowDocument | None, skip_stages: list[str]) -> workflow: WorkflowDocument | None":
  location: apply_skip_stages.py
  annotations: |
    Pure in-memory merge of CLI skip directives into a workflow document.
    Each name in `skip_stages` is applied as a `WorkflowStage` carrying
    skip=True over the workflow's stages map, so the downstream `compile_flow`
    removes those stages and transparently reconnects their dependents'
    depends_on. This routine does NOT delete stages or rewrite depends_on — it
    only prepares the declarative workflow that the compiler consumes.

    `workflow`: optional `WorkflowDocument` resolved by `run_pipeline` (loaded
                from a workflow-file via `load_workflow`, or None when no
                workflow resolved)
    `skip_stages`: stage names to skip (the repeatable -s/--skip flag names
                   passed by run coordination and the card); an empty list
                   is a no-op
    `workflow`: the resulting `WorkflowDocument` carrying the skip directives,
                or the input unchanged when `skip_stages` is empty (None stays
                None — `compile_flow` then runs with no workflow)

    Algorithm:
    1. When `skip_stages` is empty — return `workflow` unchanged (None stays
       None; no skip applied)
    2. Build a new stages map: start from a copy of the stages map of `workflow`
       when `workflow` is not None, otherwise an empty dict
    3. For each name in `skip_stages` — set stages[name] = a `WorkflowStage`
       carrying skip=True (skip wins over any pre-existing entry for that name;
       the compiler removes the stage before applying overrides)
    4. Return a NEW `WorkflowDocument`: prompt = the prompt of `workflow` when
       `workflow` is not None else None; stages = the new map; extend = a copy
       of the extend map of `workflow` when `workflow` is not None else the
       default empty map; memory = the memory field of `workflow` when
       `workflow` is not None else None; profile = the profile field of
       `workflow` when `workflow` is not None else None; build = the build
       field of `workflow` when `workflow` is not None else None — memory,
       profile, and build carried verbatim. The input
       `workflow` and its maps are NOT mutated

    Requirements:
    - Empty `skip_stages` is a no-op — return the input unchanged
    - Skip always wins — a name present in both the workflow stages and
      `skip_stages` is replaced with a `WorkflowStage` carrying skip=True
    - Do not mutate the input `workflow` or its stages/extend maps — build a
      new `WorkflowDocument` and a new stages map
    - When `workflow` is None and `skip_stages` is non-empty — construct a
      `WorkflowDocument` whose stages map carries only the skip entries (prompt
      None, extend empty, profile None, build None); skip applies to a
      workflow-less pipeline
    - Construct `WorkflowStage` with skip=True and all other fields at their
      defaults — notes stays None (the model field default)
    - The memory configuration, the profile field, and the build block of
      the input workflow survive the rebuild
      verbatim — a rebuild that drops them would silently disable memory
      participation, change activation, or lose build instructions for
      skip-driven runs
    - Stage-name validation is NOT performed here — the compiler's strict check
      raises a structural error on a name absent from the pipeline body; this
      routine stays declarative
    - Apply `convention` for code style and docstring formatting

    Constraints:
    - Do not delete stages or rewrite depends_on here — the compiler does both
    - Do not validate stage names against any pipeline here
    - Do not write, read, or generate any workflow-file — the merge operates
      purely on in-memory Python objects
    - Do not mutate the input `workflow` object or its maps
    - Do not interpret, validate, or rebuild the memory configuration — it is
      carried as an opaque value (per `memory`)

"apply_stage_env_wrappers(stages: list[FlowStage], workflow: WorkflowDocument | None, global_agent: str | None, flow_path: Path) -> stages: list[FlowStage]":
  location: stage_env_wrappers.py
  annotations: |
    Deliver the per-stage env instructions of a compiled flow: generate
    one sh closure wrapper per env-declaring stage, patch the command
    fields of exactly those stages in the ALREADY WRITTEN flow-file,
    and return a new stage list where those stages' command fields
    point at their wrappers. Stages without an env instruction pass
    through as the SAME objects, untouched.

    `stages`: the compiled flow stages
    `workflow`: the effective workflow document (its stages map carries
                the env instructions), or None (no stage is wrapped)
    `global_agent`: the effective global pipeline agent — the fallback
                    exec target; None when no global agent resolved
    `flow_path`: the path of the flow-file written by `compile_flow` —
                 the target of the post-compile command patch
    `stages`: the new stage list — wrapped stages carry command fields
              pointing at their generated wrappers

    Apply `resolve-wrapper-path` when resolving each exec target.

    Algorithm:
    1. Select the stages whose workflow entry carries a non-None env
       (matched by stage name); with none — return the input list
       unchanged WITHOUT reading or writing `flow_path` (the env-free
       invariant). Loop expansion multiplies the match: EVERY compiled
       copy descended from an env-declaring loop stage (its id carries
       the expansion suffix of the workflow stage name) is selected and
       receives its own wrapper carrying the same env values
    2. Per selected stage, resolve the exec target with the compiler's
       agent precedence: the stage agent's wrapper, else the extend-entry
       agent's wrapper of the same workflow stage name (the compiler's
       per-field default — loop-expansion suffix claims resolve through
       their base name), else the global agent's wrapper, else raise one
       strict pre-run error naming the stage
    3. Validate every declared env key as a legal environment variable
       name (POSIX shape) BEFORE writing any file — an illegal key (a
       shell metacharacter, a non-string key) would inject into or break
       the generated export line; raise one strict pre-run error naming
       the stage and the key
    4. Generate one sh closure per selected stage in a container-local
       temp directory (owner-only access, 0o700): export the stage's env
       values, then exec the resolved wrapper path
    5. Patch `flow_path`: rewrite ONLY the command fields of the
       selected stages in the serialized flow-file to the absolute
       wrapper paths — every other byte of the file stays untouched
    6. Return the new list: selected stages carry command = the
       absolute wrapper path; every other stage is the SAME input
       object

    Requirements:
    - The input list and its stage objects are never mutated
    - Wrappers are generated ONLY for env-declaring stages — env-free
      runs keep byte-identical flow output (the flow-file is neither
      read nor rewritten when no stage declares env)
    - The file patch touches only the command fields of the selected
      stages; the rest of the serialized flow-file is byte-identical
    - Per-stage values layer above all global env layers (the wrapper
      exports them last)
    - A declared env key that is not a legal environment variable name
      is a strict pre-run error naming the stage and the key — raised
      before any wrapper file is written

    Constraints:
    - Do not compile, reorder, or restructure stages — this runs after
      compilation
    - Do not write anything under the project directory or /workspace
      — container-local temp only
    - Do not print or log env values

"run_hook() -> exit_code: int":
  location: hook_bridge.py
  annotations: |
    Receive one lifecycle event of a running flow and bridge it onto the
    hooks platform — the entry the afm configuration registers as goga's
    observer hook; one short-lived process per event.

    `exit_code`: 0 on success, on ignored events, and on subscriber soft
                 failures; non-zero only on a bridge-internal failure

    Apply `afm` for the execution model of the hook command — the launch
    shape, the payload on stdin, the `AFM_*` environment, and the failure
    semantics.
    Apply `convention` for docstring style and intra-package imports.

    Algorithm:
    1. Read the event name from the `AFM_HOOK_EVENT` environment value
       and resolve it via `map_event_action`; a non-curated event returns
       0 immediately, before any platform import
    2. Read the payload from stdin and parse it as a JSON object;
       damaged input is a bridge-internal failure — return a non-zero
       exit
    3. Form the context via `build_run_event` for a run-level action or
       `build_stage_event` for a stage-level action
    4. Emit the soft event via `PipelineHooks` with the mapped action
       name and the built context; subscriber soft failures warn inside
       the platform and never change the exit code
    5. Return 0

    Requirements:
    - The command completes far inside the afm default per-hook timeout
    - No cross-event state — every event is a fresh process
    - The curated filter runs before any platform import
    - The context builder follows the mapped action — the two run-level
      names compose via `build_run_event`, the thirteen stage names via
      `build_stage_event`; an unset or empty `AFM_HOOK_EVENT` resolves as
      non-curated and exits 0

    Constraints:
    - Do not read anything besides stdin and the `AFM_*` environment
      values
    - Do not write files and do not mutate the process environment
    - Do not let a subscriber failure change the outcome
    - Do not emit the run boundaries here — they belong to the run
      coordination's checkpoints

"map_event_action(event: str) -> action: str | None":
  location: hook_bridge.py
  annotations: |
    Resolve a lifecycle event name onto the platform action vocabulary —
    the curated filter of the bridge in one place.

    `event`: the lifecycle event name as delivered by the environment
    `action`: the platform action name, or None for an event outside the
               curated vocabulary

    Apply `afm` for the lifecycle event catalog the names come from.
    Apply `convention` for docstring style and intra-package imports.

    Algorithm:
    1. Match `event` against the curated vocabulary — the thirteen stage
       transitions keep their names verbatim; the run-level pair maps
       flow_resumed to run_resumed and flow_interrupted to run_interrupted
    2. Return the matched action name; every other name — the script
       events, the remaining flow boundaries, and unknown names —
       returns None

    Requirements:
    - Pure and deterministic — the same name always resolves the same way
    - Callable before any platform import — no platform modules are
      needed to resolve a name

    Constraints:
    - Do not read the environment or the filesystem — the name arrives
      as `event`

"build_run_event(payload: dict[str, Any]) -> context: RunEvent":
  location: hook_bridge.py
  annotations: |
    Form the run-level context of one bridged event from the parsed
    payload.

    `payload`: the parsed lifecycle event object
    `context`: the read-only facts of the run-level event

    Apply `afm` for the payload shape — the flow block and the event
    facts.
    Apply `convention` for docstring style and intra-package imports.

    Algorithm:
    1. Read the flow block: the name becomes the pipeline name; the run
       identity facts fill `RunIdentity`
    2. Read the event facts: `event_id`, `occurred_at`, and `reason` —
       an absent reason becomes the empty string
    3. Return the composed `RunEvent`

    Requirements:
    - Pure passthrough — values carry under idiomatic names only; the
      raw payload never attaches to the context
    - A payload without the flow block or the event facts raises a clean
      error naming the missing fact

    Constraints:
    - Do not invent or default a missing required fact — the error names
      it

"build_stage_event(payload: dict[str, Any]) -> context: StageEvent":
  location: hook_bridge.py
  annotations: |
    Form the stage-level context of one bridged event from the parsed
    payload.

    `payload`: the parsed lifecycle event object
    `context`: the read-only facts of the stage-level event

    Apply `afm` for the payload shape — the flow and stage blocks.
    Apply `convention` for docstring style and intra-package imports.

    Algorithm:
    1. Read the flow block and the event facts the way `build_run_event`
       does
    2. Read the stage block: the stage facts fill `StageTransition` — the
       stage identifier, the stage name, the transition statuses under
       `from_status` / `to_status`, and the phase
    3. Return the composed `StageEvent`

    Requirements:
    - Pure passthrough — values carry under idiomatic names only
    - A payload without the stage block raises a clean error — a
      stage-level event always carries one

    Constraints:
    - Do not invent or default a missing required fact — the error names
      it

"pipeline_cli(argv: list[str]) -> exit_code: int":
  location: cli.py
  annotations: |
    In-container CLI implementation for python -m goga.pipeline. Parses argv
    via argparse and dispatches to one of five operations: the flat listing
    (`list_pipelines`), the overview (`describe_pipelines`), the card
    (`describe_pipeline`), run coordination (`run_pipeline`), or the
    lifecycle-event bridge (`run_hook`). Invoked through the runpy
    entrypoint in __main__.py — never imported by Python from the host side
    (runtime docker boundary, no Imports).

    `argv`: argument list (typically the process argv minus the program name)
    `exit_code`: 0 on success, 2 on argparse error, non-zero on operation
                 failure

    Apply the `argparse` practice for parser construction.
    Apply the `cli_entrypoint` practice: this routine is defined in the cli
    module; __main__ only delegates to it.
    Apply `convention` for docstring style and intra-package imports.

    Algorithm:
    1. Build the parser with three subcommands:
       - list: an optional --info/-i flag
       - run: a required name positional; an optional --info/-i flag; optional
         --workflow/-w NAME and --no-workflow flags, an optional
         --profile/-p NAME flag, and a repeatable
         --skip/-s NAME flag (all four available with and without --info);
         a --port PORT integer required only when --info is absent; an
         optional --parallel N integer
       - hook: no options — the afm-facing machinery entry; the event
         arrives through the process environment and stdin
    2. Parse argv; on argparse error exit with code 2
    3. Resolve the project pipelines directory (<cwd>/.goga/pipelines/) and
       the user pipelines directory (~/.goga/pipelines/)
    4. Dispatch:
       - list without --info — call `list_pipelines`; print the flat list:
         one bullet line per entry — the marker line "* <name>" (with the
         " (project)" suffix for project source entries); return 0
       - list with --info — call `describe_pipelines`; print the overview: one
         bullet block per pipeline — the marker line "* <name>" (with the
         " (project)" suffix for project source entries) followed by indented
         "name:" and "description:" field lines; return 0
       - run with --info — call `describe_pipeline` with the name, the parsed
         workflow flags, the parsed profile value, and the parsed skip
         names; print the card: "name:" and "description:"
         field lines, a blank line, a "---" separator, a blank line, then one
         bullet block per ordered stage — the marker line "* <id>:" and an
         indented "title:" field line; return 0
       - run without --info — call `run_pipeline` with name, port, the parsed
         workflow flags, the parsed profile value, the parsed skip names,
         and parallel; return its exit
         code
       - hook — call `run_hook` and return its exit code
    5. Render an operation failure as a clean readable message to stderr (no
       traceback) and return a non-zero exit code

    Requirements:
    - The run subcommand accepts --info/-i, --workflow/-w NAME,
      --no-workflow, --profile/-p NAME, the repeatable --skip/-s NAME, and
      --parallel N; the workflow, profile, and skip flags bind in both
      info and run modes
    - --port is an integer option required only when --info is absent; a
      missing --port without --info is an argparse-style error (exit 2);
      --port is ignored in info mode
    - Long and short flag forms behave identically
    - The flat list template: one marker line "* <name>" per pipeline (with
      the " (project)" suffix for project-source entries) and no header line
      (example: "* deploy (project)" / "* rollback")
    - The overview template: the marker line "* <name>" (with the
      " (project)" suffix for project-source entries) followed by "name:"
      and "description:" field lines indented by four spaces; the name field
      carries the authored header name, the description field the header
      description (example: "* deploy (project)" / "    name: Deploy" /
      "    description: Deploy the service")
    - The card template: a "name:" line, a "description:" line, a blank line,
      a "---" separator, a blank line, then per ordered stage the marker line
      "* <id>:" and a "title:" line indented by four spaces; the separator
      block is printed even when the card carries no stages; when the card
      provenance is non-empty, one blank line and one "tools:" field line
      follow the stage blocks — the contributing tools comma-separated in
      provenance order; an empty provenance adds nothing — the output stays
      byte-identical to the provenance-free card
    - An empty discovery is not an error: the flat list prints nothing —
      zero discovered pipelines, zero lines; the overview likewise prints
      nothing; both return 0
    - Card stage bullet blocks follow execution order; loop-expanded copies
      appear as separate blocks
    - Overview and card output stays within terminal width — no horizontal
      scrolling
    - The hook subcommand carries no options and prints nothing on the
      happy path — it is machinery for the registered observer hook, not
      a user surface

    Constraints:
    - Do not allocate a port inside this CLI — run mode receives it from the
      host-side launcher
    - Do not validate workflow flag combinations or skip stage names — the
      host-side launcher owns the flag-combination validation and the
      compiler owns the stage-name error
    - Do not print tracebacks for operation failures — clean stderr messages
    - Do not import this cell from the host side — invoke via docker only

---

Author: Goga
CreatedAt: 19/08/26
Description: |
  Cell that owns the pipeline workflow: discovery of *.yml pipeline files
  across the project and user pipeline directories, the pipeline-file entity
  model, the informational surface (overview and card), run coordination
  with the in-container run parameters — the configuration load-and-amend,
  the afm configuration authorship with the observer-hook registration, and
  the launch environment composition — the per-stage env delivery through
  generated closure wrappers, the lifecycle-event bridge of the run
  interior, and the in-container CLI entrypoint pipeline_cli.
```

**.usages file 1** (`goga/pipeline/.usages/pipeline-cli.md`) — complete
final content.

**Modification summary:** intro names five operations; ADD the `hook`
subsection after `run`; exit-codes section unchanged.

````markdown
# pipeline_cli — in-container CLI for python -m goga.pipeline

`pipeline_cli` parses argv via argparse and dispatches to the flat listing (`list_pipelines`),
the overview (`describe_pipelines`), the card (`describe_pipeline`), run coordination
(`run_pipeline`), or the lifecycle-event bridge (`run_hook`). Invoked by the host-side
docker launcher through the runpy entrypoint in `__main__.py`.

## Subcommands

### list

`list [--info]`

- Without `--info`: prints the flat list — one bullet line per pipeline: `* <name>` (with the
  " (project)" suffix for project source entries); no header line.
- With `--info`/`-i`: prints the overview — one bullet block per pipeline: the marker line
  `* <name>` (with the " (project)" suffix for project source entries) followed by `name:` and
  `description:` field lines indented by four spaces; `name:` carries the authored header name,
  `description:` the header description.
- An empty discovery prints nothing (flat list and overview alike); exit code 0.

### run

`run NAME [--info] [-w WORKFLOW | --no-workflow] [-p PROFILE] [-s NAME]... [--port PORT] [--parallel N]`

- NAME (positional, required) — pipeline name without extension.
- `--info`/`-i` (flag) — print the card instead of running: `name:` and `description:` field
  lines, a blank line, a `---` separator, a blank line, then one bullet block per stage in
  execution order — the marker line `* <id>:` and a `title:` field line indented by four
  spaces. When the card provenance is non-empty, one blank line and one `tools:` field line
  follow the stage blocks — the contributing tools comma-separated in provenance order; an
  empty provenance adds nothing (byte-identical card).
- `-w WORKFLOW` / `--no-workflow` — the workflow decision, available in BOTH modes: a run and a
  card resolve it through the same shared rule set. `--no-workflow` disables application;
  `-w WORKFLOW` names an explicit workflow; neither flag triggers the basename auto-match.
- `-p PROFILE` / `--profile PROFILE` — the contributor-profile activation channel, available
  in BOTH modes: the value composes with the `GOGA_PROFILE` env channel and the workflow's
  `profile:` default (`-p` wins). The workflow-file renders with the active profile; the card
  reflects the same composition a run with the same flag executes.
- `-s NAME` (repeatable) — stage names to skip, available in BOTH modes: a run applies them to
  the execution, a card reflects them in the composition. Forwarding-only — unknown names
  surface as the compiler's structural error during composition.
- `--port PORT` (int) — dashboard port, allocated by the host launcher. Required only when
  `--info` is absent; ignored in info mode.
- `--parallel N` (int, optional) — max concurrently executing stages; run mode only.

Dispatch: run without `--info` → `run_pipeline(NAME, project_dir, user_dir, PORT,
workflow=<WF or None>, no_workflow=<bool>, profile=<P or None>, skip=<names or None>,
parallel=<N or None>)`; run
with `--info` → `describe_pipeline(NAME, project_dir, user_dir, workflow=<WF or None>,
no_workflow=<bool>, profile=<P or None>, skip=<names or None>)`.

### hook

`hook` (no options)

- Machinery entry for the registered afm observer hook — not a user
  surface; spawned once per lifecycle event with the event on stdin and
  the `AFM_*` environment. Non-curated events exit 0 without importing
  the platform.
- Dispatch: `hook` → `run_hook()`; the exit code is its result — 0 on
  success and ignored events, non-zero only on a bridge-internal failure.

## Exit codes

0 success; 2 argparse error (including a missing `--port` without `--info`); non-zero operation
failure, rendered as a clean stderr message without a traceback.
````

**.usages file 2** (`goga/pipeline/.usages/registering-hooks.md`) —
complete final content.

**Modification summary:** intro updated (eighteen actions); ADD the
section "The bridged mid-run events" after "The run notifications"; ADD
the live-progress scenario to Integration scenarios; everything else
byte-preserved.

````markdown
# pipeline — registering hooks

How a `goga_tool_*` package subscribes its hooks to the pipeline domain
actions. For tool package authors; no goga code changes are needed.

The domain opens eighteen actions. One is an amendment — a read-and-contribute
view over the workflow a run is about to execute, delivered before
compilation. Two are notifications —
the read-only facts of the run, delivered immediately before the runner
launch and on every launch-attempt return. Fifteen are the bridged mid-run
events — the stage transitions and the run-level resume/interrupt of the
run interior, delivered live while the run executes.

## The events

| Address | Error class | Fires |
|---|---|---|
| `pipeline / amend_workflow` | hard | After the workflow resolution and the runner-skip merge, before compilation — in the run form and in the card form alike. |
| `pipeline / run_created` | soft | Immediately before the runner launch — after compilation, prompt materialization, and the afm configuration write. |
| `pipeline / run_completed` | soft | On every launch-attempt return — zero, non-zero, and spawn failures (126/127) alike. |

A failing moment fires nothing: a missing pipeline, a structural
composition error, and a configuration load or delivery failure return
before any checkpoint.

## Subscribe

```python
# inside the goga_tool_<tool> package
def register_hooks(hooks):
    hooks.subscribe("pipeline", "amend_workflow", "hardening", add_hardening)
    hooks.subscribe("pipeline", "run_completed", "reporter", report_run)
```

- `domain` — always `"pipeline"`.
- `action` — the event name from the table above.
- `name` — the hook name, unique per tool per address.
- `hook` — the callable executed when the event fires.

A hook receives values only for the parameters it declares by the fixed
offered names: `context` — the delivered object of the event, read
attributes and call methods freely, attribute assignment is blocked;
`self` — the isolated context of your tool. The declaration order does not
matter; names you did not declare receive nothing.

## The amendment view

`amend_workflow` delivers a `WorkflowAmendment` view per tool. The
reads: `pipeline` — the identity of the running pipeline; `decision` —
the workflow decision (disabled / explicit / auto-match / silent-miss,
with the resolved name); `workflow` — the original authored workflow
after the decision and the runner-skip merge, read-only and identical
for every tool (None when no workflow resolved); `work` — the current
work identity.

```python
def add_hardening(context):
    context.contribute(hardening_workflow)
```

- `contribute(document)` buffers one declarative `WorkflowDocument`-shaped
  contribution — the same instruction vocabulary an authored
  workflow-file uses (prompt, stages, extend, memory).
- Your tool's contribution commits only after every hook of your tool
  returns without raising; a repeat call replaces your buffer whole.
- Authored intent wins per slot: the prompt appends (authored first, tool
  texts in enumeration order), the memory block is whole (an authored
  block is unbeatable), stage fields fill only what the author left
  unset, extend entries add under fresh names. `skip` is an ordinary
  field — an authored skip is unbeatable, an unset skip is yours to set,
  including removing a pipeline-file stage the author did not protect.
- A failing hook of the amendment stops the command with a clean error
  naming your tool and the action; your whole contribution is discarded.
- The merged workflow passes the same compilation validation as an
  authored one — a contribution naming an unknown stage surfaces as the
  compiler's structural error.

## The run notifications

Both notifications deliver read-only facts; a failing hook warns naming
your tool, the action, and the reason — the run's exit code is never
affected.

- `run_created` — `RunCreated`: `pipeline`, `decision`, `workflow` (the
  final effective workflow — authored instructions plus the committed
  tool contributions), `composition` (the ordered stages as the card
  shows them), `provenance` (the tools whose contributions committed),
  `work`, `statuses` (the maximal present topic statuses at the moment),
  `runtime_dir`.
- `run_completed` — `RunCompleted`: the same facts recomputed at the
  completion moment, plus `exit_code` — the actual exit code of the
  launch attempt. Completion is a fact, not a success claim.

## The bridged mid-run events

Fifteen soft actions deliver the run interior live, while the stages still
execute — one event per lifecycle transition. Observed: a hook never
changes the run. Best-effort: an event not delivered before a crash is not
replayed — build subscribers tolerant of gaps.

| Class | Actions | Context |
|---|---|---|
| Stage transitions (13) | `stage_planning_started`, `stage_plan_ready`, `stage_approved`, `stage_revision_started`, `stage_execution_started`, `stage_question_asked`, `stage_question_answered`, `stage_retry_scheduled`, `stage_retry_started`, `stage_paused`, `stage_resumed`, `stage_finished`, `stage_failed` | `StageEvent` |
| Run-level (2) | `run_resumed`, `run_interrupted` | `RunEvent` |

- `StageEvent` reads: `pipeline` — the pipeline name; `run` — the run
  identity (`run_id`, `run_dir`, `root_dir`, `resumed`); `stage` — the
  transition (`id`, `name`, `from_status`, `to_status`, `phase`);
  `event_id` — the stable event identity, the idempotency key;
  `occurred_at` — the event moment (ISO-8601 UTC); `reason` — the
  free-text cause, empty when none.
- `RunEvent` reads the same facts without the `stage` block.
- Your hooks run inside a short-lived process per event: `self` state dies
  with the event — persist across events in your own storage. The process
  inherits the run launch environment (env-file layers, the task env
  layer, CLI `-e` entries) — treat it as visible.
- A failing hook warns naming your tool and the action; the event, the
  run, and the other subscribers are unaffected.

```python
def register_hooks(hooks):
    hooks.subscribe("pipeline", "stage_execution_started", "notify", on_start)
    hooks.subscribe("pipeline", "stage_finished", "notify", on_finish)


def on_start(context):
    report(f"{context.pipeline}: {context.stage.name} → executing")
```

## Integration scenarios

- **Artifact → status on completion** — subscribe to `run_completed`,
  read `work` and `exit_code`, register your status on the statuses
  domain keyed by your artifact.
- **Run reporting and automation** — subscribe to `run_created` and
  `run_completed`, read the facts, keep state in your `self` context.
- **Live progress reporting** — subscribe to the stage transitions, read
  `stage` and `run`, report while the run executes; tolerate gaps
  (best-effort delivery).
- **Workflow personalization** — subscribe to `amend_workflow`, read
  `workflow`, contribute your declarative adjustments.
- **On-the-fly composition add-ons** — contribute `extend` entries with
  fresh stage names; authored names always win.
````

---

### Documentation deliverable (not a DSL artifact)

**File:** `docs/features/pipelines/hooks.md` [MODIFIED] — extend with:

- The actions table: the 13 stage-transition actions and `run_resumed` /
  `run_interrupted` (all soft, live mid-run) alongside the existing three.
- The contexts: `StageEvent` and `RunEvent` read tables (same facts as
  `registering-hooks.md`).
- The delivery contract: live best-effort, no replay after a crash; one
  short-lived process per event; observer semantics end-to-end.
- The subscriber env visibility under `inherit_env: true` (the hook
  process inherits the afm process environment incl. the launch env
  layers).
- The two "hooks" vocabularies kept distinct in product language (the
  goga platform actions vs afm lifecycle hooks).

## Dependency Map

```
goga/hooks/catalog  (leaf; +15 soft records; no new imports)
        ▲
        │ (unchanged facade edge)
goga/pipeline/workflow (unchanged)      goga/hooks facade (unchanged)
        ▲                                     ▲
        └──────────────┬──────────────────────┘
                       │
          goga/pipeline/hooks  (+ RunIdentity, StageTransition,
          │                    RunEvent, StageEvent; PipelineHooks +2 methods)
          │ NEW imported types: RunIdentity, StageTransition,
          │ RunEvent, StageEvent (constructed by the bridge;
          │  PipelineHooks + checkpoints usage already imported)
          ▼
          goga/pipeline  (+ hook_bridge.py; write_afm_config,
                          pipeline_cli modified; argparse practice amended)
```

No cycles; the single new type-edge extends the existing parent→child
direction. afm spawns `python -m goga.pipeline hook` externally — no
Python import crosses the docker boundary.

### Impact on dependent cells

- `goga/commands/pipeline` consumes the `pipeline-cli` and
  `registering-hooks` practices of `goga/pipeline` — the changes are
  additions only; its argv composition (list/run) and its contract are
  unchanged.
- `goga/hooks`, `goga/hooks/tools`, and `goga/hooks/dispatch` consume
  `declared_actions` of `goga/hooks/catalog` — the new records are
  additive; the signature and the existing records are unchanged.

## Verification Checklist

After implementing each artifact, verify:

1. **`goga/hooks/catalog`**
   - `declared_actions()` returns the 3 existing + 15 new pipeline records;
     ordering by domain then name; no existing record rewritten.
   - `goga lint` passes; the new records resolve as valid addresses
     (`goga hooks` inspection shows them).
2. **`goga/pipeline/hooks`**
   - The four records are exported through the package facade
     (`python -c "from goga.pipeline.hooks import RunEvent"` etc.).
   - `PipelineHooks.emit_run_event` / `emit_stage_event` emit soft events;
     a failing hook warns and returns; nothing collected.
   - One registry per process: constructing the surface is cheap; the
     registry builds at the first emission only.
   - `checkpoints.md` renders the new section; code examples import
     cleanly.
3. **`goga/pipeline`**
   - `write_afm_config` writes the hook entry into the global layer of
     `~/.afm/config.yaml` (id `goga`, command `python3 -m goga.pipeline
     hook`, `events: all`, `inherit_env: true`, afm-default
     timeout/retries) with all existing fields intact; whole-file
     rewrite safe.
   - `hook_bridge.py`: `map_event_action` — 13 verbatim + 2 normalized,
     everything else None; no platform imports needed at module import.
   - `run_hook`: exit 0 on success / non-curated events / subscriber soft
     failures; non-zero on damaged stdin or an emission crash; the
     curated filter runs before any `goga.hooks` import (verify with a
     non-curated `AFM_HOOK_EVENT` and an empty stdin — no platform
     modules in `sys.modules`).
   - `pipeline_cli hook` dispatches with no options; `--help` shows the
     subcommand; happy path prints nothing.
   - The bridged emission never fires `run_created` / `run_completed`
     (the boundaries stay with the run coordination).
4. **Docs**
   - `docs/features/pipelines/hooks.md` carries the 15 actions, contexts,
     delivery contract, and env-visibility note; the two "hooks"
     vocabularies stay distinct.
5. **Cross-cutting**
   - `goga lint` clean; `goga schema` parses the three manifests (retry
     once — the command is flaky in this tree).
   - Full run with no tool packages installed: identical CLI output,
     exit codes, flow-file bytes; the bridge is silent.
   - Live run with a subscribed tool: stage events arrive mid-run with
     the full context; `event_id` stable; `reason` present when afm
     provides one.
   - Older afm binary (no hooks key): launch unaffected, no bridge, no
     errors.
