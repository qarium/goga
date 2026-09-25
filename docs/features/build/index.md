# Build

Execute a build plan inside a Docker container.

The build domain is the headless execution surface: a plan file (the output of the [planning cycle](../../workflow/index.md)) is walked task-by-task by an AI agent inside the isolated goga container, with an optional external review pass. Which tasks it solves:

- **Run plans unattended** — `goga build plan.md` prepares the environment, validates preconditions (Docker, config, agent wrappers), and delegates to the build engine running in-container.
- **Keep state persistent** — the build state survives across runs of the same plan on the same branch; `--clean` wipes it for a fresh run.
- **Separate the reviewer from the executor** — a run with review on is always two passes: tasks on the `build.agent` wrapper, then review on the review agent's wrapper (`build.review.agent`, inheriting `build.agent` when unset, with its own env layer under `build.review.env` that never inherits the root env).
- **Scope the review diff** — `build.review.base_ref` overrides the review's default-branch detection; `build.review.additional.patience` stops the external review after N unchanged rounds.
- **Gate and observe runs** — tools subscribed to `build/validate_build` read the resolved run facts and may veto the run before any pass; four notifications (`build_started`, `pass_started`, `pass_completed`, `build_completed`) carry the run's facts to reporting tools (see [Hooks](hooks.md)).

The interactive, stage-by-stage counterpart of this domain is [Pipelines](../pipelines/index.md); the SDD cycle that produces the plans is covered in [Workflow](../../workflow/index.md).

## In this directory

- [CLI](cli.md) — the full `goga build` command reference
- [Configuration](configuration.md) — the `build:` section of `.goga/config.yml`
- [Hooks](hooks.md) — hook points for tool packages
- [API](api.md) — the `goga.build` package facade
