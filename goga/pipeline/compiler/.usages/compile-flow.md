# Compile Flow — goga/pipeline/compiler

## Overview

`compile_flow` is the entry point of the cell: it reads a pipeline-file written
in goga DSL (phases-list or stages-map format), optionally applies instructions
from a declarative workflow, compiles the result into an afm flow-file
(byte-exact with the canonical `flow.yml` format), and writes the result to the
given output path. It also returns the parsed input representation alongside the
serialized output representation as a documents tuple, so consumers can read
header-level artifacts (such as the `roles` inline prompt overrides) without
re-invoking `parse_dsl`. Use this routine when you need the full pipeline → flow
transformation, optionally extended by a workflow, in one call.

## Usage

### Basic transformation (no workflow)

```python
from pathlib import Path
from goga.pipeline.compiler import compile_flow

# Inside the goga container: AFM_DIR is the runtime directory
# mounted by the host-side launcher.
pipeline_path = Path("/workspace/.goga/pipelines/feature-phases.yml")
flow_path = Path("/home/goga/pipeline/flow.yml")

documents = compile_flow(pipeline_path, flow_path)
pipeline_doc, flow_doc = documents
# flow_path now contains a byte-exact afm flow-file.
# pipeline_doc.header.roles carries any inline prompt overrides.
```

### With a workflow applied

```python
from pathlib import Path
from goga.pipeline.compiler import compile_flow
from goga.pipeline.workflow import parse_workflow

pipeline_path = Path("/workspace/.goga/pipelines/feature-phases.yml")
workflow_path = Path("/workspace/.goga/workflows/feature-phases.yml")
flow_path = Path("/home/goga/pipeline/flow.yml")

workflow = parse_workflow(workflow_path)
documents = compile_flow(pipeline_path, flow_path, workflow=workflow)
# flow_path now contains the extended flow-file with:
# - top-level prompt (if the workflow provided one)
# - per-stage command/description overrides
# - loop-expanded stage copies
# - rewritten external depends_on references
# pipeline_doc.header.roles still carries inline prompt overrides;
# pipeline_doc.body reflects the ORIGINAL parsed body (NOT reconstructed).
```

### Workflow with extend (new stages injected)

```python
from pathlib import Path
from goga.pipeline.compiler import compile_flow
from goga.pipeline.workflow import parse_workflow

pipeline_path = Path("/workspace/.goga/pipelines/feature-phases.yml")
workflow_path = Path("/workspace/.goga/workflows/feature-with-extend.yml")
flow_path = Path("/home/goga/pipeline/flow.yml")

workflow = parse_workflow(workflow_path)
documents = compile_flow(pipeline_path, flow_path, workflow=workflow)
# In addition to per-stage overrides and loop-expansion, the compiled
# flow-file carries the extend-stages embedded and positioned via
# before/after. A dangling before/after ref (naming no step and no
# extend-stage) now raises a structural error.
```

A workflow-file with an `extend:` block:

```yaml
prompt: |
  Top-level prompt emitted as the first directive of the compiled flow-file

stages:
  propose:
    skills:
      - web-search

extend:
  warmup:
    before: [propose]
    agent: codex
    loop: 3
    title: Warmup
    prompt: Bootstrap context before the first stage (looped on codex)
  extra-check:
    after: [review]
    title: Extra check
```

Each extend-entry is positioned by the compiler: `after` adds the named stages
to the new stage's `depends_on` (STAGES) or places it after them (PHASES);
`before` adds the new stage to the named stages' `depends_on` (STAGES) or
places it before them (PHASES). `depends_on` is forbidden in an extend-entry;
at least one of `before`/`after` is required.

An extend-entry may additionally carry inline `agent` (str) and `loop`
(int `>= 1`) — extracted into the model, not part of the body. These act as
DEFAULT overrides for the new stage; a `stages`-block entry for the same name
wins per field (see Priority rule above). A `stages`-block entry may also carry
`skills`, which the compiler merges with the step's pipeline-file skills. Any
stage — extend or original — that ends up with no authored `roles` value
carries the default `agents: [auto]` in the compiled flow-file (see Default
stage-field injection above).

## Parameters

- `pipeline_path: Path` — absolute path to the input pipeline-file. The file
  must be a goga DSL file: a header segment (`name`, `description`, optional
  `roles` block) followed by a `---` separator, then a body segment (YAML list
  for phases, YAML dict for stages).
- `flow_path: Path` — absolute path to the output flow-file. The parent
  directory must already exist; `compile_flow` does not create it.
