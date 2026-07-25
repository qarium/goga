# Pipelines

A **pipeline** is a named YAML file that describes a sequence of stages an AI
agent walks through to deliver a piece of work — propose, review, brainstorm,
apply, design, plan, build, change, accept. Pipelines are flat `*.yml` files
resolved from two directories and executed stage-by-stage inside the goga
container.

Pipelines ship four ready-to-use definitions:

| Pipeline  | Purpose                                                              |
|-----------|----------------------------------------------------------------------|
| `feature` | End-to-end feature implementation lifecycle                          |
| `bugfix`  | Root-cause analysis and resolution for a defect                      |
| `patch`   | Refactoring or minimal change with a formalized plan                 |
| `review`  | Scoped review of code, contracts, docs, then lint/format/tests       |

The four pipelines are described in detail in
[Shipped Pipelines](shipped.md).

This section documents the **functional model** of pipelines — what a
pipeline-file is, what a workflow is, and how the two relate. For invocation
flags, exit codes, and Docker mechanics, see the
[`goga pipeline` CLI reference](../cli/pipeline.md).

## Pipeline files vs workflows

The pipelines layer is split into two authoring surfaces:

- **[Pipeline File](pipeline-file.md)** — the base document. Defines the
  pipeline name, description, optional per-stage agent prompt overrides, and
  the ordered list of stages. Authored once per pipeline; lives in
  `.goga/pipelines/<name>.yml` (project) or `~/.goga/pipelines/<name>.yml`
  (user).
- **[Workflows](workflows.md)** — an optional layering document that extends
  a compiled pipeline at run time with a top-level prompt, per-stage agent /
  prompt overrides, loop expansion, stage skipping via `skip`, and new stages declared via `extend`.
  Authored per project; lives in `.goga/workflows/<name>.yml` (project-only).

A pipeline-file answers **what** the pipeline does. A workflow answers
**how the same pipeline should behave in this particular project** without
forking the base file.

## Discovery

Pipelines are flat top-level `*.yml` files resolved from two directories:

| Source   | Directory                | Origin                                                  |
|----------|--------------------------|---------------------------------------------------------|
| project  | `<cwd>/.goga/pipelines/` | Checked into / authored for the current project         |
| user     | `~/.goga/pipelines/`     | Populated by `goga connect` from goga assets + `goga_tool_*` packages |

Only top-level files are scanned — subdirectories are ignored, and `.yaml`
files are excluded. When a name exists in both sources, the project source
wins. See [Shipped Pipelines](shipped.md) for the full installation
algorithm.

## Compilation overview

Each pipeline-file is compiled into a flow-file in a deterministic two-stage
process owned by the `goga/pipeline/compiler` cell:

1. **Parse** — `parse_dsl` reads the pipeline-file, validates the header
   (`name`, `description`, optional `roles`), and detects the body format
   (phases list or stages map).
2. **Serialize** — `serialize_flow` applies per-format `depends_on` rules,
   merges any workflow overrides, embeds any `extend` stages, performs loop
   expansion, resolves the agent mode for each stage, and writes a byte-exact
   flow-file.

When a workflow is in scope, the compiler reconstructs the parsed body
**before** building the output stages: `extend` entries inject new stages
positioned via `before`/`after`, per-stage `agent` overrides choose which
CLI agent runs the stage, per-stage `prompt` overrides layer additional
context alongside the stage's own prompt, `skip: true` removes the stage and reconnects its dependents' `depends_on`, and `loop: N` expands the stage
into N chained copies. See [Workflows](workflows.md) for the full
semantics.

## Where to next

- Author a base pipeline — read the [Pipeline File](pipeline-file.md)
  reference.
- Layer project-specific behavior on top — read the [Workflows](workflows.md)
  reference.
- Run a pipeline from the command line — see the
  [`goga pipeline` CLI reference](../cli/pipeline.md).
