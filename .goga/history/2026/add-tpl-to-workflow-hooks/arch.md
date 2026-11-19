# Architecture Plan — Profile-aware workflow contributions

## Topic

- **Short name:** Profile-aware workflow contributions
- **Plan path:** `.goga/history/2026/add-tpl-to-workflow-hooks/arch.md` (path printed by `goga history path -f arch.md`)
- **History topic:** `add-tpl-to-workflow-hooks` (2026)
- **Normative sources:** the ADR (`adr.md` — the settled decisions), the task (`task.md`); input PRD (`prd.md`)
- **Nature of the change:** three existing cells are **modified** (extend in place; no new cells, no new dependency
  edges); one new Routine is declared; two consumer usage files are updated. The project-level jinja2 cook
  (`.goga/usages/cooks/jinja2.md`) was updated during task formulation and needs no action in this plan.

## Implementation Order

1. **`goga/pipeline/workflow`** (MODIFY) — leaf cell (no Imports). Owns the rendering semantics, the fixed jinja2
   environment, the context rule, and the `WorkflowDocument` model. Declares the new `render_contribution` routine and
   exports it (with the existing `ResolvedProfile`) to the dependent cells.
2. **`goga/pipeline/hooks`** (MODIFY) — depends on `goga/pipeline/workflow` (existing edge; the import list grows
   additively with `ResolvedProfile` and `render_contribution`) and on `goga/hooks` (unchanged). Extends the amendment
   view with the profile fact and the amendment walk with the render-at-commit step.
3. **`goga/pipeline`** (MODIFY) — root of the three; depends on `goga/pipeline/hooks` and `goga/pipeline/workflow`
   (both unchanged edges). Wires the operation's resolved profile into the amendment delivery in both forms (run and
   card).

Rationale: each cell consumes only what the already-processed cells provide; the import direction
`workflow ← hooks ← pipeline` is preserved end to end.

## Artifacts

### Cell 1: `goga/pipeline/workflow` — MODIFY

#### CODEMANIFEST diff

**1. Header → `Annotations` (global) — ADD** the following paragraph immediately after the existing
contributor-profile zone paragraph (the paragraph ending with
"`The template context is the entire content of the single active profile; with no activation the context is empty.`")
and before the existing line `Use `jinja2` for the rendering engine contract: ...`:

```
The zone renders two surfaces with one fixed environment per `jinja2`:
whole workflow-files before parsing, and the strings of committed
workflow contributions — the field-level render the pipeline amendment
applies to a tool's document at its commit. The field-level render
touches strings only: structure, field presence, and non-string values
are preserved unchanged.
```

**2. Body — ADD** the following type declaration after the `"render_workflow(...)"` declaration:

