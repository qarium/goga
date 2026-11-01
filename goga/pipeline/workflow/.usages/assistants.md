# assistants — authoring collaboration in the workflow-file

`assistants` enables a workflow's collaboration with helper agents: a
top-level catalog of run-level assistants, a delegation-bounds block, and
per-stage attachments. The document addresses workflow-file authors:
everything described here is validated structurally at parse time — typos
and type or value mismatches are rejected with a readable error naming the
workflow location.

Both assistants surfaces are name-keyed maps: the entry key IS the assistant
name, and an entry value never repeats it.

## The top-level `assistants:` catalog

Each key is an assistant name; each value declares an assistant present from
run start and reachable by name for the whole run:

| Value key | Type | Default | Note |
|-----------|------|---------|------|
| `prompt` | str | — | the assistant's instruction |
| `skills` | list[str] | — | the assistant's own skills |
| `agent` | str | global agent | a goga agent name; resolved implicitly at delivery |
| `delegate` | bool | `false` | permission to create child tasks |
| `env` | map[str,str] | — | delivered through a generated closure |

At least one of `prompt` or `skills` is required per entry. The entry key is
the assistant name: it matches `[A-Za-z0-9._-]`, `assistant` is reserved,
and it is unique across the catalog and every inline declaration. `name`,
`gate`, and `when` never appear in a catalog entry value — `name` is the key
itself, and `gate`/`when` are attachment parameters.

## The top-level `delegation:` block

| Key | Type | Default | Note |
|-----|------|---------|------|
| `depth` | int >= 0 | not authored | maximum delegation depth; 0 forbids helper creation |
| `max_tasks` | int >= 1 | `50` (materialized) | whole-run helper task budget |

Both keys are optional; an empty block is valid and materializes
`max_tasks: 50`. A workflow consisting of the block alone is valid.

## Stage attachments (`stages.<name>.assistants`)

A name-keyed map: each key is an assistant name, each value carries the
attachment parameters. A compiling example — every referenced name is
declared, and no name repeats within one stage:

```yaml
assistants:
  reviewer:
    prompt: Review the stage changes.
  auditor:
    prompt: Audit the stage changes.
stages:
  build:
    assistants:
      reviewer:
        when: finish          # 1) reference — declaration comes from the catalog
      auditor:
        gate: true            # 2) reference with the gate override
        when: finish
      security:               # 3) full inline declaration
        agent: codex
        prompt: Audit the diff.
        when: checkpoints
```

| Attachment key | Type | Default | Note |
|------------|------|---------|------|
| `when` | `start` \| `checkpoints` \| `finish` | **required** | when the assistant engages |
| `gate` | bool | `false` | `true` — the verdict must pass before the stage finishes |

`when` is required on every attachment — the entry names the assistant, so
its engagement timing is authored explicitly. `gate` is optional.

A value carrying any key beyond `gate`/`when` is a full inline declaration —
it accepts the catalog field set plus `gate`/`when` and requires at least one
of `prompt` or `skills`. A value carrying only `gate`/`when` is a reference:
the agent, prompt, skills, delegate permission, and env come from the
catalog entry; only `gate` and `when` are the attachment's own.

Attachments are valid only under `stages.<name>` — never inside an
extend-entry (the attachments of a new stage are authored in the stages
block by the new stage's name). An empty map equals absence.

## Minimal examples

Catalog with attachments and bounds:

```yaml
assistants:
  reviewer:
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
      reviewer:
        gate: true
        when: finish
```

Attachments only (every entry a full inline declaration):

```yaml
stages:
  build:
    assistants:
      security:
        prompt: Audit the diff.
        when: start
```

## Structural errors (complete list)

| Authoring | Error |
|---|---|
| `assistants:` non-mapping (a list, a string, a scalar) | non-mapping assistants block in workflow; author the map form keyed by assistant name |
| catalog entry value non-mapping | non-mapping assistant entry in workflow.assistants.NAME |
| unknown catalog key (incl. `name`, `gate`, `when`) | unknown key in workflow.assistants.NAME: KEY; valid keys: prompt, skills, agent, delegate, env |
| no `prompt` and no `skills` | assistant NAME requires at least one of prompt or skills |
| `delegation:` non-mapping | non-mapping delegation block in workflow |
| unknown `delegation:` key | unknown key in workflow.delegation: KEY; valid keys: depth, max_tasks |
| `depth` not int / < 0 | a structural error |
| `max_tasks` not int / < 1 | a structural error |
| `stages.<name>.assistants` non-mapping (a list, a string, a scalar) | non-mapping assistants in workflow.stages.NAME; author the map form keyed by assistant name |
| attachment value non-mapping | non-mapping assistant attachment in workflow.stages.NAME.ASSISTANT |
| missing `when` | when is required in workflow.stages.NAME.assistants.ASSISTANT |
| unknown attachment key | unknown key in workflow.stages.NAME.assistants.ASSISTANT: KEY; valid keys: prompt, skills, agent, delegate, env, gate, when |
| invalid `when` value | a structural error listing the permitted values |
| name outside `[A-Za-z0-9._-]` | a structural error naming the entry |
| the name `assistant` | assistant name is reserved |
| duplicate declaration name | duplicate assistant name: NAME |
| `assistants` in an extend-entry | assistants is forbidden in workflow.extend.NAME |

Compilation-time errors (raised by the compiler, not the parser): an
unknown assistant reference; an attachment on a script-only or
planning-only stage; the same assistant attached twice to one stage by a
programmatic contribution.

## Anti-patterns

- Do not author `name` inside an entry — the map key IS the assistant name.
- Do not author `gate`/`when` in the catalog — they are attachment
  parameters.
- Do not omit `when` on a stage attachment — the engagement timing is always
  authored.
- Do not author `assistants` inside an extend-entry — the attachments of a
  new stage are authored in the stages block by its name.
- Do not rely on engine defaults: `gate`, `delegate`, and `max_tasks` are
  materialized by the parser, not silently inherited; `when` is authored on
  every attachment and the compiled engagement value is always written
  explicitly.
- Do not expect the parser to resolve references — a name that matches no
  catalog entry and no inline declaration of the effective document is a
  compilation error, so a contributor may add catalog entries a workflow
  references.
