# Shipped Pipelines

Goga ships four pipeline-files inside the installed package at
`goga/assets/pipelines/`. They cover the most common authoring
lifecycles and can be used as templates for project-specific pipelines.

| Pipeline | Purpose                                                              |
|----------|----------------------------------------------------------------------|
| `feature` | End-to-end feature implementation lifecycle                        |
| `bugfix`  | Root-cause analysis and resolution for a defect                    |
| `patch`   | Refactoring or minimal change with a formalized plan               |
| `review`  | Scoped review of code, contracts, docs, then lint/format/tests     |

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
propose → task-review → brainstorm → architecture-review → apply-architecture →
code-design → design-review → coding-plan → plan-review → commit-architecture → accept-result
```

The `propose`, `brainstorm`, `code-design`, and `coding-plan` stages emit
documents named after the current git branch; the `*-review` stages
validate them; `commit-architecture` waits for user confirmation before
acceptance runs.

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

## Shared `commit-changes` stage

The `bugfix`, `patch`, and `review` pipelines share the same
`commit-changes` stage, and `feature` ships a stage named
`commit-architecture` with the same behavior. Each of these stages
commits the untracked changes accumulated during the previous stages.
In `feature`, `bugfix`, and `patch` the stage carries `communication: true`
and asks the user whether the implementation is built and ready for
acceptance — it never autoconfirms the user's answer and genuinely waits
for explicit confirmation before `accept-result` runs. (The authoring
field is `communication`; the compiled flow-file still carries the afm
key `interactive`.) In `review` the stage runs without `communication`:
it simply commits the accumulated review fixes, with no acceptance stage
to follow.

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