```yaml
"render_contribution(document: WorkflowDocument, profile_data: dict[str, Any]) -> rendered: WorkflowDocument":
  location: render_contribution.py
  annotations: |
    Render every template surface of one committed workflow contribution
    with the active profile's content — the field-level rendering step
    the pipeline amendment applies to a tool's buffered document at its
    commit moment, before the authored-wins merge.

    `document`: the committed contribution — a `WorkflowDocument`-shaped
                set of instructions, raw (pre-render)
    `profile_data`: the template context — the entire content of the
                    active profile, or an empty mapping when no profile
                    is active
    `rendered`: a NEW `WorkflowDocument` with every template surface
                rendered; the input is never mutated

    Use `jinja2` for the rendering engine contract: the fixed
    environment flags, the context rule, the missing-key semantics, and
    the strict syntax-error surfacing.
    Apply `convention` for docstring style.

    Algorithm:
    1. Walk `document` type-driven at any depth, over the typed model
       fields and the verbatim extend-entry bodies alike: render every
       string leaf and every string mapping key individually; carry every
       non-string scalar unchanged. The walk is field-set-complete over
       the document model — a new model field flows through this routine
       without touching it again — and no field is exempt: the
       never-merging global fields (profile, build, agent, env) render
       like every other surface
    2. Render each surface with the fixed environment per `jinja2` and
       exactly `profile_data` as the context — no ambient variables
       (tool, pipeline, workflow name) exist in the context
    3. While rendering the keys of one map — detect a rendered-key
       collision: two distinct source keys rendering to the same result
       key raise one strict error naming the map (its dot-path), the
       source keys, and the colliding result
    4. On a template error in any surface — dead fields included — raise
       one strict error carrying the template cause: the error class, the
       message, and the document path — the dot-path of the string
       within the contribution built from the source (pre-render) keys,
       with list elements indexed and the two gates shapes disambiguated
       positionally (the workflow-level gates settings block path versus
       a stage check-step list path)
    5. Return the new `WorkflowDocument` — every surface rendered, every
       non-string value carried unchanged, field presence unchanged (a
       rendered empty string is a value, not an absence)

    Requirements:
    - Pure — no mutation of `document` or its maps; the result is a new
      document
    - No I/O — no files, no environment reads, no subprocess; string
      rendering only
    - A document whose strings carry no template syntax renders to an
      equal document — every string unchanged, presence and order
      preserved
    - Without an active profile the render runs against an empty
      context — template syntax still processes, missing keys render
      empty
    - Rendering never changes field presence — the presence-based
      empty-contribution check downstream is unaffected

    Constraints:
    - Do not parse, validate, or restructure the document — rendering
      replaces string values and keys only; the structure is preserved
    - Do not merge, apply, or interpret the document — the amendment
      merge and the compilation own both
    - Do not resolve profiles or read the environment — the context
      arrives as `profile_data`
    - Do not build a second template environment, dialect, or ambient
      context — one fixed environment, one context rule, per `jinja2`
```

**3. Footer → `Description` — CHANGE** the trailing fragment
`... activation precedence resolution, and whole-file Jinja rendering of workflow-files before parsing.`
to
`... activation precedence resolution, whole-file Jinja rendering of workflow-files before parsing, and field-level rendering of committed workflow contributions.`

Everything else in the CODEMANIFEST stays unchanged.

#### `.usages/` files

None — no new or updated usage files in `goga/pipeline/workflow/.usages/`. The rendering practice lives in the
project-level jinja2 cook (already connected in the header, already covering the field-level pattern); the
consumer-side delivery documentation lives with the hooks pair (cells 2 and 3).

### Cell 2: `goga/pipeline/hooks` — MODIFY

#### CODEMANIFEST diff

**1. Header → `Imports` — CHANGE** the workflow import block from

```yaml
  - Types:
      - WorkflowDocument
      - WorkflowGates
    From: goga/pipeline/workflow
```

to

```yaml
  - Types:
      - WorkflowDocument
      - WorkflowGates
      - ResolvedProfile
      - render_contribution
    From: goga/pipeline/workflow
```

**2. Header → `Annotations` (global):**

- **CHANGE** the sentence
  `Tools are mutually blind — every amendment view reads the original authored workflow, never a staged state.`
  to
  `Tools are mutually blind — every amendment view reads the original authored workflow and the same resolved profile fact, never a staged state.`
- **ADD** the following paragraph immediately after that sentence (closing the first header paragraph):

```
The amendment is profile-aware: every tool's view carries the
operation's already-resolved active contributor profile as a read-only
fact — identical for every tool, absent without activation — and a
tool's committed contribution renders field-level with that profile's
content at its commit moment, inside the walk, before the
presence-based empty-contribution check: every string leaf and every
string mapping key of the contributed document is a template surface,
and `render_contribution` renders them under the fixed workflow
rendering semantics. A render failure is disciplinarily a hook failure
— one hard pre-run error in the amendment-failure format carrying the
template cause; the first failing tool stops the walk, later tools'
hooks never run, and the tool's whole contribution is discarded. A
contribution without template syntax composes byte-identically with or
without an active profile.
```