- `workflow: WorkflowDocument | None = None` — optional declarative instructions
  from a project workflow-file. When a `WorkflowDocument` is passed (parsed via
  `parse_workflow`), the cell reconstructs the parsed body per the workflow
  instructions BEFORE building the FlowStages. `workflow.stages` entries may
  carry `agent` / `prompt` / `loop` / `skills`; `workflow.extend` entries may
  additionally carry inline `agent` (str) and `loop` (int `>= 1`) extracted
  from the entry body. When `None` — no workflow is applied, the output
  carries no top-level prompt and no per-stage overrides.
- `root_dir: str | None = None` — optional top-level afm `root_dir` directive.
  When a non-`None` string is passed, the compiled flow-file carries a
  top-level `root_dir:` key (emitted immediately after `prompt` when present,
  before `name`). When `None` — the `root_dir:` key is omitted entirely
  (back-compat with flow-files that carry no `root_dir`). The compiler
  performs NO environment-variable reads: the caller computes the value.
  In the standard in-container pipeline, `run_pipeline` resolves the value
  from `Path.cwd()` (= `/workspace` inside the goga container — the single
  source of truth mirroring the host-side mount decision).
- `project_name: str | None = None` — optional project name used as the
  description prefix in the compiled flow-file. When not `None`, the
  `FlowDocument` description becomes `f"[{project_name}] {header.description}"`;
  when `None`, the description is the header description unchanged. OUTPUT-only —
  the `PipelineDocument` description stays the faithful mirror (like `root_dir`).
  The compiler performs NO environment / subprocess reads; `run_pipeline`
  resolves the value in-container via `resolve_project_name` (basename of the
  git origin remote URL, minus a trailing `.git`; `None` when unavailable).

## Return Values

`compile_flow` returns a `tuple[PipelineDocument, FlowDocument]`:

- `PipelineDocument` — the parsed input representation (header, body format,
  body). The body field reflects the ORIGINAL parsed body, NOT the
  workflow-reconstructed body — workflow-reconstructed stages live only in
  `FlowDocument.stages`. Carries `header.roles: PipelineRoles | None` — inline
  prompt overrides parsed from the header-level `roles:` block, or `None` when
  the block is absent or empty.
- `FlowDocument` — the serialized output representation (the afm flow-file
  model). When a workflow was applied, the FlowDocument carries the reconstructed
  stages, loop-expanded depends_on, and `prompt: str | None` (emitted as the
  first top-level key when not None). Does NOT carry `roles` — inline prompts
  are a goga-side artifact, not part of the afm flow-file.

The text flow-file is also written to `flow_path` as a side effect. On failure,
an exception is raised (see below) and the documents tuple is not returned.

## Supported Input Formats

Two body shapes are supported:

- **phases** — body is a YAML list of step items. Each item is a map with a
  `name:` key (the step id), a `title:` key (display label), and any
  extra fields (`roles`, `prompt`, `skills`, `interactive`). `depends_on` is
  auto-generated by list position: the first step has no `depends_on`, each
  subsequent step depends on the previous one. When a workflow with `loop: N`
  is applied to a PHASES stage, the expanded copies chain naturally via list
  position (first copy inherits the original position, subsequent copies depend
  on predecessor, the next ORIGINAL step depends on the last copy).
- **stages** — body is a YAML dict keyed by step id. Each value is a map with
  `title:` and optional `depends_on:`, plus any extra fields.
  `depends_on` is passed through as-is, EXCEPT that a workflow with loop
  expansion rewrites external references to base names to the LAST expanded id
  (e.g. a stage depending on "review" gets rewritten to depend on "review-2"
  when review has loop=2).

Any other body shape (scalar, missing `---` separator, already-afm format with
a top-level `stages:` key but no separator) raises a structural error.

The optional header-level `roles:` block accepts three fixed keys —
`planner`, `executor`, `reviewer`. Each value is an inline prompt text
(str). Unknown keys (including `summary`), non-str values, and empty
mappings are handled by `parse_dsl` per its contract; the legacy `agents`
key is a structural error. The `roles` data is carried through
`PipelineHeader.roles` (of type `PipelineRoles`) and never enters the
compiled afm flow-file.

## Workflow Application (when a workflow is provided)

When `compile_flow` is called with a non-None `workflow`, the cell reconstructs
the parsed body BEFORE building the FlowStages:

0. **Embed extend-stages**: for each entry in `workflow.extend`, position the
   new stage. STAGES: build a `StageStep` whose `depends_on` is initialized
   from `after`, and append the new stage to the `depends_on` of each
   `before`-target. PHASES: insert the new `PhaseStep` into the body list
   after its `after`-targets and before its `before`-targets (`PhaseStep`
   carries no `depends_on`; ordering is positional). Every before/after ref is
   guaranteed to resolve here — step 0.45 strict-validates them BEFORE the embed
   and raises a structural error on a dangling ref; cross-references between
   extend-stages resolve. Runs BEFORE per-stage overrides,
   loop-expansion, and reference rewriting (which then apply to extend-stages
   uniformly; after loop-expansion both `after`- and `before`-derived refs in
   STAGES resolve to the LAST expanded id).
0.45. **Strict validation of `extend.<name>.before/.after` refs**: build the
   valid-name set = (every original step name) ∪ (every extend-stage name in
   `workflow.extend` — so a cross-reference to another extend-stage resolves).
   For each `before`/`after` ref: if the ref is NOT in the valid-name set, raise
   a structural error `unknown stage name in workflow.extend.<name>.before: <ref>`
   (or `.after`). This REPLACES the previous silent WARNING+skip / verbatim
   pass-through. Runs BEFORE the step-0 embed (and before any skip removal), so a
   ref to a stage that exists in the original body — even if also marked
   `skip: true` — is NOT flagged (it is removed later at step 0.6; referencing a
   skipped stage is not a dangling ref). Existence only is checked; cycles,
   self-references, and duplicate refs stay afm's concern.

0.5. **Strict validation of `workflow.stages` names**: build the valid-name set =
   (every original step name) ∪ (every extend-stage name embedded at step 0).
   For each name in `workflow.stages`: if the name is NOT in the valid-name set,
   raise a structural error `unknown stage name in workflow.stages: <name>`.
   This REPLACES the previous silent warning+skip for unknown names. The check
   runs on the FULL set (before skip removal), so a stage that exists — even if
   also marked `skip: true` — is NOT flagged as unknown. Extend-stage names are
   valid (embedded first). Strictness over `extend.<name>.before/.after` refs is
   enforced symmetrically at step 0.45 (a dangling ref is a structural error
   there too).

