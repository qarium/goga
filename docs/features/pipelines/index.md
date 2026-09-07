# Pipelines

A **pipeline** is a named YAML file that describes a sequence of stages an AI
agent walks through to deliver a piece of work — propose, review, brainstorm,
apply, design, plan, build, change, accept. Pipelines are flat `*.yml` files
resolved from two directories and executed stage-by-stage inside the goga
container.

Pipelines ship ready-to-use definitions:

| Pipeline      | Purpose                                                                  |
|---------------|--------------------------------------------------------------------------|
| `refinement`  | Product definition and task refinement: define, discover, propose, task review |
| `development` | End-to-end development lifecycle: architecture, design, plan, accept     |
| `bugfix`      | Root-cause analysis and resolution for a defect                          |
| `patch`       | Refactoring or minimal change with a formalized plan                     |
| `review`      | Scoped review of code, contracts, docs, then lint/format/tests           |
| `sync`        | Sync specifications and tests with the implementation                    |

The shipped pipelines are described in detail in
[Shipped Pipelines](shipped.md).

This page documents the **functional model** of pipelines — what a
pipeline-file is, what a workflow is, and how the two relate. For invocation
flags, exit codes, and Docker mechanics, see the
[`goga pipeline` CLI reference](cli.md).

## Pipeline files vs workflows

The pipelines layer is split into two authoring surfaces:

- **[Pipeline File](pipeline-file.md)** — the base document. Defines the
  pipeline name, description, optional per-stage agent prompt overrides, and
  the ordered list of stages. Authored once per pipeline; lives in
  `.goga/pipelines/<name>.yml` (project) or `~/.goga/pipelines/<name>.yml`
  (user).
- **[Workflows](workflows.md)** — an optional layering document that extends
  a compiled pipeline at run time with a top-level prompt, per-stage agent /
  prompt overrides, loop expansion, stage skipping via `skip`, manual launch
  via `manual`, note buttons via `notes`, new stages declared via `extend`,
  and project-memory participation via the `memory` block and the per-stage
  `reflect` / `memory` instructions.
  Authored per project; lives in `.goga/workflows/<name>.yml` (project-only).

A pipeline-file answers **what** the pipeline does. A workflow answers
**how the same pipeline should behave in this particular project** without
forking the base file.

## Discovery

Pipelines are flat top-level `*.yml` files resolved from two directories:

| Source   | Directory                | Origin                                                  |
|----------|--------------------------|---------------------------------------------------------|
| project  | `<cwd>/.goga/pipelines/` | Checked into / authored for the current project         |
| user     | `~/.goga/pipelines/`     | Populated by `goga connect` from goga assets and `goga_tool_*` packages |

Only top-level files are scanned — subdirectories are ignored, and `.yaml`
files are excluded. When a name exists in both sources, the project source
wins. A tool pipeline is namespaced as `<tool>:<name>.yml` — just a
filename stem containing a colon — so it is resolved like any other bare
name and the discovery scan picks it up verbatim. See
[Shipped Pipelines](shipped.md) for the full installation algorithm.

## Compilation overview

Each pipeline-file is compiled into a single deterministic pipeline
definition in two stages:

1. **Parse** — goga reads the pipeline-file, validates the header
   (`name`, `description`, optional `roles`), and detects the body format
   (phases list or stages map).
2. **Serialize** — goga applies per-format `depends_on` rules,
   merges any workflow overrides, embeds any `extend` stages, performs loop
   expansion, resolves the agent mode for each stage, and writes the exact
   stage sequence the run will follow.

When a workflow is in scope, goga reconstructs the parsed body
**before** building the output stages: `extend` entries inject new stages
positioned via `before`/`after`, per-stage `agent` overrides choose which
CLI agent runs the stage, per-stage `prompt` overrides layer additional
context alongside the stage's own prompt, `skip: true` removes the stage
and reconnects its dependents' `depends_on`, `loop: N` expands the stage
into N chained copies, per-stage `approve: auto|plan|dialog` drives the
auto-approval behavior (interactive suppression and/or automatic approval
of agent actions), and per-stage `manual: true|false` forces or cancels
the stage's manual launch mode (a stage-body `trigger: manual` makes the
stage pause until launched). A per-stage `notes` map becomes the stage's
note buttons. A workflow `memory` block plus per-stage `reflect` /
`memory` instructions turn on project-memory participation — active only
when at least one stage takes part. Every stage is either an **agent stage** — a `prompt` for an AI agent,
with optional `skills` and `roles` — or a **script stage** — a literal
`script` executed without an agent (see
[Pipeline File — Stage fields](pipeline-file.md#stage-fields)). Any stage
may also carry `before_script` / `after_script` bracketing scripts, and a
script stage takes a `timeout` (a duration string such as `30m` or
`1h30m`) that bounds its script action. See
[Workflows](workflows.md) and
[Pipeline File — Script directives](pipeline-file.md#script-directives)
for the full semantics.

## Where to next

- Author a base pipeline — read the [Pipeline File](pipeline-file.md)
  reference.
- Layer project-specific behavior on top — read the [Workflows](workflows.md)
  reference.
- Run a pipeline from the command line — see the
  [`goga pipeline` CLI reference](cli.md).

## In this directory

- [CLI](cli.md) — the full `goga pipeline` command reference
- [Automation](automation.md) — running pipelines unattended and in CI
- [Runtime](runtime.md) — the container every pipeline runs in
- [Configuration](configuration.md) — the `pipeline:` section of `.goga/config.yml`
- [Hooks](hooks.md) — hook points for tool packages
- [API](api.md) — the `goga.pipeline` package facade
- [Pipeline File](pipeline-file.md) — the base authoring document
- [Workflows](workflows.md) — the project-specific layering document
- [Shipped Pipelines](shipped.md) — the ready-to-use definitions