**3. Body — CHANGE** the `"WorkflowAmendment(...)"` declaration to (parameter, annotation addition, and new property;
the `contribute` method and the other properties stay unchanged):

```yaml
"WorkflowAmendment(pipeline: PipelineIdentity, decision: WorkflowDecision, workflow: WorkflowDocument | None, work: WorkIdentity, profile: ResolvedProfile | None = None)":
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
    `profile`: the operation's already-resolved active contributor
                profile — the profile that rendered the authored
                workflow-file: its name, its whole content, and its
                source (project or home) — or None when no profile is
                active (no activation resolved, or no workflow in
                effect)

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
    Use the `registering-hooks` practice for the hook signature that
    receives this view.

    Requirements:
    - The reads deliver the original facts — no staged-application
      state exists; a tool never sees another tool's contribution
    - The `profile` fact is operation data passed in by the caller —
      no reads and no re-resolution happen at the checkpoint; it is
      read-only and identical for every tool and in every delivery
      form, and reads absent (None) without activation — including
      the no-workflow silent-miss case
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
    "profile -> ResolvedProfile | None": |
      The operation's active contributor profile — its name, its whole
      content, and its source — or None when no profile is active;
      read-only and identical for every tool.
  methods:
    "contribute(document: WorkflowDocument)": |
      Buffer one declarative contribution of this tool.

      `document`: the complete contribution — a `WorkflowDocument`-shaped
                  set of instructions (prompt, stages, extend, memory,
                  assistants, delegation, repeat, gates) using the same
                  vocabulary an authored workflow-file uses

      Requirements:
      - The call buffers into the buffer of this tool alone and changes
        nothing until the delivery commits it
      - The replacement is whole — a later call replaces the earlier
        buffered document
      - A document with no prompt, no stages, no extend, no memory, no
        assistants, no delegation, no repeat, and no gates block is an
        empty contribution — the delivery discards it with a warning

      Constraints:
      - Do not cancel, redirect, or defer the operation — a
        contribution transforms the workflow layer only
```

**4. Body — CHANGE** the `amend_workflow` method of `"PipelineHooks()"` to:

```yaml
    "amend_workflow(pipeline: PipelineIdentity, decision: WorkflowDecision, workflow: WorkflowDocument | None, work: WorkIdentity, profile: ResolvedProfile | None = None) -> overlay: WorkflowOverlay": |
      Deliver the workflow-amendment checkpoint and return the
      effective workflow with its provenance.

      `pipeline`: the identity of the pipeline being composed
      `decision`: the workflow decision of the operation
      `workflow`: the authored workflow after the decision and the
                   runner-skip merge; None when no workflow resolved
      `work`: the current work identity
      `profile`: the operation's already-resolved active contributor
                 profile — the profile that rendered the authored
                 workflow-file — or None when no profile is active
                 (including the no-workflow silent-miss case);
                 identical for every tool and in every delivery form
      `overlay`: the effective workflow and the contributing tools

      Use the `per-tool-delivery` practice for the delivery loop.

      Algorithm:
      1. Resolve the address domain="pipeline", action="amend_workflow"
         against `declared_actions`
      2. Walk the subscriptions of the address per tool in enumeration
         order: build the tool's `WorkflowAmendment` view over the
         delivered facts — every tool reads the same original
         `workflow` and the same `profile` fact — wrap it via
         `wrap_context`, project the call arguments via
         `build_hook_arguments` with the tool's own context, and call
         each hook of the tool
      3. A tool with a raising hook is a hard failure: a clean error
         naming the tool and the action stops the command at the first
         failure; the tool's contribution is discarded
      4. A tool whose every hook returned without raising has its
         buffered document rendered at its commit moment: every string
         of the contribution renders with the active profile's content
         via `render_contribution`, which receives the content of
         `profile` as its rendering context — an empty mapping when
         `profile` is None. A render failure is the same hard failure
         as a raising hook: the clean error naming the tool and the
         action carries the template cause from the render error; the
         tool's whole contribution is discarded and the walk stops
         before the next tool is called
      5. The empty-contribution check runs on the rendered document and
         stays presence-based and unchanged: a tool whose rendered
         document is empty — no prompt, no stages, no extend, no
         memory, no assistants, no delegation, no repeat, and no gates
         block — is a content no-op: a warning naming the tool, the
         action, and the reason, the contribution discarded, the walk
         continues
      6. A tool whose rendered document is non-empty commits as one
         `ToolContribution` — the rendered document is the committed
         document
      7. Merge the committed contributions onto `workflow` via
         `merge_workflow_overlay` and return the overlay

      Requirements:
      - The commit granularity is the tool — a tool's whole
        contribution renders and commits only after every hook of the
        tool succeeds
      - The render runs inside the walk at each tool's commit — never
        as a pass after the walk; after a render failure no later
        tool's hooks run
      - The profile fact never varies per tool — one resolved value
        reaches every view
      - An address without subscriptions returns the passthrough
        overlay — the workflow passed in, an empty provenance
      - The merged result passes the same compilation validation an
        authored workflow passes
      - A contribution without template syntax composes byte-identically
        with or without an active profile

      Constraints:
      - Do not apply any contribution outside the single merge after
        the walk
      - Do not skip a subscriber of the address
      - Do not read repositories or the filesystem at the checkpoint
      - Do not resolve the profile here — the resolved value arrives as
        `profile`
```

