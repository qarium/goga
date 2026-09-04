# memory — authoring memory in the workflow-file

`memory` enables a workflow's participation in the project memory: one
top-level configuration block and two per-stage participation instructions.
The document addresses workflow-file authors: everything described here is
validated structurally at parse time — typos and type or value mismatches
are rejected with a readable error.

## The top-level `memory:` block

| Key | Type | Default | Note |
|-----|------|---------|------|
| `method` | `reflect` \| `alignment` | `reflect` | selector of the instruction vocabulary; the selector is goga-side and never reaches the compiled output |
| `path` | str | no suffix | suffix inside the fixed root of the project memory |
| `max_rules` | int >= 1 | `25` | materialized — cannot be silently omitted |
| `commit` | bool | `false` | materialized |
| `mode` | `r` \| `w` \| `rw` | `rw` (materialized) | only with `method: alignment`; with `method: reflect` — a structural error |

An unknown key is a structural error. A workflow consisting of the `memory:`
block alone is valid (not counted as empty).

## Instructions of the `stages` block

| Instruction | Permitted method | Value |
|------------|------------------|-------|
| `reflect: {file, mode?}` | `reflect` | `file` is required — the stage's reflection file (a path shape inside the memory root: no leading `/`, not absolute, no `..`); `mode` is optional (`r`/`w`/`rw`), the `rw` default is materialized |
| `memory: <bool>` | `alignment` | `true` — the stage participates; `false` equals the key's absence |

A method/instruction mismatch is a structural error: `reflect` is permitted
only under the reflect method, `memory` — only under the alignment method.
The default method is `reflect`, so a `memory` instruction without a
`memory:` block carrying an explicit `method: alignment` is an error.

Both instructions are forbidden in an extend-entry: the participation of a
new stage is authored in the `stages` block by its name.

## Minimal examples

Reflect method (the default) — stages reflecting into a shared memory file:

```yaml
memory:
  max_rules: 40
stages:
  brainstorm:
    reflect:
      file: shared.md
  review:
    reflect:
      file: shared.md
      mode: r
```

Alignment method — selective stage participation:

```yaml
memory:
  method: alignment
  path: goga-development
  mode: rw
stages:
  brainstorm:
    memory: true
  build:
    memory: true
```

A block without instructions is a valid configuration (a silent no-op at
compilation).

## Structural errors (complete list)

| Authoring | Error |
|---|---|
| `memory:` non-mapping | non-mapping memory block in workflow |
| unknown `memory:` key | unknown key in workflow.memory: KEY; valid keys: method, path, max_rules, commit, mode |
| `method` outside {reflect, alignment} | a structural error listing the permitted values |
| `max_rules` not int / < 1 | a structural error |
| `commit`/`memory` not bool | a structural error |
| `mode` outside {r, w, rw} | a structural error listing the permitted values |
| `mode` with `method: reflect` | mode is forbidden in workflow.memory with method: reflect |
| `path`/`reflect.file` of bad shape | a structural error (empty string, leading `/`, absolute path, `..`) |
| `reflect` non-mapping | non-mapping reflect in workflow.stages.NAME |
| unknown `reflect` key | unknown key in workflow.stages.NAME.reflect: KEY; valid keys: file, mode |
| `reflect` without `file` | a structural error |
| `reflect` under alignment | reflect is forbidden in workflow.stages.NAME with method: alignment |
| `memory` under reflect | memory is forbidden in workflow.stages.NAME with method: reflect |
| `reflect`/`memory` in an extend-entry | reflect/memory is forbidden in workflow.extend.NAME |

## Anti-patterns

- Do not author `reflect`/`memory` in a stage body or in an extend-entry
  body — the single authoring point of the instructions is the `stages`
  block of the workflow-file (keys in stage bodies are rejected at
  compilation).
- Do not rely on afm defaults: the materialization of the defaults (`mode`,
  `max_rules`, `commit`) is mandatory parser behavior, not a style choice.
- Do not set `mode` in the `memory:` block under the default method — that
  is a structural error, not a silent ignore.
