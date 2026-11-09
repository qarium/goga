# gates — authoring stage quality gates in the workflow-file

`gates` declares automated stage-completion checks: a per-stage list of check
steps a stage must pass before it counts as done, plus an optional
workflow-level settings block tuning the correction retries. The document
addresses workflow-file authors: everything described here is validated
structurally at parse time — typos and type or value mismatches are rejected
with a one-line error naming the workflow location. goga never runs the
checks: the engine executes the compiled gate and owns every retry semantic.

## The top-level `gates:` settings block

| Key | Type | Default | Note |
|-----|------|---------|------|
| `patience` | int >= 0 | not authored | tolerance for an unchanged correction stalemate |
| `max_iterations` | int >= 0 | not authored | bound of failed correction attempts |
| `fresh_correction` | bool | not authored | whether a correction session starts fresh |

- Authored keys only — no defaults are materialized; the engine defaults
  apply for unauthored keys.
- An empty block (`gates: {}`) equals absence. A workflow consisting of the
  block alone is valid.
- A boolean is not an integer for these checks.
- The settings travel only with stages that declare check steps — the block
  alone is inert: nothing is emitted, no error is raised.

## Per-stage check steps (`stages.<name>.gates`)

A list of check steps; an empty list equals absence. Each step is a mapping:

| Key | Type | Required | Note |
|-----|------|----------|------|
| `name` | str | yes | the dashboard label; required — the step numbering fallback is never relied on |
| `script` | str, non-empty | xor `agent` | a shell check step |
| `agent` | str, non-empty | xor `script` | an AI-review step; the same agent-name vocabulary as the per-stage agent override |
| `timeout` | str | no | carried verbatim; the duration grammar is engine-owned |
| `prompt` | str | no | the review instruction of an AI step — agent steps only (forbidden on a `script` step) |

Exactly one of `script`/`agent` per step — both or neither is a structural
error. The steps compile in authored order.

## Minimal examples

Settings plus a shell step and an AI-review step:

```yaml
gates:
  max_iterations: 2
  fresh_correction: true
stages:
  implementation:
    gates:
      - name: tests
        script: pytest -q
      - name: review
        agent: reviewer
        prompt: Review the diff for correctness.
```

Without the settings block the gated stages carry the steps alone (the
engine list form); an authored `timeout` overrides the materialized shell
default:

```yaml
stages:
  build:
    gates:
      - name: compile
        script: make all
        timeout: 30m
```

## Structural errors (parse time)

- "non-mapping gates block in workflow" — a scalar/list settings value
- "unknown key in workflow.gates: KEY; valid keys: patience, max_iterations, fresh_correction"
- "non-int value in workflow.gates.KEY" / "KEY must be >= 0 in workflow.gates" (a boolean is not an integer)
- "non-bool value in workflow.gates.fresh_correction"
- "non-list gates in workflow.stages.NAME"
- "non-mapping gate step in workflow.stages.NAME.gates[i]"
- "unknown key in workflow.stages.NAME.gates[i]: KEY; valid keys: name, script, agent, timeout, prompt"
- "gates step without name in workflow.stages.NAME.gates[i]"
- "gates step must carry exactly one of script/agent in workflow.stages.NAME.gates[i]"
- "script must be a non-empty string in workflow.stages.NAME.gates[i]" (and the agent counterpart)
- "prompt is forbidden on a script gate step in workflow.stages.NAME.gates[i]" — prompt belongs to AI steps
- "gates is forbidden in workflow.extend.NAME" — checks of a new stage are
  authored in the stages block by the new stage's name

## What is NOT validated here

- The `timeout` duration grammar and the `name` text content — values pass
  verbatim; the engine reports malformed values at flow load/preflight.
- Stage names — the compiler's strict unknown-stage check covers them.
- Engine interplay constraints (the failure budget vs the patience value,
  the effective ceiling) — the engine owns and reports these.

## Anti-patterns

- Do not author `gates` in an extend-entry or in a stage body — both are
  strict structural errors; the checks of any stage are authored in the
  stages block by the stage's name.

This cell does NOT act on gates — no command composition, no emission
decisions, no retry interpretation. The compiler translates the authored
vocabulary one-directionally into the engine's and emits the stage gate;
the engine runs it.
