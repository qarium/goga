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
| `delegate` | bool | not authored | explicit false is an authored opt-out; omitted is inheritable |
| `env` | map[str,str] | — | delivered through a generated closure |

An entry MAY carry neither `prompt` nor `skills` — an override-style
entry that configures delivery fields (`agent`, `delegate`, `env`) and
takes its content from a tool-delivered entry of the same name. The
EFFECTIVE entry must resolve `prompt` or `skills` — enforced at
compilation with an error naming the assistant and its authoring site;
an override naming an assistant no tool delivers stops compilation. The
entry key is the assistant name: it matches `[A-Za-z0-9._-]`,
`assistant` is reserved, and it is unique across the catalog and every
inline declaration. `name`, `gate`, `when`, and `skip` never appear in a
catalog entry value — `name` is the key itself, and `gate`/`when`/`skip`
are stage-entry parameters.

## Explicit empty values (overrides)

`skills: []` and `env: {}` are authored overrides that CLEAR the field —
they are not absence. `delegate:` omitted is absence (the value may flow
from a tool-delivered entry); `delegate: false` is an explicit opt-out.
`gate:` and `when:` omitted are absence too — an entry addressing a
pipeline-declared assistant inherits its values (below). Absence vs
empty decides what a tool delivery or a pipeline declaration may still
supply.

## The top-level `delegation:` block

| Key | Type | Default | Note |
|-----|------|---------|------|
| `depth` | int >= 0 | not authored | maximum delegation depth; 0 forbids helper creation |
| `max_tasks` | int >= 1 | `50` (materialized) | whole-run helper task budget |

Both keys are optional; an empty block is valid and materializes
`max_tasks: 50`. A workflow consisting of the block alone is valid.

## Stage attachments (`stages.<name>.assistants`)

A name-keyed map: each key is an assistant name, each value carries the
entry's instruction — exactly one meaningful instruction per entry. A
compiling example:

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

| Entry key | Type | Default | Note |
|------------|------|---------|------|
| `when` | `start` \| `checkpoints` \| `finish` \| `message` | not authored | when the assistant engages |
| `gate` | bool | not authored | `true` — the verdict must pass before the stage finishes |
| `skip` | bool | not authored | `true` ALONE — veto one pipeline-declared assistant of this stage |

`when` is required on an entry that names an assistant declared in the
workflow-file (a catalog entry or a full inline declaration) — the entry
names the assistant, so its engagement timing is authored explicitly. A
when-less entry is legal authoring when the name is declared by the
pipeline-file stage the entry addresses (an extension — see below);
compilation raises "when is required" for a when-less entry naming no
such declaration. `gate` is optional on every entry.

`when: message` is the resting engagement: the engine sends NO initial
request — the helper waits idle until someone messages it, each message
is one turn, and the helper stays attached afterwards. Combine it with
`gate: true` deliberately: a gated message helper produces a verdict only
after it is messaged, so a stage attaching one never finishes until
someone writes to the helper and its verdict passes.

A value carrying any key beyond `gate`/`when` is a full inline declaration
— it accepts the catalog field set plus `gate`/`when` and may carry
neither `prompt` nor `skills` (an override-style inline declaration; the
effective-content requirement is enforced at compilation). A value
carrying only `gate`/`when` is a reference: the agent, prompt, skills,
delegate permission, and env come from the catalog entry; only `gate` and
`when` are the entry's own.

