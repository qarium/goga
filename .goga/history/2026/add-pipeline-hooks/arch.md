# Architecture Plan — pipeline hooks

Author: Goga
CreatedAt: 18/09/26
Topic branch: add-pipeline-hooks
Decision source: `.goga/history/2026/add-pipeline-hooks/adr.md` (ADR wins over PRD; PRD re-aligned)
Task source: `.goga/history/2026/add-pipeline-hooks/task.md`

---

## Topic

- Short name: **pipeline-hooks**
- Plan path: `.goga/history/2026/add-pipeline-hooks/arch.md`

Opening the pipeline domain to installed `goga_tool_*` packages through three
hooks-platform actions (`pipeline/amend_workflow` hard — the platform's first
hard action; `pipeline/run_created`, `pipeline/run_completed` soft), the
authored-wins workflow overlay layer, the run/card integration with provenance,
tool-author documentation, and tests.

---

## Implementation Order

1. **`goga/hooks/catalog` (MODIFY)** — data-only additive records; no Imports;
   every consumer (platform dispatch, `goga hooks`) reads it. No dependencies
   of its own — first.
2. **`goga/pipeline/hooks` (CREATE)** — the pipeline hooks zone. Depends on
   `goga/hooks` (platform facade) and `goga/pipeline/workflow` (instruction
   models) — both exist unchanged, so the zone builds immediately after the
   catalog records it resolves against exist.
3. **`goga/pipeline` (MODIFY)** — run/card integration. Depends on the zone
   (imports its facade and `checkpoints` practice) and on `goga/history`
   (branch/topic/status facts) — designed after its dependency exists.
4. **Documentation** — fill the negative stub `docs/features/pipelines/hooks.md`
   and sync mkdocs traceability; the tool-author usage
   (`goga/pipeline/.usages/registering-hooks.md`) is a cell-3 artifact shipped
   with step 3.
5. **Tests** — per project conventions, alongside each artifact (checklist
   below).

Design order note: cells were designed leaves-to-root; the zone never imports
`goga/pipeline` (the parent imports the zone) — the cross-import rule holds.

---

## Artifacts

### Cell 1 — `goga/hooks/catalog` (MODIFY, data-only)

**CODEMANIFEST diff** — the only change is three bullets appended to the
`Requirements` list of the `declared_actions` annotations (after the
`amend_todo_entry` bullet). Nothing else in the file changes; published
records stay untouched.

Add:

```yaml
    - The catalog carries the pipeline workflow-amendment action — the
      record domain="pipeline", name="amend_workflow", error_class="hard":
      the first failing hook of the action stops the command with a clean
      error naming the tool — the platform's first hard action
    - The catalog carries the pipeline run-creation notification action —
      the record domain="pipeline", name="run_created", error_class="soft":
      a failing hook of the action is skipped with a warning and the command
      continues
    - The catalog carries the pipeline run-completion notification action —
      the record domain="pipeline", name="run_completed", error_class="soft":
      a failing hook of the action is skipped with a warning and the command
      continues
```

**.usages/ files** — none (unchanged).

---

### Cell 2 — `goga/pipeline/hooks` (CREATE)

**CODEMANIFEST** — full content:

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
  emits the two run notifications over the platform facade. One registry
  per run carries every checkpoint of a command — the checkpoints never
  multiply the package enumeration. Every context is built from the
  operation data the caller passes — no repository reads happen here.
  The amendment action is hard — the platform's first: the first
  failing tool stops the command with a clean error naming the tool and
  the action, and the tool's whole contribution is discarded. The two
  notifications are soft — a failing hook warns naming the tool, the
  action, and the reason, and the run's exit code is unaffected. Tools
  are mutually blind — every amendment view reads the original authored
  workflow, never a staged state.
  Use the `per-tool-delivery` practice for the staged delivery loop of
  the amendment checkpoint — its loop skeleton, primitives, and
  tool-grouped commit apply as written.
  Use the `declaring-actions` practice for the emission contract of the
  notification checkpoints.
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
       the tools
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
       base is None and no contribution committed

    Requirements:
    - Pure — the inputs stay unmutated; the result is a new document
    - The prompt concatenation joins the non-empty texts with a single
      blank line between consecutive texts — the authored prompt first,
      then each committed contribution text in enumeration order; no other
      separators, prefixes, or suffixes are added
    - Deterministic — the same inputs give the same overlay
    - The result stays declarative — it passes the same compilation
      validation an authored workflow passes

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

