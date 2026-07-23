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
    prompt="Example top-level prompt",  # optional; None omits the key
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

- `doc: FlowDocument` — the document to serialize. The `prompt` of each
  `FlowDocument` may be `None` (the key is omitted from output) or a `str`
  (emitted as the FIRST top-level key, in block-literal scalar style). The
  `root_dir` of each `FlowDocument` may be `None` (the key is omitted from
  output) or a `str` (emitted as the SECOND top-level key — after `prompt`
  when present, before `name` — as a plain scalar). The `fields` of each
  `FlowStage` must already be in canonical key order (`interactive`,
  `command`, `prompt`, `description`, `agents`, `supervisor`,
  `supervisor_prompt`, `skills`, then alphabetically-sorted extra keys) —
  `serialize_flow` does not reorder. Use `compile_flow` to build a
  correctly-ordered document from a pipeline-file.

## Return value

A `str` containing the YAML representation, byte-exact with the canonical
`flow.yml` format for equivalent content. When `doc.prompt` is `None`, the
output omits the `prompt` key entirely. When `doc.root_dir` is `None`, the
output omits the `root_dir` key entirely.

## Side Effects

`serialize_flow` performs no file I/O. It takes a `FlowDocument` and returns
a string. Pure (modulo exceptions).

## Preconditions

- The input `FlowDocument` must be well-formed — `fields` dicts in canonical
  order (extended to include `command` and `description`), `depends_on` is
  `None` or a list of strings, `prompt` is `None` or `str`.

## Anti-patterns

- Do not skip the canonical ordering of `FlowStage.fields` before calling
  `serialize_flow`. The serializer does not reorder; out-of-order keys
  produce out-of-order output.
- Do not validate `depends_on` references through this routine. Dangling ids,
  cycles, and duplicates are afm's responsibility.
- For the common end-to-end case, prefer `compile_flow` — it composes
  `parse_dsl` and `serialize_flow` correctly and applies the per-format
  `depends_on` rules.
- Do not expect `prompt=None` to emit an empty `prompt:` key — it omits the
  key entirely (backwards-compat behavior).