Attachments are valid only under `stages.<name>` — never inside an
extend-entry (the attachments of a new stage are authored in the stages
block by the new stage's name). An empty map equals absence.

## Governing pipeline-shipped assistants

A stage of the pipeline-file may ship its own helper declarations (authored
in the pipeline-file stage body). The workflow addresses such a shipped
assistant through the same `stages.<stage>.assistants.<name>` entry, keyed
by the name's origin:

**Skip — the veto.** `{skip: true}` alone removes the assistant from that
stage for this project: no attachment, no team membership, no generated
profile — the stage itself still runs. `skip` targets exactly one
pipeline declaration of that stage; skipping a name no pipeline
declaration of that stage declares is a compilation error (a catalog or
inline name is governed by not authoring an attachment, never by skip).
`skip: false` alone authoring nothing is a structural
error, and `skip` mixed with any other key is a contradictory-authoring
error.

**Extension — additive configuration.** Any other entry addressing a
pipeline-declared name extends it:

| Key | Effect |
|-----|--------|
| `when` | overrides the pipeline engagement (omitted — the pipeline value stands) |
| `gate` | overrides the pipeline gate (omitted — stands; explicit `false` deliberately downgrades a gated helper to advisory) |
| `agent` / `env` / `delegate` | configure delivery for this project |
| `prompt` | APPENDED to the pipeline text — pipeline text first, one blank line, then this text |
| `skills` | EXPANDS the pipeline list — pipeline entries first, then these, deduplicated by value |

An extension may omit `when` — the pipeline engagement stands. A workflow
that mentions a shipped assistant not at all leaves it exactly as the
pipeline authored it — it attaches on every run, with or without a
workflow-file.

**Visibility.** A pipeline-declared name is visible only to its own
stage's entry: addressing it from another stage is an unknown-assistant
error. The name must not collide with the workflow's catalog or any
inline declaration — one global namespace, enforced at compilation.

## Minimal examples

Veto one shipped assistant, extend another:

```yaml
stages:
  review:
    assistants:
      auditor:            # declared by the pipeline-file stage 'review'
        skip: true        # veto — does not run in this project
      notifier:           # declared by the pipeline-file stage 'review'
        when: checkpoints # re-time: pipeline 'finish' overridden
        agent: codex      # delivery retargeted for this project
```

Extend content (append + expand):

```yaml
stages:
  build:
    assistants:
      security:           # declared by the pipeline-file stage 'build'
        prompt: |
          Also check the lockfile.
        skills: [dep-audit]   # added after the pipeline skills, deduplicated
```

## Structural errors (complete list)

| Authoring | Error |
|---|---|
| `assistants:` non-mapping (a list, a string, a scalar) | non-mapping assistants block in workflow; author the map form keyed by assistant name |
| catalog entry value non-mapping | non-mapping assistant entry in workflow.assistants.NAME |
| unknown catalog key (incl. `name`, `gate`, `when`, `skip`) | unknown key in workflow.assistants.NAME: KEY; valid keys: prompt, skills, agent, delegate, env |
| `delegation:` non-mapping | non-mapping delegation block in workflow |
| unknown `delegation:` key | unknown key in workflow.delegation: KEY; valid keys: depth, max_tasks |
| `depth` not int / < 0 | a structural error |
| `max_tasks` not int / < 1 | a structural error |
| `stages.<name>.assistants` non-mapping (a list, a string, a scalar) | non-mapping assistants in workflow.stages.NAME; author the map form keyed by assistant name |
| attachment value non-mapping | non-mapping assistant attachment in workflow.stages.NAME.ASSISTANT |
| unknown stage-entry key | unknown key in workflow.stages.NAME.assistants.ASSISTANT: KEY; valid keys: prompt, skills, agent, delegate, env, gate, when |
| invalid `when` value (when authored) | a structural error listing the permitted values |
| non-bool `gate` / non-bool `skip` | a structural error |
| `skip: true` mixed with any other key | skip cannot be combined with extension keys in workflow.stages.NAME.assistants.ASSISTANT |
| lone `skip: false` | skip: false requires an extension field in workflow.stages.NAME.assistants.ASSISTANT |
| empty entry `{}` | empty assistant entry in workflow.stages.NAME.assistants.ASSISTANT |
| name outside `[A-Za-z0-9._-]` | a structural error naming the entry |
| the name `assistant` | assistant name is reserved |
| `assistants` in an extend-entry | assistants is forbidden in workflow.extend.NAME |

Compilation-time errors (raised by the compiler, not the parser): a
missing `when` on an entry naming no pipeline declaration of that stage
(a reference or a full inline declaration); an unknown assistant
reference (including a pipeline-declared name addressed from another
stage); a name collision across the effective namespace (catalog, inline,
pipeline declarations — including tool-delivered contributions); an
effective entry resolving no prompt and no skills; an attachment on a
script-only or planning-only stage; the same assistant attached twice to
one stage by a programmatic contribution.

## Anti-patterns

- Do not author `name` inside an entry — the map key IS the assistant name.
- Do not author `gate`/`when`/`skip` in the catalog — they are stage-entry
  parameters.
- Do not rely on a defaulted `when` on a workflow-declared assistant — its
  engagement timing is always authored; only a pipeline-declared assistant
  carries one the extension may inherit.
- Do not combine `skip` with extension keys — the veto is authored alone.
- Do not author `assistants` inside an extend-entry — the attachments of a
  new stage are authored in the stages block by its name.
- Do not expect the parser to resolve references or classify origins — a
  name that matches no declaration of the effective document is a
  compilation error.
- Do not rely on engine defaults: `gate` and `max_tasks` materialize at
  emission; `delegate` omitted is inheritable; the compiled engagement
  value is always written explicitly.