"PipelineHooks()":
  location: events.py
  annotations: |
    The checkpoint surface of the pipeline domain — the amendment
    delivery and the two run notifications over the platform facade.

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
      checkpoints
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

---

Author: Goga
CreatedAt: 18/09/26
Description: |
  Owner of the pipeline domain hooks zone — the run-event facts, the
  workflow amendment with its overlay, and the checkpoint surface over
  the hooks platform.
```

**.usages file** — `goga/pipeline/hooks/.usages/checkpoints.md` (full content):

```markdown
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
    pipeline=identity, decision=decision, overlay=overlay,
    composition=stages, work=work, statuses=statuses,
    runtime_dir=runtime_dir,
)
exit_code = run_flow(...)
statuses = resolve_topic_status(topic_dir, scale)  # recompute at the moment
hooks.emit_run_completed(
    pipeline=identity, decision=decision, overlay=overlay,
    composition=stages, work=work, statuses=statuses,
    runtime_dir=runtime_dir, exit_code=exit_code,
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
```

---

### Cell 3 — `goga/pipeline` (MODIFY)

**CODEMANIFEST diff** — six localized changes; everything else unchanged.

**3.1 Imports** — append two groups to the existing `Imports` list (the five
existing groups stay verbatim):

```yaml
  - Types:
      - PipelineHooks
      - PipelineIdentity
      - WorkflowDecision
      - WorkIdentity
      - CompositionStage
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
```

**3.2 Global Annotations** — insert one paragraph after the
`GOGA_SKIP_STAGES=<csv>` paragraph:

```yaml
  The run coordination and the card compose through the pipeline hooks zone:
  the workflow amendment is delivered after the runner-skip merge and before
  compilation, the run notifications fire around the runner launch, and the
  card reports the contributing tools. An explicit workflow disable turns
  the layer off — the raw authored DSL composes and no amendment delivers;
  a silent auto-match miss keeps the layer active onto the empty base. The
  branch, topic, and status facts resolve in the operation before the
  delivery — the checkpoints read nothing. With no tool packages installed
  the overlay is the passthrough — every form behaves exactly as before.
  Use the `checkpoints` practice for the checkpoint surface of the zone.
  Use the `topic-paths` practice for the topic directory resolution behind
  the work identity and the `topic-statuses` practice for the status facts
  of the run events.
```

**3.3 `run_pipeline`** — replace the full annotations block (signature and
`location` unchanged):

```yaml
  annotations: |
    Resolve a pipeline name to an absolute file path via `list_pipelines`,
    resolve an optional workflow via `resolve_workflow` from the environment
    decision, deliver the workflow amendment through the pipeline hooks zone,
    compile the pipeline-file (extended by the effective workflow) into an
    afm flow-file at runtime via `compile_flow`, materialize the four
    agent prompt files (defaults plus inline overrides) into the runtime
    prompts directory, emit the run-creation facts, launch afm through
    `run_flow`, and emit the run-completion facts on its return. This is the
    run coordination routine — it performs discovery, workflow resolution,
    path resolution, fact resolution, amendment delivery, compilation, and
    prompt materialization; the actual subprocess execution lives in
    `run_flow`.

    `name`: pipeline name without extension
    `project_dir`: project-level pipelines directory (same meaning as in `list_pipelines`)
    `user_dir`: user-level pipelines directory (same meaning as in `list_pipelines`)
    `port`: TCP port forwarded to afm run --port via `run_flow`
            (allocated by the host-side caller)
    `parallel`: optional cap on concurrently executing stages, forwarded to
                `run_flow` as its max_parallel argument. When None (default) —
                afm runs unbounded (run_flow omits --max-parallel). Read from
                the in-container CLI --parallel flag
    `exit_code`: 0 on success, non-zero on error (missing pipeline, missing
                 binary, afm failure, structural DSL error, workflow parse
                 error, materialization error). 127 means afm is not on PATH
                 inside the container.

    Apply `convention` for error-handling style and docstring formatting.
    Apply `parse-workflow` for the workflow-file contract consumed through
    `resolve_workflow`.
    Apply `compile-flow` for the compilation step contract and the documents
    tuple.
    Apply `default_prompts` for resolving the packaged default prompt files.
    Apply `run-flow` for the subprocess launch contract.
    Apply `checkpoints` for the amendment delivery and the two emissions of
    the pipeline hooks zone.
    Apply `topic-paths` for the work identity resolution and
    `topic-statuses` for the status facts of the run events.

    Algorithm:
    1. Discover pipelines via `list_pipelines` and find the entry whose name
       matches
    2. If no match — report that the pipeline is missing and return a
       non-zero exit code
    3. Build the absolute pipeline path from the matching entry's source
       directory and the pipeline name
    4. Resolve the in-container runtime directory from the AFM_DIR
       environment variable; when unset raise a readable "AFM_DIR not set"
       error; resolve the value to an absolute path
    5. Compose the output flow path inside that directory
    6. Read the workflow decision from the environment —
       GOGA_WORKFLOW_DISABLED="1" disables the workflow, otherwise
       GOGA_WORKFLOW_NAME names an explicit workflow — and resolve via
       `resolve_workflow` with the pipeline name
    7. Read GOGA_SKIP_STAGES from the environment (unset/empty — no skip);
       when non-empty split into names and apply via `apply_skip_stages`
       onto the resolved workflow
    8. Resolve the amendment facts from the operation's own data: the
       `PipelineIdentity` (discovered name, authored header name and
       description, entry source), the `WorkflowDecision` (disabled /
       explicit / auto-match / silent-miss with the resolved name), and the
       `WorkIdentity` (current branch via `resolve_current_branch_name`;
       the hosting topic slug and year via `resolve_topic_dir` when its
       directory exists, the branch-only form otherwise)
    9. Unless the decision is disabled, deliver the amendment via the
       `PipelineHooks` checkpoint surface with the authored workflow after
       the skip merge — receiving the overlay result; a disabled decision
       delivers nothing (the layer is off)
    10. Resolve the in-container project name via `resolve_project_name`
        (None when the git origin remote is unavailable). Compile via
        `compile_flow` with the overlay workflow (the resolved workflow when
        the layer is off), the in-container project root (Path.cwd()) as
        root_dir, and the project name; receive the documents tuple;
        structural errors propagate unchanged
    11. Materialize agent prompts atomically (validate-all, then wipe, then
        write): resolve the default prompts directory per `default_prompts`;
        for each overridable role (planner, executor, reviewer) require an
        inline override from the documents tuple or an existing default file
        (stem via `translate_role`); require the summary default; then reset
        <AFM_DIR>/prompts/ and write exactly four files — overrides where
        present, defaults otherwise, summary always from the default
    12. Order the compiled stages via `order_stages` and build one
        `CompositionStage` per ordered stage — id from the `FlowStage` id,
        title from the `FlowStage` name
    13. Resolve the work statuses — the maximal present statuses of the
        hosting topic via `assemble_status_scale` and `resolve_topic_status`;
        an empty list in the branch-only form
    14. Emit the run-creation facts via the checkpoint surface immediately
        before the launch: the identity, the decision, the overlay, the
        composition, the work identity, the statuses, and the runtime dir as
        a posix string
    15. Launch afm via `run_flow` with the compiled flow-file path, `port`,
        and max_parallel=`parallel`
    16. On every return of `run_flow` — zero, non-zero, and spawn failures
        alike — recompute the work statuses at the completion moment and
        emit the run-completion facts with the actual exit code
    17. Return the exit code returned by `run_flow`

    Requirements:
    - Always pass the absolute pipeline path to `compile_flow` — never the
      bare name
    - Always pass the absolute compiled flow path to `run_flow` — never the
      bare name or the DSL path
    - Always forward `port` to `run_flow`; forward `parallel` (None
      propagates — no --max-parallel flag)
    - Read AFM_DIR, GOGA_WORKFLOW_DISABLED, GOGA_WORKFLOW_NAME, and
      GOGA_SKIP_STAGES directly from the process environment
    - GOGA_WORKFLOW_DISABLED="1" takes precedence over GOGA_WORKFLOW_NAME
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
    - `run_created` fires immediately before the runner launch;
      `run_completed` fires on every launch-attempt return path — no exit
      path skips the completion emission
    - A missing pipeline and a structural composition error fire no events
      — the return happens before the checkpoints
    - The runtime dir fact is the resolved AFM_DIR path as a posix string
    - With no tool packages installed the overlay is the passthrough — the
      compiled workflow, the prompts, and the output behave exactly as
      before
    - <AFM_DIR>/prompts/ contains exactly four files after step 11 succeeds;
      validation precedes any wipe or write — atomicity guarantees no
      partial state on disk
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
    - Do not invoke afm directly outside `run_flow`
    - Do not invoke the compiler outside `compile_flow`
    - Do not invoke the workflow parser outside `parse_workflow`
    - Do not allocate the port — the caller allocates it
    - Do not default `parallel` — None means unbounded
    - Do not accept relative `project_dir` or `user_dir`
    - Do not mask or wrap exceptions from `compile_flow` or `parse_workflow`
      — structural errors propagate with their readable messages
    - Do not resolve git or topic facts inside a hook delivery — the
      operation owns the resolution
    - Do not skip the completion emission on any launch-attempt return path
    - Do not write prompts inside the project directory or /workspace —
      always <AFM_DIR>/prompts/
    - Do not write inline prompt overrides into the compiled flow-file
    - Do not delete skipped stages or rewrite depends_on — `compile_flow`
      does both
    - Do not write or generate a workflow-file for skip — the merge is
      in-memory only
```

**3.4 `describe_pipeline`** — replace the full annotations block (signature
and `location` unchanged):

```yaml
  annotations: |
    Compose the card of a single pipeline: name, description, the
    post-workflow stage composition as it would execute, and the tools
    that contributed to it.

    `name`: pipeline name without extension
    `project_dir`: project-level pipelines directory (absolute)
    `user_dir`: user-level pipelines directory (absolute)
    `workflow`: optional explicit workflow name (without the .yml extension)
    `no_workflow`: when True, workflow application is disabled
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
    2. Resolve the workflow via `resolve_workflow` with the pipeline name and
       the workflow flags
    3. Resolve the amendment facts (the `PipelineIdentity`, the
       `WorkflowDecision`, and the `WorkIdentity` — the current branch via
       `resolve_current_branch_name`; the hosting topic slug and year via
       `resolve_topic_dir` when its directory exists, the branch-only form
       otherwise) and, unless the decision is disabled, deliver the
       amendment via the `PipelineHooks` checkpoint surface with the resolved
       workflow — receiving the overlay result
    4. Compile the pipeline-file via `compile_flow` into a temporary flow-file
       located in a system temporary directory — outside the project
       directory and outside every runtime directory — with the overlay
       workflow, and receive the documents tuple
    5. Order the compiled stages via `order_stages`
    6. Build the card: name and description from the parsed pipeline document
       header; one `CardStage` per ordered stage — id from the `FlowStage`
       id, title from the `FlowStage` name (the display label); the card
       provenance from the overlay
    7. Discard the temporary flow-file and return the card

    Requirements:
    - The stage composition equals the composition a run of the same pipeline
      with the same workflow flags would execute — the same amendment layer
      with the same precedence and the same compilation machine produce
      both
    - The card names the contributing tools — the provenance is empty when
      nothing contributed
    - An explicit workflow disable turns the layer off — no delivery
      happens and the raw authored DSL composes
    - A silent auto-match miss keeps the layer active — the delivery runs
      onto the empty base
    - Loop-expanded stage copies appear as separate stages
    - The run-only GOGA_SKIP_STAGES environment variable is not read — the
      CLI skip channel is a run concern; workflow-file skip directives DO
      apply through the shared compilation machine (part of the composition
      a run with the same workflow flags executes)
    - The temporary flow-file lives outside the project and runtime
      directories and is removed afterwards
    - The card name and description are the authored DSL header values

    Constraints:
    - Do not launch afm and do not run any stage — the card is read-only
    - Do not emit run events in card form
    - Do not write into the project directory or any runtime directory
    - Do not re-parse the pipeline-file — header data comes from the documents
      tuple
    - Do not reorder stages beyond `order_stages`
```

**3.5 `PipelineCard`** — replace the type block:

```yaml
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
    - `provenance` defaults to an empty list via
      field(default_factory=list) in the implementation; the signature
      default `[]` is a DSL representation, the actual default factory is
      applied at construction

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
```

**3.6 `pipeline_cli`** — replace the card-template requirement bullet in the
`Requirements` list (all other bullets, the signature, Algorithm, and
Constraints unchanged):

```yaml
    - The card template: a "name:" line, a "description:" line, a blank line,
      a "---" separator, a blank line, then per ordered stage the marker line
      "* <id>:" and a "title:" line indented by four spaces; the separator
      block is printed even when the card carries no stages; when the card
      provenance is non-empty, one blank line and one "tools:" field line
      follow the stage blocks — the contributing tools comma-separated in
      provenance order; an empty provenance adds nothing — the output stays
      byte-identical to the provenance-free card
```

**.usages file** — `goga/pipeline/.usages/registering-hooks.md` (CREATE,
full content):

```markdown
# pipeline — registering hooks

How a `goga_tool_*` package subscribes its hooks to the pipeline domain
actions. For tool package authors; no goga code changes are needed.

The domain opens three actions. One is an amendment — a read-and-contribute
view over the workflow a run is about to execute, delivered before
compilation; it is the platform's first hard action. Two are notifications —
the read-only facts of the run, delivered immediately before the runner
launch and on every launch-attempt return.

## The events

| Address | Error class | Fires |
|---|---|---|
| `pipeline / amend_workflow` | hard | After the workflow resolution and the runner-skip merge, before compilation — in the run form and in the card form alike. |
| `pipeline / run_created` | soft | Immediately before the runner launch — after compilation and prompt materialization. |
| `pipeline / run_completed` | soft | On every launch-attempt return — zero, non-zero, and spawn failures (126/127) alike. |

A failing moment fires nothing: a missing pipeline and a structural
composition error return before any checkpoint.

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
`self` — the isolated context of your tool. The declaration order does
not matter; names you did not declare receive nothing.

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

## Integration scenarios

- **Artifact → status on completion** — subscribe to `run_completed`,
  read `work` and `exit_code`, register your status on the statuses
  domain keyed by your artifact.
- **Run reporting and automation** — subscribe to `run_created` and
  `run_completed`, read the facts, keep state in your `self` context.
- **Workflow personalization** — subscribe to `amend_workflow`, read
  `workflow`, contribute your declarative adjustments.
- **On-the-fly composition add-ons** — contribute `extend` entries with
  fresh stage names; authored names always win.
```

**Existing .usages sync** — three shipped practices of the cell drift with
the integration and are updated in place (no structural rewrites):

- `goga/pipeline/.usages/describe-pipeline.md` — document the `provenance`
  field of `PipelineCard` in "The models"; state in the intro and the
  workflow-equivalence section that the card composes through the pipeline
  hooks zone with the same precedence a run applies, that the card names the
  contributing tools, and that no run events fire in card form.
- `goga/pipeline/.usages/pipeline-cli.md` — extend the `--info` card format
  with the conditional `tools:` field line — printed only when the card
  provenance is non-empty, the contributing tools comma-separated in
  provenance order; an empty provenance adds nothing (byte-identical card).
- `goga/pipeline/.usages/run-pipeline.md` — insert the amendment delivery
  between the skip merge and compilation in the composition flow, and note
  the two run events (`run_created` immediately before the launch,
  `run_completed` on every launch-attempt return).

---

### Non-cell deliverables (task items 6–7)

- **`docs/features/pipelines/hooks.md`** — fill the negative stub with the
  address | error class | fires table, the context members, and the failure
  semantics (source material: the `registering-hooks` usage above; nav slot
  already exists in `mkdocs.yml`).
- **MkDocs traceability** — sync after the docs fill; no navigation changes
  required.
- **Tests** — per `.goga/usages/conventions.md`: unit coverage for the
  overlay merge semantics (per-slot precedence, enumeration order, per-tool
  commit/discard), the event timeline (pre-launch creation, any-exit
  completion with code and runtime dir incl. 126/127), card/run equivalence,
  and the zero-impact guarantee.

---

## Dependency Map

```
 [unchanged leaves]                 [modified]                [new]

 goga/pipeline/workflow ──T: WorkflowDocument──────────┐
                                                 │
 goga/hooks (facade) ──T: HookRegistry, wrap_context,
   build_hook_arguments, emit_hook_event,
   declared_actions + U: declaring-actions,
   per-tool-delivery, registering-hooks──────────┤
                                                 ▼
                                     goga/pipeline/hooks (CREATE)
                                     11 types + .usages/checkpoints.md
                                                 │
                                                 │ T: PipelineHooks, PipelineIdentity,
                                                 │    WorkflowDecision, WorkIdentity,
                                                 │    CompositionStage + U: checkpoints
                                                 ▼
 goga/history ──T: resolve_current_branch_name,──────► goga/pipeline (MODIFY)
   resolve_topic_dir, resolve_topic_status,              │
   assemble_status_scale + U: topic-paths,               ├──► goga/pipeline/compiler (unchanged)
   topic-statuses                                        └──► goga/afm (unchanged)

 goga/hooks/catalog (MODIFY: +3 records) — consumed through the platform;
 published records and the remaining platform cells unchanged
```

No circular dependency: the zone never imports `goga/pipeline`; the parent
imports the zone. `goga/history` imports no pipeline cell.

---

## Verification Checklist

**`goga/hooks/catalog` (after step 1)**
- `goga lint` passes; the three records are additive; the published records
  and `Action` are untouched
- `declared_actions()` ordering stays domain-then-name with the new records
- unit tests: catalog completeness and deterministic ordering

**`goga/pipeline/hooks` (after step 2)**
- `goga lint` passes on the new CODEMANIFEST; the facade `__init__` exposes
  all eleven contract types through `__all__`
- facade check: `python -c "from goga.pipeline.hooks import PipelineHooks"`
- unit tests: per-slot precedence (prompt append order, memory whole-block,
  stages per-field with `skip` as an ordinary field, extend add with
  later-tool-wins), enumeration order, per-tool commit/discard, hard-stop
  with a clean error naming tool and action, empty-buffer warning +
  continue, mutual blindness of the amendment views, passthrough overlay,
  emission context members, soft-warn semantics, no repository reads at the
  checkpoints

**`goga/pipeline` (after step 3)**
- `goga lint` passes; run/card tests: the amendment delivers between the
  skip merge and `compile_flow`; `run_created` fires immediately before
  `run_flow`; `run_completed` fires on zero, non-zero, and 126/127 returns
  with the recomputed statuses and the actual exit code; no events on a
  missing pipeline or a structural composition error
- card/run equivalence: the same flags produce the same composition and the
  same provenance in both forms; the card names the contributing tools
- disable semantics: an explicit disable delivers nothing and composes the
  raw DSL; a silent auto-match miss keeps the layer active
- zero impact: with no tool packages installed, every form's output,
  errors, and exit codes are byte-identical to the pre-change behavior
  (empty provenance adds no line to the card)
- the three existing usage files of the cell are in sync with the new
  surface (describe-pipeline models list `provenance`; pipeline-cli card
  format carries the conditional `tools:` line; run-pipeline flow carries
  the amendment step and the two events)

**Documentation (after step 4)**
- `docs/features/pipelines/hooks.md` answers each integration scenario from
  the problem (artifact → status, run reporting/automation, workflow
  personalization, on-the-fly add-ons) from moments, context members, and
  failure semantics alone; mkdocs nav and traceability in sync

**Final**
- `pytest tests/ -x` green; `ruff check goga/` clean; AC1–AC9 of the task
  re-verified against the implementation
