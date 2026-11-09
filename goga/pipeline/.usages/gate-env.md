# Gate step env delivery

## Domain

How the `stages.<name>.gates[*].env` workflow instruction reaches a check
step's execution: authoring, the wrapper mechanism, and the layering rules.
Target audience: workflow authors declaring per-step gate environments and
contributors reasoning about the compiled verify emission.

## Authoring

Inside the workflow stages block, a gate check step may carry `env` — a map
of environment variables for that step, literal and/or rendered from profile
data, valid on BOTH step kinds (a shell `script` step and an AI `agent`
step alike):

```yaml
stages:
  implementation:
    gates:
      - name: Unit tests
        script: pytest -q
        env:
          FOO: bar
      - name: Code review
        agent: reviewer
        prompt: Review the diff.
        env:
          REVIEW_STRICTNESS: strict
```

An empty map equals absence. Keys must be legal environment variable names
(POSIX shape: a letter or underscore, then letters, digits, or underscores)
— anything else is a strict pre-run error naming the stage, the step, and
the key, raised before any wrapper is written.

## Delivery mechanism

The engine's verify-step schema carries no `env` field — an emitted key is
rejected at flow load — so a step's env travels through a generated sh
closure wrapper the step's `run` (a script step) or `command` (an agent
step) field points at. The compiler emits the step exactly as it would
without env; after compilation goga patches the claimed steps' lines in the
written flow-file to point at their wrappers — a targeted patch; every other
byte of the flow-file stays untouched, and a run whose gates declare no step
env is not rewritten at all (byte-identical). The wrapper:

1. exports the step's env values (above every global env layer),
2. carries the payload — the authored script lines as-is on a script step
   (the same shell, working directory, and exit status the engine gives the
   authored `run` value), or execs the agent's in-container wrapper
   forwarding `"$@"` on an AI step (the per-stage env closure shape).

Wrappers are generated per run in a container-local temp directory
(`/tmp/goga-gate-env`, owner-only) and never touch the project directory.
The file name composes the stage id, the step index, and the step name — the
index guarantees uniqueness (step names are not unique-checked). Loop-expanded
copies of a gated stage each receive their own wrapper with the same values.

## What stays identical

Steps without `env` compile and serialize without wrappers — the flow output
of a gate-env-free workflow stays byte-identical to the compiler's direct
composition. The step's `name`/`timeout`/`prompt` values and the gate
settings ride the emission unchanged; only the claimed step's `run`/`command`
line differs. The stage-level `env` instruction (see `per-stage-env`) is a
separate surface with its own wrappers — the two layer independently.