All other members of `PipelineHooks()` (`emit_run_created`, `emit_run_completed`, `emit_run_event`,
`emit_stage_event`) and every other type of the cell stay unchanged.

**5. Footer → `Description` — ADD** the closing sentence:
`The amendment is profile-aware: the resolved-profile fact on the view and the commit-time rendering of contributed strings.`

#### `.usages/` files

**File:** `goga/pipeline/hooks/.usages/checkpoints.md` — UPDATE two sections (the rest of the file stays verbatim).

Replace the section `## Resolve the facts in the operation` with:

~~~~markdown
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
- `loaded.profile` — the operation's already-resolved active contributor
  profile (the profile that rendered the authored workflow-file), or
  `None`; the delivery receives it as operation data — the checkpoint
  never reads or re-resolves it.
~~~~

Replace the section `## Amend before compilation` with:

~~~~markdown
## Amend before compilation

Deliver the amendment after the runner-skip merge and before
`compile_flow`; compile the effective workflow the delivery returns.

```python
overlay = hooks.amend_workflow(
    pipeline=identity,
    decision=decision,
    workflow=merged_workflow,  # None is valid — a silent miss keeps the layer active
    work=work,
    profile=loaded.profile,    # the resolved profile or None — every tool's view and the rendering use it
)
compile_flow(overlay.workflow, ...)
```

- A tool contributes one declarative `WorkflowDocument`; authored intent
  wins per slot — the prompt appends, the memory block is whole, the repeat
  block is whole, the gates settings block is whole, stage fields fill only
  what the author left unset (an authored per-stage check-step list is
  never overwritten), extend entries add; the workflow-global run settings
  (`agent`, `env`) ride the authored workflow verbatim — a tool can
  neither supply nor override them; the assistant catalog merges
  with field-level overrides — the winning tool-delivered entry of a name
  is the base and the authored entry replaces exactly the fields it
  specifies (agent, env, delegate, prompt, skills; an explicit empty
  skills/env clears), omitted fields flow from the tool, a delivered name
  with no authored entry adds fresh (tool inline declarations under an
  authored name stay dropped); the delegation block is whole, and stage
  assistant maps append with name deduplication.
- Every tool's view carries the same read-only profile fact (`profile` —
  name, content, source, or `None` without activation); the card and the
  run form deliver the same fact.
- At each tool's commit the buffered contribution renders field-level
  with the active profile's content (workflow rendering semantics; an
  empty context without activation) — before the unchanged
  presence-based empty-contribution check and the authored-wins merge.
