# CLI Command: init

## Purpose

CLI wrapper for the goga project initialization command. Integrates
interactive onboarding with template scaffolding (copier). Routes between
onboarding-only, scaffold-then-onboarding, and upgrade modes, guards
against re-initializing an existing project, and carries the tool
invitation flag into the onboarding session.

## Syntax

```
goga init [<tpl>] [-t <name>]... [--upgrade] [--ref <git-ref>]
```

## Modes

| Invocation | Behaviour |
|------------|-----------|
| `goga init` | onboarding only (interactive survey in a clean directory) |
| `goga init <tpl>` | scaffold (`Scaffold.generate`) → conditional onboarding |
| `goga init --upgrade` | scaffold migration only (`Scaffold.upgrade`); no onboarding |
| `goga init` (when `.goga/` already exists, no `<tpl>`) | non-zero exit: "Project already initialized" |
| `goga init <tpl> --upgrade` | non-zero exit: "<tpl> and --upgrade are mutually exclusive" (`--upgrade` updates existing state tied to a specific repository) |
| `goga init --ref <ref>` (no `<tpl>`, no `--upgrade`) | non-zero exit: "--ref requires <tpl> or --upgrade" (ref is meaningful only with a template source) |
| `goga init -t <name> --upgrade` | non-zero exit: `-t/--tool` requires an onboarding session and `--upgrade` runs none |

## Arguments and options

- `<tpl>` — optional positional. Git URL of a copier template, optionally with
  a ref fragment (`url.git#v1.0`).
- `-t <name>`, `--tool <name>` — repeatable. Invites the named tool package
  into the onboarding session. Acts in both modes that run onboarding (bare
  and `<tpl>`-given); a repeated name deduplicates into one invitation and
  one block, preserving the flag order. Rejected with a nonzero exit when
  combined with `--upgrade`. The command passes the names through as opaque
  data — installation checks, warnings, and the invitation semantics belong
  to the onboarding domain (see `onboarding-usage`).
- `--upgrade` — boolean. Run template migration (`Scaffold.upgrade`) from
  `.goga/scaffold.yml`. No onboarding. Mutually exclusive with `<tpl>` (`--upgrade` updates
  existing state tied to a specific repository). Requires a git-tracked destination (a git repo,
  clean — no uncommitted changes) and a git-trackable template (a git URL) with a non-decreasing
  version; the scaffold engine enforces these and exits nonzero on violation.
- `--ref <git-ref>` — override the ref: with `<tpl>` it overrides the URL fragment; with
  `--upgrade` it overrides the migration target ref. A bare `--ref` (without `<tpl>` and without
  `--upgrade`) is rejected with a nonzero exit.

## Execution order

When `<tpl>` is provided, scaffold runs FIRST, then onboarding. A template may
bring `.goga/config.yml` and other `.goga/` artefacts; onboarding detects
existing artefacts and skips the corresponding survey sections instead of
asking twice.

## Created/modified files

- `.goga/scaffold.yml` — copier state file (written by scaffold; read by
  `--upgrade`). Must not be git-ignored.
- `.goga/config.yml`, `.goga/usages/conventions.md`, `Dockerfile` — produced
  by onboarding (skipped when already present).
- `.goga/tools/<tool>/<file>` — config files contributed by the invited
  tools, written by the onboarding engine.

## Exit code

- `0` — success
- non-zero — error, or already-initialized (bare `init` in a project where
  `.goga/` exists), or missing scaffold state file on `--upgrade`, or invalid argument
  combination (`<tpl>` with `--upgrade`; `-t/--tool` with `--upgrade`; a bare `--ref`)

## Examples

```bash
# Interactive onboarding only (clean directory)
goga init

# Interactive onboarding with invited tool packages
goga init -t my-tool -t viewer

# Scaffold a project from a template, then conditional onboarding
goga init https://github.com/example/goga-py-template.git

# Scaffold from a template and invite tools into the session
goga init https://github.com/example/goga-py-template.git -t my-tool

# Scaffold at a pinned version
goga init https://github.com/example/goga-py-template.git#v1.0

# Override the ref with --ref
goga init https://github.com/example/goga-py-template.git#v1.0 --ref main

# Migrate a previously scaffolded project
goga init --upgrade

# Migrate to a specific ref (override the migration target)
goga init --upgrade --ref v2.0
```

## Anti-patterns

- Do not expect onboarding in `--upgrade` mode — it is scaffold-only, and
  `-t/--tool` is rejected there.
- Do not expect the already-initialized guard to fire when `<tpl>` is given.
- Do not combine `<tpl>` with `--upgrade` — the combination is rejected (`--upgrade` updates
  existing state tied to a specific repository).
- Do not git-ignore `.goga/scaffold.yml` — `--upgrade` depends on it.
- Do not check tool installation in the command — the names are opaque data;
  the onboarding domain warns for invited-but-not-installed names.
