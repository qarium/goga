# Build

Execute a build plan through a **ralph-loop** inside a Docker container.

The build domain is the headless execution surface: a plan file (the output of the [planning cycle](../../workflow/index.md)) is walked task-by-task by an AI agent inside the isolated goga container, with an optional external review pass. Which tasks it solves:

- **Run plans unattended** — `goga build plan.md` prepares the environment, validates preconditions (Docker, config, agent wrappers), and delegates to the ralph-loop running in-container.
- **Keep state persistent** — the ralph-loop state survives across runs of the same plan on the same branch; `--clean` wipes it for a fresh run.
- **Separate the reviewer from the executor** — `build.review_executor` configures a second agent (and an env layer) for the review pass: the build runs tasks with one wrapper, then the review with another.
- **Scope the review diff** — `base_ref` overrides the review's default-branch detection; `patience` stops the external review after N unchanged rounds.

The interactive, stage-by-stage counterpart of this domain is [Pipelines](../pipelines/index.md); the SDD cycle that produces the plans is covered in [Workflow](../../workflow/index.md).

## In this directory

- [CLI](cli.md) — the full `goga build` command reference
- [Configuration](configuration.md) — the `build:` section of `.goga/config.yml`
- [Hooks](hooks.md) — hook points for tool packages
- [API](api.md) — the `goga.build` package facade