- A render failure in any contributed string is hard: the command stops
  pre-run with the amendment-failure error (tool, action) carrying the
  template cause (error class, message, document path); the tool's
  contribution is discarded and later tools' hooks never run.
- A contribution without template syntax composes byte-identically, with
  or without an active profile.
- The amendment action is hard: the first failing tool stops the command
  with a clean error naming the tool and the action; the tool's whole
  contribution is discarded.
- An address without subscriptions returns the passthrough overlay — the
  workflow stays what was passed, the provenance is empty. With no tool
  packages installed every run composes exactly what was passed.
~~~~

### Cell 3: `goga/pipeline` — MODIFY

#### CODEMANIFEST diff

**1. Header → `Imports` — CHANGE** the workflow import block from

```yaml
  - Types:
      - load_workflow
      - WorkflowDocument
      - WorkflowStage
      - WorkflowGateStep
      - LoadedWorkflow
      - WorkflowSyntaxError
    Usages:
      - parse-workflow
      - memory
      - load-workflow
      - profiles
      - assistants
    From: goga/pipeline/workflow
```

to the same block with `ResolvedProfile` appended to `Types` (after `WorkflowSyntaxError`):

```yaml
  - Types:
      - load_workflow
      - WorkflowDocument
      - WorkflowStage
      - WorkflowGateStep
      - LoadedWorkflow
      - WorkflowSyntaxError
      - ResolvedProfile
    Usages:
      - parse-workflow
      - memory
      - load-workflow
      - profiles
      - assistants
    From: goga/pipeline/workflow
```

**2. Header → `Annotations` (global) — ADD** the following fragment at the end of the composition paragraph
(immediately after its closing sentence `The branch, topic, and status facts resolve in the operation before the delivery — the checkpoints read nothing.`):

```
The amendment delivery is profile-aware in both forms: the operation's
already-resolved active contributor profile — the loaded workflow's
profile, None when no workflow resolved — travels into the delivery as
operation data; every tool's view reads the same profile fact and the
delivery renders each committed contribution's strings with that
profile's content before the merge. The run form and the card form
deliver the identical fact and the identical rendering.
```

**3. Body — `describe_pipeline` — CHANGE** step 4 of the Algorithm from

```
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
```

to

```
4. Resolve the amendment facts (the `PipelineIdentity` — the authored
   header name and description read via `parse_dsl` from the
   pipeline-file text; the `WorkflowDecision`; and the `WorkIdentity` —
   the current branch via `resolve_current_branch_name`, the literal
   "unknown" when it resolves None; the hosting topic slug and year via
   `resolve_topic_dir` when its directory exists, the branch-only form
   otherwise) and, unless the decision is disabled, deliver the
   amendment via the `PipelineHooks` checkpoint surface with the merged
   workflow and the operation's resolved profile (the `LoadedWorkflow`
   profile of step 2 — None when no workflow resolved) — receiving the
   overlay result; a disabled decision delivers nothing and the overlay
   is the passthrough `WorkflowOverlay` of the merged workflow
```

and **ADD** the requirement bullet:

```
- The card delivers the amendment with the resolved profile exactly as
  the run form does — the same fact on every tool's view and the same
  rendering of contributed strings; the card's merged composition
  equals what a run with the same flags executes
```

**4. Body — `run_pipeline` — CHANGE** step 12 of the Algorithm from

```
12. Unless the decision is disabled, deliver the amendment via the
    `PipelineHooks` checkpoint surface with the authored workflow after
    the skip merge — receiving the overlay result; a disabled decision
    delivers nothing (the layer is off) and the overlay is the
    passthrough `WorkflowOverlay` of the merged workflow
```

to

