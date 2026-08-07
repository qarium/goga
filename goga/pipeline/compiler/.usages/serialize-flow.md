# serialize_flow — FlowDocument → canonical afm flow-file YAML

`serialize_flow` serializes a `FlowDocument` to byte-exact canonical afm flow-file
YAML using `beautiful_yaml` plus a custom SafeDumper (canonical key order,
flow-style agents, block-style skills/depends_on/top-level prompt).

## Canonical per-stage key order

interactive, auto_approve, command, prompt, description, agents, supervisor,
supervisor_prompt, skills, script_before, script, script_after, <unknown A-Z>.

The serializer does NOT reorder — canonical order is fixed at `FlowStage`
assembly (`compile_flow`); `serialize_flow` iterates `fields` as-is.

## Style rules

- agents: flow-style
- skills, depends_on, top-level prompt: block-style
- auto_approve: plain bool scalar
- script_before/script/script_after: plain scalars when single-line;
  block-literal scalars when multi-line (forced via a marker class — the
  dumper default renders multi-line strings single-quoted, not block)
- empty list values (e.g. explicit empty depends_on) written explicitly

## Backward compatibility

Flow-files whose stages carry none of the new keys serialize byte-identically to
before — the new keys are simply absent.
