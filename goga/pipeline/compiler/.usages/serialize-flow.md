# Serialize Flow — goga/pipeline/compiler

## Overview

`serialize_flow` is the serialization half of the compilation pipeline,
exposed separately for advanced consumers. Use it when you need to render a
`FlowDocument` built by other means (e.g. constructed manually or transformed
after parsing) into the canonical afm flow-file format. For the common
end-to-end case, prefer `compile_flow`.

## Usage

```python
from pathlib import Path
from goga.pipeline.compiler import serialize_flow, FlowDocument, FlowStage

doc = FlowDocument(
    name="My flow",
    description="Custom flow",
    stages=[
        FlowStage(
            id="step-a",
            name="Step A",
            depends_on=None,
            fields={"interactive": True, "agents": ["planning"]},
        ),
    ],
)

text = serialize_flow(doc)
Path("/tmp/out.yml").write_text(text)
```

## Parameters

- `doc: FlowDocument` — the document to serialize. The `fields` of each
  `FlowStage` must already be in canonical key order (`interactive`, `prompt`,
  `agents`, `skills`, then alphabetically-sorted extra keys) — `serialize_flow`
  does not reorder. Use `compile_flow` to build a correctly-ordered document
  from a pipeline-file.

## Return value

A `str` containing the YAML representation, byte-exact with the canonical
`flow.yml` format for equivalent content.

## Side Effects

`serialize_flow` performs no file I/O. It takes a `FlowDocument` and returns
a string. Pure (modulo exceptions).

## Preconditions

- The input `FlowDocument` must be well-formed — `fields` dicts in canonical
  order, `depends_on` is `None` or a list of strings.

## Anti-patterns

- Do not skip the canonical ordering of `FlowStage.fields` before calling
  `serialize_flow`. The serializer does not reorder; out-of-order keys
  produce out-of-order output.
- Do not validate `depends_on` references through this routine. Dangling ids,
  cycles, and duplicates are afm's responsibility.
- For the common end-to-end case, prefer `compile_flow` — it composes
  `parse_dsl` and `serialize_flow` correctly and applies the per-format
  `depends_on` rules.