```
12. Unless the decision is disabled, deliver the amendment via the
    `PipelineHooks` checkpoint surface with the authored workflow after
    the skip merge and the operation's resolved profile — the profile
    of the loaded workflow (`LoadedWorkflow` profile: a
    `ResolvedProfile`, or None when no workflow resolved): the views
    read it as their profile fact and the delivery renders the
    committed contributions' strings with its content — receiving the
    overlay result; a disabled decision delivers nothing (the layer is
    off) and the overlay is the passthrough `WorkflowOverlay` of the
    merged workflow
```

and **ADD** the requirement bullet:

```
- The amendment delivery carries the operation's resolved profile —
  the loaded workflow's profile, or None when no workflow resolved;
  one resolved value feeds every tool's view and the contribution
  rendering, identically in the run and the card forms
```

**5. Footer** — unchanged (the responsibility zone does not change).

#### `.usages/` files

**File:** `goga/pipeline/.usages/registering-hooks.md` — UPDATE (the tool-author guide; the rest of the file stays
verbatim).

Replace the section `## The amendment view` with:

~~~~markdown
## The amendment view

`amend_workflow` delivers a `WorkflowAmendment` view per tool. The
reads: `pipeline` — the identity of the running pipeline; `decision` —
the workflow decision (disabled / explicit / auto-match / silent-miss,
with the resolved name); `workflow` — the original authored workflow
after the decision and the runner-skip merge, read-only and identical
for every tool (None when no workflow resolved); `work` — the current
work identity; `profile` — the operation's active contributor profile:
`name`, `data` (its whole content mapping), and `source` (`project` or
`home`), or None when no profile is active — including when no workflow
resolved. It is the same profile that rendered the workflow-file, read
identically by every tool; you never need to re-resolve it — the CLI
channel and the home bundle are wired for you.

```python
def add_hardening(context):
    if context.profile and context.profile.name == "strict":
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
- **Every string of your contribution is a template surface.** At your
  tool's commit the platform renders every string of the contributed
  document — values and mapping keys alike, at any depth — with the
  active profile's content, under the same rendering semantics the
  workflow-file uses: a missing profile key renders empty, no active
  profile renders against an empty context, and no other variables
  exist in the context (your tool name, the pipeline, and the workflow
  name are not template variables). A stage prompt contributed as
  `Model: {{ model }}` renders against the profile exactly as an
  authored workflow-file prompt would.
- A template error anywhere in your contribution — fields that never
  merge included — stops the command before it runs: the error names
  your tool and the action and carries the template cause (the error
  class, the message, and the document path of the failing string);
  your whole contribution is discarded and no later tool's hooks run.
  Two keys of one of your maps that render to the same string fail the
  same way — the map, both source keys, and the colliding result are
  named.
- **Legacy note — intended behavior change:** a string carrying literal
  `{{ }}` that used to land in the workflow as inert text now renders
  (or fails). This is the intended and only behavior change; a
  contribution without template syntax composes exactly as before, with
  or without an active profile.
- A failing hook of the amendment stops the command with a clean error
  naming your tool and the action; your whole contribution is discarded.
- The merged workflow passes the same compilation validation as an
  authored one — a contribution naming an unknown stage surfaces as the
  compiler's structural error.
~~~~

**ADD** the scenario to the section `## Integration scenarios`:

```markdown
- **Profile-aware contribution** — subscribe to `amend_workflow`, read
  `profile` (name, content, source) to branch programmatically, and put
  `{{ ... }}` expressions in your contributed strings to template them
  against the same profile the workflow-file used.
```

## Dependency Map

Arrow reads "consumer imports supplier"; layers point downward to the leaves; the platform layer imports nothing.

