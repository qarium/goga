# Shipped Pipelines

Goga ships four pipeline-files inside the installed package at
`goga/assets/pipelines/`. They cover the most common authoring
lifecycles and can be used as templates for project-specific pipelines.

| Pipeline | Purpose                                                |
|----------|--------------------------------------------------------|
| `feature` | End-to-end feature implementation lifecycle           |
| `bugfix`  | Root-cause analysis and resolution for a defect       |
| `patch`   | Refactoring or minimal change with a formalized plan  |
| `review`  | Convention drift detection and lint/format/tests pass |

## How pipelines get installed

Pipelines land in the user pipeline directory (`~/.goga/pipelines/`)
through the same `goga connect` step that installs skills. Pipeline
installation runs once at the end of `goga connect`, after every agent
has been symlinked, and reuses the same `goga_tool_*` discovery that
skills use.

Two sources feed `~/.goga/pipelines/`, applied in this order:

1. **Internal source** — flat `*.yml` files from `goga/assets/pipelines/`
   shipped with the goga package. These are always installed first and
   establish the base.
2. **Tool packages** — every installed Python package with the
   `goga_tool_*` prefix is scanned for a `pipelines/` directory. Each
   flat `*.yml` file in that directory is copied into
   `~/.goga/pipelines/`.

This is symmetric with how skills spread: tool packages ship both
`skills/<name>/SKILL.md` and `pipelines/<name>.yml` next to each other,
and a single `goga connect` run installs both.

### Conflict resolution

A name conflict — the same `<name>.yml` exists in both the internal
source and a tool package — is resolved by the `--force-overwrite` flag
passed to `goga connect`:

| `--force-overwrite` | Behaviour on name conflict                                       |
|---------------------|------------------------------------------------------------------|
| `false` (default)   | The tool's pipeline is skipped; the internal-source pipeline wins. A warning is logged to stderr. |
| `true`              | The tool's pipeline overwrites the internal-source pipeline.     |

This mirrors the conflict semantics used for tool-skill installation.

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

## `feature`

End-to-end feature implementation. Eleven stages that walk from task
formulation through acceptance:

```
propose → task-review → brainstorm → architecture-review → apply →
design → design-review → plan → plan-review → commit-architecture → accept
```

The `propose`, `brainstorm`, `design`, and `plan` stages emit documents
named after the current git branch; the `*-review` stages validate them;
`commit-architecture` waits for user confirmation before acceptance runs.

## `bugfix`

Defect resolution lifecycle. Three stages:

```
hotfix → commit-changes → accept
```

`hotfix` runs the `goga-change` skill for root-cause analysis and
resolution.

## `patch`

Refactoring or minimal change with a formalized plan. Three stages:

```
ad-hoc → commit-changes → accept
```

`ad-hoc` runs the `goga-change` skill for task formalization, plan, and
implementation in one stage.

## `review`

Project analysis against conventions. Three stages:

```
compliance-convention → testing-changes → commit-changes
```

`compliance-convention` reads `.goga/usages/conventions.md`, scans the
change scope (the diff against the default branch, or a user-selected
scope), and fixes only the convention drift the user confirms. It
deliberately does not run lint, format, or tests — those are the job of
the next stage. `testing-changes` runs lint, format, and tests per the
same convention file and fixes every error so the branch stays green on
CI. `commit-changes` then commits the accumulated fixes.

Both `compliance-convention` and `testing-changes` carry explicit
constraints: the convention stage must not pick a default branch when it
is ambiguous (main, master, …) and must not fabricate a finding priority
when it is not obvious; the testing stage must not ignore any error. The
default branch ambiguity is resolved by asking the user.

## Shared `commit-changes` stage

The `bugfix`, `patch`, and `review` pipelines share the same
`commit-changes` stage, and `feature` ships a stage named
`commit-architecture` with the same behavior. Each of these stages
commits the untracked changes accumulated during the previous stages and,
in `feature`/`bugfix`, asks the user whether the implementation is built
and ready for acceptance. The stage is `interactive` and never
autoconfirms the user's answer — it genuinely waits for explicit
confirmation before `accept` runs.

The stage explicitly excludes `docs/<tasks|arch|design|plans>` from the
commit path, so in-flight design artifacts that live outside the source
tree are not bundled into the implementation commit.

## Using them as templates

Copy any shipped pipeline into the project pipeline directory and edit
the copy:

```bash
cp ~/.goga/pipelines/feature.yml .goga/pipelines/my-feature.yml
```

The copy becomes a **project** pipeline and shadows the shipped one only
when both share a name — otherwise they coexist as two distinct
pipelines. See [Pipeline File](pipeline-file.md) for the authoring
reference.

To distribute a pipeline **across projects** alongside other goga
tooling, ship it inside a `goga_tool_*` package under
`<package>/pipelines/<name>.yml`. A `goga connect` run will then pick it
up automatically — the same mechanism that installs tool skills. Do not
place hand-edited pipelines directly into `~/.goga/pipelines/`, because
`goga connect` recreates that directory on every run.

## See also

- [Pipeline File](pipeline-file.md) — full DSL reference for authoring or
  forking a pipeline.
- [Workflows](workflows.md) — layer project-specific behavior on top of a
  shipped pipeline without forking it.
- [`goga connect` CLI reference](../cli/connect.md) — full pipeline
  installation algorithm and conflict-resolution semantics.
- [`goga connect` CLI reference](../cli/connect.md) — install shipped
  pipelines into the user pipeline directory.
