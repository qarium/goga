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

print(header.name)        # "Goga feature"
print(header.description) # "Feature implementation"
print(fmt)                # BodyFormat.PHASES or BodyFormat.STAGES
for step in body.steps:
    print(step.name, step.description)
```

## Parameters

- `text: str` — the full pipeline-file text (including the `---` separator
  and both segments).

## Return value

A 3-tuple:

- `header: PipelineHeader` — the parsed header (`name`, `description`).
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
| Body shape is neither list nor dict             | structural error "unsupported body format" |

`parse_dsl` does NOT raise on empty body — that check lives in `compile_flow`.

## Anti-patterns

- Do not expect `parse_dsl` to apply `depends_on` rules. The body it returns
  preserves source `depends_on` (or its absence) verbatim — the compiler
  applies position-based rules in `compile_flow`.
- Do not validate `depends_on` references through this routine. Dangling ids,
  cycles, and duplicates are afm's responsibility.
- For the common end-to-end case, prefer `compile_flow` — it composes
  `parse_dsl` and `serialize_flow` correctly and applies the per-format
  `depends_on` rules.