```
                    goga/hooks  (platform facade; unchanged)
                         ▲
                         │ Types + Usages (unchanged)
                         │
   goga/pipeline/workflow│(leaf; MODIFY)
                         │  exports: ResolvedProfile, render_contribution (NEW)
                         │         + WorkflowDocument, WorkflowGates (existing)
                         ▲
                         │ Types: WorkflowDocument, WorkflowGates,
                         │         ResolvedProfile (+), render_contribution (+)
                         │         — additive to the EXISTING edge
                         │
   goga/pipeline/hooks   │(MODIFY)
                         │  WorkflowAmendment(+profile), amend_workflow(+render-at-commit)
                         ▲
                         │ Types + Usages (unchanged list; the delivery gains an argument)
                         │
   goga/pipeline         │(MODIFY)
                            run_pipeline / describe_pipeline pass loaded.profile
```

- No new dependency edges; no cycles; the fixed direction `workflow ← hooks ← pipeline` is preserved.
- `goga/pipeline/compiler` and `goga/hooks` are untouched consumers.
- `goga/build` (build path) is out of scope by the task constraints; its workflow import set is unaffected.
- `goga/commands/pipeline` imports the `registering-hooks` practice from
  `goga/pipeline` (the tool-package hook subscription context of the host-side
  launcher); the usage-file update is additive — the subscription mechanics it
  documents are unchanged, no contract change reaches that cell.

## Verification Checklist

Run after the CODEMANIFEST and usage-file changes land, in this order:

1. **DSL validity** — `goga lint` passes project-wide (all three modified CODEMANIFESTs parse; no duplicate imports;
   imported types exist in the provider facades — `ResolvedProfile` and `render_contribution` are exported by
   `goga/pipeline/workflow`; no import cycles).
2. **Reference closure** — every backtick reference in the new/changed annotations resolves inside its document:
   `render_contribution`, `profile_data`, `document`, `rendered`, `jinja2`, `convention` (workflow);
   `profile`, `render_contribution`, `per-tool-delivery`, `convention`, `registering-hooks` (hooks);
   `LoadedWorkflow`, `ResolvedProfile`, `PipelineHooks` (pipeline). No "X from Imports" phrasing; no comparative
   references to previously shipped functionality; annotations carry no implementation details.
3. **Practice wiring** — every connected practice is referenced in an annotation (`jinja2` in the new routine's
   annotation and the extended header; `per-tool-delivery` in the rewritten `amend_workflow`); `checkpoints.md` and
   `registering-hooks.md` remain self-contained (no cross-references to other practices).
4. **Contract-content gates** (re-read the changed sections against the ADR):
   - `render_contribution`: type-driven field-set-complete walk; strings and string keys only; never-merging globals
     render; empty-context parity; dot-path failure vocabulary with indexed lists and positionally disambiguated
     gates paths; rendered-key collision failure; purity and no-I/O.
   - `amend_workflow`: render at each tool's commit INSIDE the walk, before the unchanged presence-based
     empty-contribution check; render failure = the hard amendment failure (tool, action) carrying the template
     cause; the walk stops before the next tool; the merge and `merge_workflow_overlay` stay untouched.
   - Wiring: `run_pipeline` step 12 and `describe_pipeline` step 4 pass the same resolved value
     (`LoadedWorkflow.profile`, None when no workflow resolved); signatures of both routines unchanged.
5. **Acceptance-criteria trace** — each criterion of the task maps to a contract element:
   profile-visible amendment → the view fact + both wiring steps; profile-aware contribution → the type-driven
   render + the commit; uniform effect → one `ResolvedProfile` feeding file render and contribution render; parity
   semantics → the empty-context requirement; strict failures → the walk's step 4 semantics; backward compatibility →
   the equal-document requirement, the unchanged presence-based check, the untouched `emit_*` members, no new
   surfaces.
6. **Tests note for the implementation stage** — new tests mirror the source structure per the project convention:
   `tests/pipeline/workflow/test_render_contribution.py` (pure render cases: template values and keys at depth,
   extend bodies, globals, non-string scalars untouched, empty context, collision, error paths with exact dot-path
   messages), extension of the hooks delivery tests (profile fact on the view identical per tool, render-at-commit
   order, first-failure stop, later tools never run, template-free byte-identity), and wiring tests for both forms
   (same resolved value in run and card).
