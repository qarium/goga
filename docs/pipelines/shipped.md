# Shipped Pipelines

Goga ships six pipeline-files inside the installed package at
`goga/assets/pipelines/`. They cover the most common authoring
lifecycles and can be used as templates for project-specific pipelines.

| Pipeline | Purpose                                                              |
|----------|----------------------------------------------------------------------|
| `refinement`  | Product definition and task refinement: define, discover, propose  |
| `development` | End-to-end development lifecycle: architecture, design, plan, accept |
| `bugfix`  | Root-cause analysis and resolution for a defect                    |
| `patch`   | Refactoring or minimal change with a formalized plan               |
| `review`  | Scoped review of code, contracts, docs, then lint/format/tests     |
| `sync`    | Sync specifications and tests with the implementation              |

## How pipelines get installed

Pipelines land in the user pipeline directory (`~/.goga/pipelines/`)
through the same `goga connect` step that installs skills. Pipeline
installation runs once at the end of `goga connect`, after every agent
has been symlinked, and reuses the same `goga_tool_*` discovery that
skills use.

Two sources feed `~/.goga/pipelines/`, applied in this order:

1. **Internal source** — flat `*.yml` files from `goga/assets/pipelines/`
   shipped with the goga package. These are always installed first, are
   written **un-prefixed** (e.g. `development.yml`), and establish the base.
2. **Tool packages** — every installed Python package with the
   `goga_tool_*` prefix is scanned for a `pipelines/` directory. Each
   flat `*.yml` file `<name>.yml` in that directory is copied into
   `~/.goga/pipelines/` **namespaced as `<tool>:<name>.yml`**, where
   `<tool>` is the package name with the `goga_tool_` prefix dropped and
   underscores normalized to hyphens (so `goga_tool_hello_world` becomes
   `hello-world`).

Namespacing makes every tool pipeline addressable as
`goga pipeline <tool>:<name>` (e.g. `goga pipeline acme:deploy`), while
internal pipelines stay un-prefixed and are addressed as
`goga pipeline <name>` (e.g. `goga pipeline development`). This structurally
prevents collisions both between a tool pipeline and an internal-source
pipeline and between two tools that ship the same pipeline name.

This diverges from how skills spread: tool skills are installed under a
`goga-tool-` prefix into `~/.goga/skills/`, while tool pipelines are
namespaced by tool into `~/.goga/pipelines/`. The discovery mechanism is
shared, but the destination layout differs.

### Residual conflict resolution

After namespacing, a tool pipeline can only collide with an existing
file when its namespaced destination `<tool>:<name>.yml` already exists
— for example, when the internal goga source already provides a pipeline
at that exact namespaced stem, or when another tool resolves to the same
namespace. Such a residual conflict is
resolved by the `--force-overwrite` flag passed to `goga connect`:

| `--force-overwrite` | Behaviour on residual namespaced conflict                        |
|---------------------|------------------------------------------------------------------|
| `false` (default)   | The tool's pipeline is skipped; the existing file wins. A warning is logged to stderr. |
| `true`              | The tool's pipeline overwrites the existing file at `<tool>:<name>.yml`. |

This mirrors the residual-conflict semantics used for tool-skill
installation — see [`goga connect`](../cli/connect.md).

### Idempotency

`~/.goga/pipelines/` is **fully recreated on every `goga connect` run**
(delete + copy), the same way `~/.goga/skills/` is. A pipeline file
placed there by hand does not survive the next connect — write the file
into the internal source or into a tool package instead.

The project-level directory `.goga/pipelines/` is never touched by
`goga connect` — it is user-owned at the project scope.

### After connect

