# Parse DSL — goga/pipeline/compiler

## Overview

`parse_dsl` is the parsing half of the compilation pipeline, exposed
separately for advanced consumers. Use it when you need access to the
intermediate representation — e.g. to inspect the parsed DSL before
compilation, to apply custom transformations between parsing and
serialization, or to detect the body format programmatically. For the
common end-to-end case, prefer `compile_flow`.

## Usage

```python
from pathlib import Path
from goga.pipeline.compiler import parse_dsl

text = Path("/workspace/.goga/pipelines/feature-phases.yml").read_text()
header, fmt, body = parse_dsl(text)

print(header.name)  # "Goga feature"
print(header.description)  # "Feature implementation"
print(fmt)  # BodyFormat.PHASES or BodyFormat.STAGES
if header.roles is not None:
    print(header.roles.planner)  # inline override or None
for step in body.steps:
    print(step.name, step.title)
```

## Parameters

- `text: str` — the full pipeline-file text (including the `---` separator
  and both segments).

## Return value

A 3-tuple:

- `header: PipelineHeader` — the parsed header (`name`, `description`,
  optional `roles: PipelineRoles | None`). `roles` is set to `None` when
  the header segment has no `roles:` block or an empty `roles:` mapping;
  otherwise it is a `PipelineRoles` instance whose three fixed-key fields
  (`planner`, `executor`, `reviewer`) carry inline prompt overrides or
  `None`.
- `fmt: BodyFormat` — the detected body format (`PHASES` for a list body,
  `STAGES` for a dict body).
- `body: PhasesBody | StagesBody` — the parsed body. Type matches `fmt`:
  `PhasesBody` when `fmt == BodyFormat.PHASES`, `StagesBody` otherwise.

## Side Effects

`parse_dsl` performs no file I/O. It takes a string and returns in-memory
objects. Pure (modulo exceptions).

## Preconditions

- The input must contain a `---` separator line. Files without it
  (already-afm format) raise "missing body separator".

## Errors

| Condition                                       | Exception                                 |
|-------------------------------------------------|-------------------------------------------|
| `---` separator missing                         | structural error "missing body separator" |
| Header missing `name` or `description`          | structural error "header missing name/description" |
| Legacy `agents` key in header                    | structural error "agents key is forbidden in header; use roles" |
| Unknown key in header `roles` block (incl. `summary`) | structural error "unknown role in header.roles: <key>; valid keys: planner, executor, reviewer" |
| Non-str value in header `roles.<key>`            | structural error "non-str value in header.roles.<key>" |
| Body shape is neither list nor dict             | structural error "unsupported body format" |

`parse_dsl` does NOT raise on empty body — that check lives in `compile_flow`.
An absent `roles` block and an empty `roles:` mapping are both represented
as `roles = None` (no structural error). The legacy `agents` key in the
header is a structural error (never represented as None).

## Anti-patterns

- Do not expect `parse_dsl` to apply `depends_on` rules. The body it returns
  preserves source `depends_on` (or its absence) verbatim — the compiler
  applies position-based rules in `compile_flow`.
- Do not validate `depends_on` references through this routine. Dangling ids,
  cycles, and duplicates are afm's responsibility.
- Do not mutate the returned `PipelineHeader` or `PipelineRoles` — consumers
  treat them as read-only.
- `interactive` is NOT a header field, and parse_dsl does NOT touch it — it is
  an open-ended stage-body field carried verbatim in the body. The
  `communication` → `interactive` translation happens in `compile_flow`, not
  here.
- For the common end-to-end case, prefer `compile_flow` — it composes
  `parse_dsl` and `serialize_flow` correctly and applies the per-format
  `depends_on` rules.
