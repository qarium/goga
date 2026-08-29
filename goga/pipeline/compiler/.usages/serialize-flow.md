# serialize_flow — FlowDocument → canonical afm flow-file YAML

`serialize_flow` serializes a `FlowDocument` to byte-exact canonical afm flow-file
YAML using `beautiful_yaml` plus a custom SafeDumper (canonical key order,
flow-style agents, block-style skills/depends_on/top-level prompt).

## Canonical per-stage key order

interactive, auto_approve, auto_run, command, prompt, description, buttons, agents,
supervisor, supervisor_prompt, skills, script_before, script, script_after,
script_timeout, <unknown A-Z>.

The serializer does NOT reorder — canonical order is fixed at `FlowStage`
assembly (`compile_flow`); `serialize_flow` iterates `fields` as-is.

## Style rules

- agents: flow-style
- skills, depends_on, top-level prompt: block-style
- auto_approve, auto_run: plain bool scalars
- buttons: a block-style mapping; each value — a plain scalar when single-line,
  a block-literal scalar when multi-line (the script-family pattern)
- script_before/script/script_after: plain scalars when single-line;
  block-literal scalars when multi-line
- script_timeout: plain scalar when single-line; block-literal scalar when
  multi-line (the script-family pattern)
- empty list values (e.g. explicit empty depends_on) written explicitly

## Key presence

Stages without auto_approve / auto_run / buttons / script_before / script /
script_after / script_timeout serialize without those keys — each appears only
when its source directive is present. `auto_run` appears only for a
manual-effective stage, always as `auto_run: false`. `buttons` appears only when
the workflow supplied a non-empty notes instruction for the stage.
