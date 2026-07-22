# Parse Workflow — goga/pipeline/workflow

## Overview

`parse_workflow` is the entry point of the cell: it reads a project workflow-file
`.goga/workflows/<name>.yml`, validates its structure (known keys, field types,
loop bounds), and returns a `WorkflowDocument` carrying declarative instructions
for the compiler. Use this routine when you need to turn a workflow-file path
into a structured object the compiler can consume.

## Usage

```python
from pathlib import Path
from goga.pipeline.workflow import parse_workflow

workflow_path = Path("/workspace/.goga/workflows/feature-phases.yml")
workflow = parse_workflow(workflow_path)

if workflow.prompt is not None:
    print("Top-level prompt:")
    print(workflow.prompt)

for stage_name, stage in workflow.stages.items():
    print(f"{stage_name}: agent={stage.agent}, loop={stage.loop}, skills={stage.skills}")

for name, extend_stage in workflow.extend.items():
    print(f"extend {name}: before={extend_stage.before}, after={extend_stage.after}, "
          f"agent={extend_stage.agent}, loop={extend_stage.loop}")
```

## Parameters

- `workflow_path: Path` — absolute path to the workflow-file. The file must
  be a YAML document whose root is a mapping containing up to three optional
  keys: `prompt` (a string), `stages` (a mapping of stage-name to override
  object), and `extend` (a mapping of stage-name to new-stage extend-entry).

## Return value

A `WorkflowDocument` with three fields:

- `prompt: str | None` — top-level prompt text, or `None` when the file has no `prompt:`
- `stages: dict[str, WorkflowStage]` — map of per-stage overrides keyed by
  stage name; an empty map when the file has no `stages:`
- `extend: dict[str, WorkflowExtendStage]` — map of new-stage extend-instructions
  keyed by stage name; an empty map when the file has no `extend:`. Each
  `WorkflowExtendStage` exposes `before: list[str] | None`,
  `after: list[str] | None`, `agent: str | None`, `loop: int | None`, and
  `body: dict[str, Any]` (the `body` excludes `before` / `after` / `agent` /
  `loop` / `depends_on`).

Each `WorkflowStage` exposes:

- `agent: str | None` — agent name (e.g. `"codex"`), or `None`
- `prompt: str | None` — per-stage prompt text, or `None`
- `loop: int | None` — positive iteration count (>= 1), or `None` (no expansion)
- `skills: list[str] | None` — skill names merged with the pipeline-file
  skills by the compiler, or `None` (no merge)

## Side Effects

`parse_workflow` reads one file path and returns an in-memory object. No other
I/O, no network calls, no subprocesses. Pure (modulo exceptions).

## Preconditions

- `workflow_path` must point to an existing readable file.
- The file must be a valid YAML document with a mapping root.
- Top-level allowed keys: `prompt`, `stages`, `extend`. Any other top-level
  key raises a structural error.
- An extend-entry forbids `depends_on` (structural error), requires at least
  one of `before`/`after`, accepts optional inline `agent` (str) and `loop`
  (int `>= 1`), and `before`/`after` (when present) must be `list[str]`.
- Per-stage allowed keys: `agent`, `prompt`, `loop`, `skills`. Any other
  stage key raises a structural error.
- `loop` (per-stage and inline extend) must be `int >= 1`. Zero, negative
  values, and non-int types raise a structural error.
- `skills` (when present) must be `list[str]`; a non-list-of-str value raises
  a structural error.

## Errors

