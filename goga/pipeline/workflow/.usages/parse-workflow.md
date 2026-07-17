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
    print(f"{stage_name}: agent={stage.agent}, loop={stage.loop}")
```

## Parameters

- `workflow_path: Path` — absolute path to the workflow-file. The file must
  be a YAML document whose root is a mapping containing up to two optional
  keys: `prompt` (a string) and `stages` (a mapping of stage-name to override
  object).

## Return value

A `WorkflowDocument` with two fields:

- `prompt: str | None` — top-level prompt text, or `None` when the file has no `prompt:`
- `stages: dict[str, WorkflowStage]` — map of per-stage overrides keyed by
  stage name; an empty map when the file has no `stages:`

Each `WorkflowStage` exposes:

- `agent: str | None` — agent name (e.g. `"codex"`), or `None`
- `prompt: str | None` — per-stage prompt text, or `None`
- `loop: int | None` — positive iteration count (>= 1), or `None` (no expansion)

## Side Effects

`parse_workflow` reads one file path and returns an in-memory object. No other
I/O, no network calls, no subprocesses. Pure (modulo exceptions).

## Preconditions

- `workflow_path` must point to an existing readable file.
- The file must be a valid YAML document with a mapping root.
- Top-level allowed keys: `prompt`, `stages`. Any other top-level key raises
  a structural error.
- Per-stage allowed keys: `agent`, `prompt`, `loop`. Any other stage key
  raises a structural error.
- `loop` must be `int >= 1`. Zero, negative values, and non-int types raise a
  structural error.

## Errors

| Condition | Exception |
|-----------|-----------|
| `workflow_path` does not exist or is unreadable | `FileNotFoundError` / `PermissionError` (propagated) |
| Invalid YAML | structural error "invalid YAML in workflow-file" |
| YAML root is not a mapping | structural error "workflow must be a mapping" |
| Top-level key not in {prompt, stages} | structural error "unknown key in workflow: <key>; valid keys: prompt, stages" |
| `prompt` is not a `str` | structural error "non-str value in workflow.prompt" |
| `stages` is not a `dict` | structural error "non-mapping stages block in workflow" |
| Stage entry is not a `dict` | structural error "non-mapping stage '<name>' in workflow.stages" |
| Stage key not in {agent, prompt, loop} | structural error "unknown key in workflow.stages.<name>: <key>; valid keys: agent, prompt, loop" |
| `agent` is not a `str` | structural error "non-str value in workflow.stages.<name>.agent" |
| Stage `prompt` is not a `str` | structural error "non-str value in workflow.stages.<name>.prompt" |
| `loop` is not an `int` | structural error "non-int value in workflow.stages.<name>.loop" |
| `loop < 1` | structural error "loop must be >= 1 in workflow.stages.<name>" |
| Both `prompt` absent and no stage entries | structural error "empty workflow — provide at least prompt or one stage" |

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
  propose-review:
    loop: 2
    agent: claude
```

All three per-stage fields (`agent`, `prompt`, `loop`) are optional. The `stages`
section may be absent entirely. The top-level `prompt` may also be absent — but
a workflow providing neither is rejected.

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
- Do not call `parse_workflow` on the host. The workflow-file is read and
  parsed inside the goga container
  (`/workspace/.goga/workflows/<name>.yml`); the host performs only the
  early file-existence validation for the explicit `--workflow` CLI flag,
  and all actual file I/O and parsing happens in-container.