Once installed, shipped pipelines behave like any other user pipeline.
They are discoverable by `goga pipeline`, can be applied as-is, layered
on with a [workflow](workflows.md), or shadowed by a same-named project
pipeline (project source wins on name conflicts — see
[Discovery](pipeline-file.md#document-shape)).

## `refinement`

The refinement workround as a pipeline. Four stages that turn a product
idea into a reviewed task:

```
define → discover → propose → task-review
```

`define` runs the `goga-define` skill and produces a PRD; `discover`
records the settled technical decisions as a short ADR; `propose`
formulates the structured task; `task-review` verifies it. The `define`,
`discover`, `propose`, and `task-review` stages emit and consume
documents named after the current git branch (`docs/defines/`,
`docs/proposals/`, `docs/tasks/`), and each later stage falls back to
the earlier artifacts when they exist.

## `development`

The development workround as a pipeline. Nine stages that walk from a
reviewed task through acceptance:

```
brainstorm → architecture-review → apply-architecture → code-design → design-review →
coding-plan → plan-review → commit-changes → accept-result
```

The `brainstorm`, `code-design`, and `coding-plan` stages emit documents
named after the current git branch; the `*-review` stages validate them;
`commit-changes` commits the accumulated changes and waits for user
confirmation that the implementation is built before acceptance runs.
`accept-result` is triggered manually (`trigger: manual`) — it runs the
acceptance audit only when you decide the implementation is done.

## `bugfix`

Defect resolution lifecycle. Three stages:

```
hotfix → commit-changes → accept-result
```

`hotfix` runs the `goga-change` skill for root-cause analysis and
resolution.

## `patch`

Refactoring or minimal change with a formalized plan. Three stages:

```
ad-hoc → commit-changes → accept-result
```

`ad-hoc` runs the `goga-change` skill for task formalization, plan, and
implementation in one stage.

## `review`

Scoped review of a change set against conventions, contracts, and
documentation, followed by lint/format/tests. Six stages:

```
discovery-scope → code-review → contracts-review → documentation-review → testing → commit-changes
```

`discovery-scope` defines the change scope (the diff against the default
branch, or a user-selected scope), persists it to `/tmp/changes.txt` in a
form readable for the downstream stages, and asks the user when the
default branch is ambiguous (main, master, …).

`code-review` reads `/tmp/changes.txt` and the project convention
`.goga/usages/conventions.md`, categorizes the convention rules, and for
each deviation emits a finding with `location`, `convention`, and
`severity` — fixing only the deviations the user confirms. Convention
rules take precedence over the existing source code.

`contracts-review` reviews changed CODEMANIFEST and `.usages/` files
against explicit checklists (annotations describe high-level order
without implementation details; no `X from Imports` phrasing; multilevel
numerical numbering; usage files are self-contained and connected through
Imports) and requires `goga lint` to be clean after fixes.

`documentation-review` reviews changed documentation pages against a
technical-writing checklist (content accuracy, structural hierarchy,
terminology consistency, formatting markup). It deliberately skips
markdown files inside `.usages/` and `.goga/usages/`, and skips
CODEMANIFEST files — those are owned by `contracts-review`.

`testing` runs lint, format, and tests per `.goga/usages/conventions.md`
and fixes every error so the branch stays green on CI. If the convention
does not define how lint, format, and tests are executed, the stage asks
the user to specify the verification procedure.

`commit-changes` commits the accumulated fixes.

All four review stages (`code-review`, `contracts-review`,
`documentation-review`, `testing`) carry shared constraints: do not
fabricate a finding priority when it is not obvious (set it as
`unknown`); do not run lint/format/tests outside the dedicated `testing`
stage; fix findings only after user confirmation. The `testing` stage
must not ignore any error.

## `sync`

Re-syncs specifications and tests with the implementation. Two stages:

```
resolve → commit-changes
```

`resolve` runs the `goga-accept` skill: starting from the uncommitted
changes, it resolves the drift between code, contracts, and tests.
`commit-changes` then commits the accumulated fixes.

## Using them as templates

Copy any shipped pipeline into the project pipeline directory and edit
the copy:

```bash
cp ~/.goga/pipelines/development.yml .goga/pipelines/my-development.yml
```

The copy becomes a **project** pipeline and shadows the shipped one only
when both share a name — otherwise they coexist as two distinct
pipelines. See [Pipeline File](pipeline-file.md) for the authoring
reference.

To distribute a pipeline **across projects** alongside other goga
tooling, ship it inside a `goga_tool_*` package under
`<package>/pipelines/<name>.yml`. A `goga connect` run will then pick it
up automatically and install it as `<tool>:<name>.yml` — the same
discovery mechanism that installs tool skills. Do not place hand-edited
pipelines directly into `~/.goga/pipelines/`, because `goga connect`
recreates that directory on every run.

## See also

- [Pipeline File](pipeline-file.md) — full DSL reference for authoring or
  forking a pipeline.
- [Workflows](workflows.md) — layer project-specific behavior on top of a
  shipped pipeline without forking it.
- [`goga connect` CLI reference](../cli/connect.md) — install shipped
  pipelines into the user pipeline directory, namespacing rules, and
  residual conflict-resolution semantics.