| Condition | Exception |
|-----------|-----------|
| `workflow_path` does not exist or is unreadable | `FileNotFoundError` / `PermissionError` (propagated) |
| Invalid YAML | structural error "invalid YAML in workflow-file" |
| YAML root is not a mapping | structural error "workflow must be a mapping" |
| Top-level key not in {prompt, stages, extend} | structural error "unknown key in workflow: <key>; valid keys: prompt, stages, extend" |
| `prompt` is not a `str` | structural error "non-str value in workflow.prompt" |
| `stages` is not a `dict` | structural error "non-mapping stages block in workflow" |
| `extend` is not a `dict` | structural error "non-mapping extend block in workflow" |
| Stage entry is not a `dict` | structural error "non-mapping stage '<name>' in workflow.stages" |
| Stage key not in {agent, prompt, loop, skills} | structural error "unknown key in workflow.stages.<name>: <key>; valid keys: agent, prompt, loop, skills" |
| `agent` is not a `str` | structural error "non-str value in workflow.stages.<name>.agent" |
| Stage `prompt` is not a `str` | structural error "non-str value in workflow.stages.<name>.prompt" |
| `loop` is not an `int` | structural error "non-int value in workflow.stages.<name>.loop" |
| `loop < 1` | structural error "loop must be >= 1 in workflow.stages.<name>" |
| `skills` not a `list[str]` | structural error "non-list-of-str skills in workflow.stages.<name>" |
| Extend entry value is not a `dict` | structural error "non-mapping extend entry `<name>` in workflow.extend" |
| Extend entry contains `depends_on` | structural error "depends_on is forbidden in workflow.extend.<name>" |
| `before` not a `list[str]` | structural error "non-list-of-str before in workflow.extend.<name>" |
| `after` not a `list[str]` | structural error "non-list-of-str after in workflow.extend.<name>" |
| Inline extend `agent` is not a `str` | structural error "non-str value in workflow.extend.<name>.agent" |
| Inline extend `loop` is not an `int` | structural error "non-int value in workflow.extend.<name>.loop" |
| Inline extend `loop < 1` | structural error "loop must be >= 1 in workflow.extend.<name>" |
| Neither `before` nor `after` present | structural error "extend entry `<name>` requires at least one of before/after" |
| `prompt` absent, no stage entries, and no extend entries | structural error "empty workflow — provide at least prompt, one stage, or one extend entry" |

## Example workflow-file

Reference workflow for `parse_workflow`:

```yaml
prompt: |
  Example top-level prompt emitted as the first directive of the compiled flow-file

stages:
  propose:
    agent: codex
    prompt: |
      Additional prompt merged into this stage's description channel
    skills:
      - web-search
  propose-review:
    loop: 2
    agent: claude

extend:
  extra-check:
    after: [propose-review]
    title: Extra check
    prompt: |
      Additional verification stage inserted after propose-review
  warmup:
    before: [propose]
    title: Warmup
    agent: codex
    loop: 3
    prompt: |
      Looped warmup stage running on a specific agent (3 copies: warmup-1..3)
```

All four per-stage fields (`agent`, `prompt`, `loop`, `skills`) are optional.
The `stages` section may be absent entirely. The top-level `prompt` may also be
absent. An `extend:` entry carries `before`/`after` (at least one required;
`depends_on` forbidden), optional inline `agent` (str) and `loop` (int `>= 1`)
— extracted into the model, not part of the body — plus any stage body fields
(`title`, `prompt`, `skills`, `roles`, `interactive`, …) passed through
verbatim. A workflow providing none of `prompt`, `stages`, or `extend` is
rejected.

## Anti-patterns

- Do not pass a relative path — `parse_workflow` reads it directly, and a
  relative path depends on the current working directory.
- Do not expect `parse_workflow` to match stage names against any pipeline. The
  stage names in `stages:` are NOT validated against the target pipeline's
  stages — the compiler performs that match during apply and silently ignores
  unknown names with a warning (a workflow may cover multiple pipelines).
- Do not expect `parse_workflow` to expand `loop` cycles. `WorkflowStage.loop`
  is a count; the compiler performs the expansion.
- Do not expect `parse_workflow` to translate `agent` into a wrapper path. The
  agent-name string is passed through to the compiler as-is.
- Do not expect `parse_workflow` to rewrite `depends_on` references. The
  workflow supplies instructions; the compiler rebuilds the pipeline body
  accordingly.
- Do not expect `parse_workflow` to embed extend-stages or derive
  `depends_on` — it returns positioning instructions (`before`/`after`); the
  compiler embeds the stage and derives `depends_on`.
- Do not expect `parse_workflow` to compose the extend-entry `agent` into a
  wrapper path, expand its `loop`, or merge its `skills` — it extracts and
  type-validates these fields; the compiler applies them.
- Do not expect inline `agent` / `loop` of an extend-entry to appear in
  `extend_stage.body` — they are extracted into dedicated model fields and
  never reach the flow-file as stage fields.
- Do not call `parse_workflow` on the host. The workflow-file is read and
  parsed inside the goga container
  (`/workspace/.goga/workflows/<name>.yml`); the host performs only the
  early file-existence validation for the explicit `--workflow` CLI flag,
  and all actual file I/O and parsing happens in-container.
