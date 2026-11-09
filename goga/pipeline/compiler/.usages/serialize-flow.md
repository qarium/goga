# serialize_flow — FlowDocument → canonical afm flow-file YAML

`serialize_flow` serializes a `FlowDocument` to byte-exact canonical afm flow-file
YAML using `beautiful_yaml` plus a custom SafeDumper (canonical key order,
flow-style agents, block-style skills/depends_on/top-level prompt).

## Canonical per-stage key order

interactive, auto_approve, auto_run, command, prompt, description, buttons, agents,
supervisor, supervisor_prompt, skills, script_before, script, script_after,
script_timeout, reflect, memory_use, assistants, verify, <unknown A-Z>.

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
- reflect: a block-style mapping of plain scalars (file, mode)
- memory_use: a plain bool scalar
- collaboration block: a block-style mapping, key order mode, max_depth;
  plain scalars; a None max_depth omitted entirely
- team list: a block-style list; each member a block-style mapping, key
  order id, title, profile, instruction, skills; instruction a plain
  scalar when single-line and a block-literal scalar when multi-line (the
  script-family pattern); skills a block-style list, written explicitly
  when empty
- stage assistants: a block-style list of mappings; each entry a
  block-style mapping, key order profile, title, instruction, mode,
  trigger; instruction follows the script-family pattern; mode and
  trigger plain scalars; NO skills key — the engine strict-parses
  stage entries and rejects unknown fields (skills travel only on a
  team member entry, and the team draws from the catalog alone)
- repeat: the scalar `true` when the directive carries no authored key;
  otherwise a block-style mapping, key order max_cycles, keep_runs; plain
  scalars; present keys only
- empty list values (e.g. explicit empty depends_on) written explicitly

## Stage `verify` emission

- List form (no authored settings): the verify value IS the steps list.
- Container form (any authored setting): a block mapping — `steps` first,
  then the authored settings in the fixed order `max_failures`,
  `review_patience`, `fresh_correction` (present keys only, plain scalars).
- Each step: key order `name`, `run`|`command`, `timeout`, `prompt`;
  single-line values as plain scalars, multi-line as block-literal
  (script-family pattern).
- A stage without a gate carries no `verify` key — byte-identical output
  for gate-free workflows.

## Key presence

Stages without auto_approve / auto_run / buttons / script_before / script /
script_after / script_timeout / reflect / memory_use / assistants serialize
without those keys — each appears only when its source directive is present.
`auto_run` appears only for a manual-effective stage, always as
`auto_run: false`. `buttons` appears only when the workflow supplied a
non-empty notes instruction for the stage. Stage `assistants` appear only
when the stage carries at least one effective attachment.

A flow document without memory participation serializes without the top-level
`memory` block and without any memory stage key — byte-identical output for
memory-free workflows. When present, the block sits between `description` and
`stages` with the key order path, mode, memory_use, max_rules, commit (a None
field omitted entirely).

The `collaboration` block is always present (mode at minimum) — it sits
between `memory` (when present) and `team`. The `team` list is omitted
entirely when empty. A flow document without a team and without stage
attachments serializes without those keys — byte-identical output except
the always-present collaboration mode key.

A flow document without a `repeat` directive (a non-repeatable pipeline)
serializes without the key — byte-identical output. When present, it sits
between `description` and `memory`, ahead of the `memory` block.