0.6. **Skip removal + transparent depends_on reconnection**: stages whose
   `workflow.stages[name].skip` is True (and exist) are removed from the
   working body.
   - Stages format: dependents' `depends_on` are transparently reconnected — a
     reference to a removed stage S is replaced with S's transitive non-skipped
     predecessors (`resolve(S)`); chains resolved; no dangling refs or duplicates.
     `resolve` uses a visited set so a `depends_on` cycle among skipped stages
     terminates (cycles stay afm's concern; the compiler does not crash on one).
   - Phases format: removed steps drop from the list; `depends_on` re-derives by
     position (automatic collapse).
   `skip` wins over `agent`/`prompt`/`loop`/`skills` overrides (removal runs
   before Pass 1). If the reconstructed body becomes empty (every stage
   skipped), raise a structural error `empty body`.
1. **Per-stage overrides (in-place on the step body)**: for each stage name
   that has an explicit `stages`-block entry OR originated from an
   extend-entry carrying inline `agent`/`loop`, determine the EFFECTIVE
   override (per-field: `stages`-block value when provided, else the
   extend-entry's inline value, else None/1 — the `stages` block wins per
   field):
   - Find the step in the body whose `name`/id equals the stage name.
   - If not found — silent (it can only be an intentionally skipped stage
     removed at Pass 0.6; unknown names already errored at Pass 0.5).
   - If found:
     - when the effective agent is not None — add
       `body["command"] = "/home/goga/bin/{effective_agent}-as-claude.sh"`
       (path composition inline, no host-side resolver call)
     - when `workflow_stage.prompt` is not None — add
       `body["description"] = workflow_stage.prompt` (prompt has no inline
       extend equivalent — an extend-entry's prompt already lives in its body)
     - when `workflow_stage.skills` is not None — merge skills:
       `body["skills"] = dedup(pipeline_skills ++ workflow_skills)`, where
       `pipeline_skills` is the step body's existing `skills` (or `[]`) and
       `workflow_skills` is the `stages`-block skills list (`++` concatenates
       pipeline first; dedup drops later duplicates by value). Both-empty
       yields no `skills` key.
2. **Loop-expansion (build a new ordered sequence of steps)**: for each step
   determine `loop_count` as the EFFECTIVE loop: `stages`-block `loop` when
   provided, else the extend-entry's inline `loop` when the step originated
   from an extend-entry carrying one, else 1. When `loop_count >= 2`, append N
   copies with id `<name>-1`, ..., `<name>-N`, each subsequent copy depending
   on the previous one. Record `expanded_ids: dict[str, list[str]]` mapping
   base-name to the list of ids produced.
3. **External depends_on rewrite** (STAGES format only — PHASES is handled by
   list position): for each `StageStep` with non-None `depends_on`, replace any
   reference matching a base-name with `loop_count >= 2` with
   `expanded_ids[ref][-1]` (the LAST expanded id).

**Priority rule (inline extend vs `stages` block)**: an extend-entry's inline
`agent`/`loop` are DEFAULT override values; an explicit `stages`-block entry
for the same name wins PER FIELD. Thus a `stages`-block `agent` → command
composition wins over an inline `agent`, and a `stages`-block `loop` wins over
an inline `loop`. Inline `agent`/`loop` never appear in the compiled flow-file
as stage fields — they are extracted into the model by `parse_workflow` and
consumed only as override defaults. Extend-entry `skills` are NOT merged — they
pass through verbatim as the new stage's skills (a new stage has no pipeline
side to merge with).

## Default stage-field injection

The input stage-body field for the afm agents list is `roles` (an authoring
`agents` key in a stage body is a structural error). The afm `interactive`
field is authored as the `communication` key in a stage body (pipeline-file
stage AND embedded extend-stage) and translated to the output `interactive`
key in its canonical slot; an authoring `interactive` key is a structural
error "interactive key is forbidden in stage body; use communication". The
output canonical key order keeps `interactive` (afm contract stable).

When a step body has
**no usable `roles` value** (the `roles:` key is absent, explicitly `null`,
or set to an empty list `[]`), the compiler injects a SINGLE default field
into the assembled `FlowStage.fields` of the compiled afm flow-file:

- `agents: [auto]`

`auto` is a **sentinel agent mode**: goga emits the literal string `auto`
verbatim and does NOT interpret it — the actual agent selection is performed on
the afm side. `supervisor` and `supervisor_prompt` are NO LONGER
default-injected; they remain valid authored fields that pass through to their
canonical slots when the source step body carries them.

This default is an **output-side** concern — it lives only in the compiled
`FlowDocument.stages`, never in the `PipelineDocument.body` returned to
consumers (which stays a faithful mirror of the source pipeline-file).

An **authored non-empty `roles` value** (any list with at least one entry)
always wins and disables injection entirely — the compiler does not second-guess
the user's choice of roles. Authored `roles` values are translated
entry-by-entry into the output `agents` values via `translate_role`
(planner/executor/reviewer → planning/implementation/review; every other value
verbatim). The injection runs uniformly on both the non-workflow path and the
workflow path (after per-stage overrides and loop-expansion), so
workflow-applied command/description overrides coexist with the injected
default in the same stage without collision.

The canonical per-stage key order is unchanged (`supervisor` /
`supervisor_prompt` retain their slots between `agents` and `skills`, but appear
only when authored):

```
interactive, command, prompt, description, agents, [supervisor, supervisor_prompt,] skills, …
```

Example — source pipeline-file stage without `roles`:

```yaml
- name: deploy
  title: Deploy
  prompt: Run deployment
```

Compiled flow-file stage (default injected):

```yaml
- id: deploy
  name: Deploy
  agents: [auto]
  prompt: |
    Run deployment
```

## Side Effects

`compile_flow` reads from `pipeline_path` and writes to `flow_path`. No other
I/O. No subprocess calls. No environment variable reads — the caller supplies
both paths explicitly, and the workflow as a value.

If `flow_path` already exists, it is overwritten.

## Preconditions

- `pipeline_path` must be an existing file readable by the current process.
- `flow_path.parent` must already exist and be writable. The caller is
  responsible for creating the output directory before invoking
  `compile_flow`.
- The input pipeline-file must contain a `---` separator line. Files without
  the separator (e.g. a ready-made afm flow-file) are not supported and will
  raise "missing body separator".
- When `workflow` is passed, it must be a valid `WorkflowDocument` obtained
  from `parse_workflow`. Structural errors from `parse_workflow` propagate
  before `compile_flow` is invoked, unless the consumer intercepts them.

## Errors

| Condition                                       | Exception                                 |
|-------------------------------------------------|-------------------------------------------|
| `pipeline_path` does not exist or is unreadable | `FileNotFoundError` / `PermissionError` (propagated) |
| `---` separator missing                         | structural error "missing body separator" |
| Header missing `name` or `description`          | structural error "header missing name/description" |
| Legacy `agents` key in header                   | structural error "agents key is forbidden in header; use roles" |
| Legacy `agents` key in a stage body             | structural error "agents key is forbidden in stage body; use roles" |
| Unknown key in header `roles` block (incl. `summary`) | structural error "unknown role in header.roles: <key>; valid keys: planner, executor, reviewer" |
| Non-str value in header `roles.<key>`           | structural error "non-str value in header.roles.<key>" |
| Body shape is neither list nor dict             | structural error "unsupported body format" |
| Body has zero steps                             | structural error "empty body"             |
| Unknown name in `workflow.stages`               | structural error "unknown stage name in workflow.stages: <name>" |
| Dangling `extend.<name>.before`/`.after` ref    | structural error "unknown stage name in workflow.extend.<name>.before/.after: <ref>" |
| All stages skipped — reconstructed body empty   | structural error "empty body"             |
| `flow_path.parent` does not exist               | `FileNotFoundError` (propagated)          |

Unknown stage names in `workflow.stages` (names not matching any step in the
body or any extend-stage) are NOW a structural error (formerly a warning+skip).
Dangling `extend.<name>.before`/`.after` refs (naming no step and no
extend-stage) are likewise NOW a structural error (formerly a warning+skip /
verbatim pass-through).

## Anti-patterns

- Do not expect an unknown `workflow.stages` name to be silently skipped
  anymore — strict validation now raises a structural error. Split or prune
  workflows that intentionally reference names absent from the target pipeline.
- Do not expect a dangling `extend.<name>.before`/`.after` ref to be silently
  skipped anymore — strict validation now raises a structural error (symmetric
  with `workflow.stages`). A ref to an existing stage also marked `skip: true`
  is NOT flagged (validation runs before removal).
- Do not expect `compile_flow` to leave dangling `depends_on` after a skip —
  dependents are transparently reconnected to the skipped stage's predecessors.
- Do not pass a relative path — both paths must be absolute.
- Do not expect `compile_flow` to create `flow_path.parent`. Create the
  directory before calling.
- Do not pass an already-afm-format file (one with a top-level `stages:` key
  and no `---` separator). Only goga DSL files are supported.
- Do not call `compile_flow` from the host side. It is designed to run inside
  the goga container where `AFM_DIR` is mounted; the caller resolves the
  output path from `AFM_DIR` and passes it explicitly.
- Do not expect the output to differ between two calls with the same input —
  the compiler is deterministic and idempotent.
- Do not re-invoke `parse_dsl` to obtain `header.roles` — read
  `PipelineDocument.header.roles` from this routine's return value.
- Do not expect inline prompt overrides to appear in the `FlowDocument` — they
  are carried only by `PipelineDocument`; the afm flow-file is unaffected.
- Do not expect the `PipelineDocument.body` to reflect the workflow-reconstructed
  stages — the body remains the ORIGINAL parsed body; workflow-affected stages
  live only in `FlowDocument.stages`.
- Do not call `compile_flow` from the host with a workflow-file path — parse
  the workflow in-container via `parse_workflow` and pass the resulting
  `WorkflowDocument`. The host does no workflow-file I/O except the early
  existence validation.
- Do not expect `compile_flow` to call any host-side wrapper resolver for the
  `agent → command` composition — the cell composes the wrapper path
  in-container inline.
- Do not pass the `PipelineDocument.body` to a consumer as the source of truth
  for workflow-modified stages — only `FlowDocument.stages` reflects the
  workflow.
- Do not expect `compile_flow` to embed extend-stages after loop-expansion —
  embedding (step 0) precedes overrides, loop-expansion, and reference
  rewriting, which then apply to extend-stages uniformly.
- Do not expect an extend-entry's inline `agent` / `loop` to appear in the
  compiled stage as a field — they are override defaults, consumed into
  `command` / loop-expansion (and a `stages`-block entry for the same name
  wins per field).
- Do not expect `supervisor` / `supervisor_prompt` to appear by default — they
  are authored-only now; the default `agents` value injected into a stage
  without an authored `roles` value is `[auto]`.
- Do not read `AFM_DIR`, `Path.cwd()`, or any environment variable inside
  `compile_flow` to derive `root_dir` — the compiler is contractually a pure
  transformer with no env reads. The caller supplies the value explicitly via
  the `root_dir` parameter; in the standard in-container pipeline this is
  `run_pipeline` resolving `Path.cwd()` and forwarding it.
