# assistants — authoring collaboration in the workflow-file

`assistants` enables a workflow's collaboration with helper agents: a
top-level catalog of run-level assistants, a delegation-bounds block, and
per-stage attachments. The document addresses workflow-file authors:
everything described here is validated structurally at parse time — typos
and type or value mismatches are rejected with a readable error naming the
workflow location.

## The top-level `assistants:` catalog

Each entry is a named assistant present from run start and reachable by
name for the whole run:

| Key | Type | Default | Note |
|-----|------|---------|------|
| `name` | str | required | `[A-Za-z0-9._-]`; `assistant` is reserved; unique across the catalog and every inline declaration |
| `prompt` | str | — | the assistant's instruction |
| `skills` | list[str] | — | the assistant's own skills |
| `agent` | str | global agent | a goga agent name; resolved implicitly at delivery |
| `delegate` | bool | `false` | permission to create child tasks |
| `env` | map[str]str | — | delivered through a generated closure |

At least one of `prompt` or `skills` is required. `gate` and `when` are
attachment parameters — authoring either in the catalog is a structural
error.

## The top-level `delegation:` block

| Key | Type | Default | Note |
|-----|------|---------|------|
| `depth` | int >= 0 | not authored | maximum delegation depth; 0 forbids helper creation |
| `max_tasks` | int >= 1 | `50` (materialized) | whole-run helper task budget |

Both keys are optional; an empty block is valid and materializes
`max_tasks: 50`. A workflow consisting of the block alone is valid.

## Stage attachments (`stages.<name>.assistants`)

Three entry forms:

```yaml
stages:
  build:
    assistants:
      - reviewer                      # 1) bare name — catalog reference
      - name: reviewer                # 2) reference with overrides
        gate: true
        when: finish
      - name: security                # 3) full inline declaration
        agent: codex
        prompt: Audit the diff.
        when: checkpoints
```

| Attachment key | Type | Default | Note |
|------------|------|---------|------|
| `name` | str | required | identifies the assistant |
| `gate` | bool | `false` | `true` — the verdict must pass before the stage finishes |
| `when` | `start` \| `checkpoints` \| `finish` | `checkpoints` | when the assistant engages |

A map entry carrying any key beyond `name`/`gate`/`when` is a full inline
declaration — it accepts the catalog field set plus `gate`/`when` and
requires at least one of `prompt` or `skills`. A map carrying only
`name`/`gate`/`when` is a reference: the agent, prompt, skills, delegate
permission, and env come from the catalog entry; only `gate` and `when`
may be overridden.

Attachments are valid only under `stages.<name>` — never inside an
extend-entry (the attachments of a new stage are authored in the stages
block by the new stage's name). An empty list equals absence.

## Minimal examples

Catalog with attachments and bounds:

```yaml
assistants:
  - name: reviewer
    agent: claude
    delegate: true
    skills:
      - code-audit
    prompt: |
      Review the stage changes and report concrete findings.
delegation:
  depth: 3
  max_tasks: 50
stages:
  build:
    assistants:
      - name: reviewer
        gate: true
        when: finish
```

Attachments only (every entry a full inline declaration):

```yaml
stages:
  build:
    assistants:
      - name: security
        prompt: Audit the diff.
```

## Structural errors (complete list)

| Authoring | Error |
|---|---|
| `assistants:` non-list | non-list assistants block in workflow |
| catalog entry non-mapping | non-mapping assistant entry in workflow.assistants |
| unknown catalog key (incl. `gate`/`when`) | unknown key in workflow.assistants.NAME: KEY; valid keys: name, prompt, skills, agent, delegate, env |
| missing `name` | name is required in workflow.assistants entry |
| no `prompt` and no `skills` | assistant NAME requires at least one of prompt or skills |
| `delegation:` non-mapping | non-mapping delegation block in workflow |
| unknown `delegation:` key | unknown key in workflow.delegation: KEY; valid keys: depth, max_tasks |
| `depth` not int / < 0 | a structural error |
| `max_tasks` not int / < 1 | a structural error |
| `stages.<name>.assistants` non-list | non-list assistants in workflow.stages.NAME |
| invalid `when` value | a structural error listing the permitted values |
| name outside `[A-Za-z0-9._-]` | a structural error naming the entry |
| the name `assistant` | assistant name is reserved |
| duplicate declaration name | duplicate assistant name: NAME |
| `assistants` in an extend-entry | assistants is forbidden in workflow.extend.NAME |

Compilation-time errors (raised by the compiler, not the parser): an
unknown assistant reference; an attachment on a script-only or
planning-only stage; the same assistant attached twice to one stage.

## Anti-patterns

- Do not author `gate`/`when` in the catalog — they are attachment
  parameters.
- Do not author `assistants` inside an extend-entry — the attachments of a
  new stage are authored in the stages block by its name.
- Do not rely on engine defaults: `when`, `gate`, `delegate`, and
  `max_tasks` are materialized by the parser, not silently inherited.
- Do not expect the parser to resolve references — a name that matches no
  catalog entry and no inline declaration of the effective document is a
  compilation error, so a contributor may add catalog entries a workflow
  references.
