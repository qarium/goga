# Runtime Commands for Build and Pipeline Artifacts

## Problem

goga users — developers running `goga build` and `goga pipeline` — need to inspect, preserve, and share the host-side state that those runs leave behind: build state under `~/.goga/runtime/builds/<normalized-project>/<branch>/` and pipeline state under `~/.goga/runtime/pipelines/<normalized-project>/<branch>/<pipeline-name>/`.

Today these locations are an internal implementation detail:

- the CLI never reveals them, so finding the artifacts of a failed or suspicious run requires reverse-engineering the internal path formula;
- there is no built-in way to package the state, so preparing a bug report, a backup, or a transfer between machines means manual path reconstruction and hand-rolled archiving;
- the `--clean` flags of `goga build` / `goga pipeline` destroy the state irrecoverably, with no supported way to preserve it first.

As a result, users cannot reliably locate build/pipeline artifacts when investigating a run, and cannot preserve or hand over that state when they need to report, compare, back up, or move it.

## Users

**Primary user.** A goga user — a developer working in a terminal in a project repository, who runs `goga build` and `goga pipeline` from the project working directory. They encounter the problem:

- after a suspicious or failed run, when they want to inspect what the run left behind;
- before wiping state with `--clean`, when they want to preserve it;
- when filing a bug report or moving state between machines, when they need to package it.

The user is comfortable with the CLI, git, and shell scripting, and expects command output to be usable both interactively (copy/paste) and in scripts.

**Secondary actor.** The recipient of an archive — a maintainer or colleague who receives the packaged artifacts (for example, attached to a bug report) and opens them on their own machine. They never operate the new commands, but they expect a standard, self-contained archive openable without goga.

**User expectations:**

- the printed path is exact and directly usable — copy/paste, piping, scripts;
- the printed path reflects the same location identity the build/pipeline commands use (same project, branch, and pipeline-name rules, including `:` → `-` for pipeline names);
- the archive is created in a predictable place under a predictable name and is openable with standard tools;
- locating and packaging artifacts never modifies or deletes the underlying state.

**Constraints on the user side:** the commands are run from the project working directory (the artifact location derives from the current directory and the current git branch); obtaining a pipeline's artifacts requires knowing the pipeline name, which the run flow itself establishes.

## Goals

1. **Artifact discoverability.** A goga user can determine, from the CLI, the exact host location of the current project's build artifacts and of a given pipeline's artifacts (per branch) — replacing reverse-engineering of the internal path formula.
2. **Artifact portability.** A goga user can package the relevant build or pipeline artifacts into a single self-contained archive suitable for bug reports, backup before `--clean`, and transfer between machines — without manual path reconstruction and without altering or endangering the underlying state.

## User Experience

The change introduces a new top-level CLI command group, `goga runtime`, with three stateless subcommands run from the project working directory.

### Entry point

The user is in a terminal at the project root and wants to find where a run's artifacts live or to package them. They invoke a `goga runtime` subcommand; no container is started, no project files are touched.

### Primary scenarios

**Locate build artifacts.** The user runs `goga runtime build`. The product prints exactly one stdout line — the absolute host path of the build artifacts directory for the current project and branch — and nothing else. Nothing on disk is created, modified, or deleted. This mirrors the established scripting contract of `goga history path` (one line, for scripting, e.g. `dir=$(goga runtime build)`).

**Locate pipeline artifacts.** The user runs `goga runtime pipeline <name>`. The product prints exactly one stdout line — the absolute host path of that pipeline's artifacts directory — under the same guarantees. The pipeline name is sanitized exactly as when the pipeline runs (`:` → `-`), so the printed path is the directory the run actually uses.

**Archive artifacts.** The user runs `goga runtime archive` and explicitly selects exactly one target — the build artifacts or a named pipeline's artifacts. The product:

- resolves the same directory the corresponding path command prints;
- packages the target directory's full recursive contents into a single `.tar.gz` archive;
- writes the archive to the current working directory under the deterministic name `goga-runtime-<target>-<branch>.tar.gz`, where `<target>` is `build` or the sanitized pipeline name;
- prints exactly one stdout line — the path of the created archive — and leaves the source state untouched.

### Alternative scenarios

- **Custom destination.** `-o/--output` gives an explicit archive destination path; an explicit path expresses intent to overwrite an existing file there.
- **Outside a git repository / detached HEAD.** The branch segment falls back to `default`, inherited from the existing location identity; all commands still work.
- **Pipeline names containing `:`** are sanitized the same way as at run time, so path and archive commands address the same directory the run uses.

### Failure scenarios

- **Archive target directory does not exist** (nothing ever ran, or state was wiped by `--clean`): the command reports the missing path in a human-readable error, creates no archive file, and exits non-zero. No empty archive is produced.
- **Default archive name already exists:** the command refuses to overwrite, reports the collision, points the user to an explicit destination via `-o`, and exits non-zero.
- **Usage errors** — missing `<name>` for `pipeline`, or missing/duplicate target selection for `archive`: a usage error with a non-zero exit.
- **Unwritable destination:** a clear error with a non-zero exit; no partial files are kept.

### Feedback, consequences, recovery

- Path commands print exactly one line on stdout; errors are human-readable messages on stderr with non-zero exit codes; stdout is reserved for the single result line in all commands.
- All commands are read-only with respect to runtime state; the only new artifact is the archive file itself, which can be deleted without consequence.
- Re-running any command is safe: path commands return the same value; `archive` may be re-run subject to the collision rule.
- Consistency of a snapshot is not guaranteed while a build or pipeline is actively writing its state; archives are best taken between runs. This is a documented limitation, not an enforced precondition.

## Requirements

### Command group

- **R1.** The product must provide a top-level CLI command group `runtime` with three subcommands: `build`, `pipeline <name>`, and `archive`.
- **R2.** All `runtime` commands must derive artifact locations from the current working directory and the current git branch, using the same identity rules as `goga build` and `goga pipeline` (`/` → `-` in the project path and branch segments; branch falls back to `default` outside a repository or on detached HEAD).

### Path commands

- **R3.** `goga runtime build` must print exactly one line on stdout — the absolute path of the build artifacts directory for the current project and branch — with no other stdout output and no side effects on disk.
- **R4.** `goga runtime pipeline <name>` must print exactly one line on stdout — the absolute path of that pipeline's artifacts directory — applying the same `:` → `-` sanitization to `<name>` as the pipeline run commands do; same single-line and no-side-effect guarantees. A missing `<name>` is a usage error with a non-zero exit.
- **R5.** Path commands must print the computed path even when the directory does not yet exist; the location is deterministic and nothing is created on disk.

### Archive command

- **R6.** `goga runtime archive` must package exactly one target per invocation — the build artifacts or the artifacts of one named pipeline — selected explicitly through the command line. Invoking it with no target selection or with both selections is a usage error.
- **R7.** The archive must contain the full recursive contents of the target directory, preserving the relative structure.
- **R8.** The archive format must be `.tar.gz`, self-contained and openable with standard tools without goga.
- **R9.** By default the archive must be written to the current working directory under the deterministic name `goga-runtime-<target>-<branch>.tar.gz` (`<target>` = `build` or the sanitized pipeline name; `<branch>` = the branch segment of the location identity).
- **R10.** `-o/--output` must accept an explicit destination path; an explicitly given destination may overwrite an existing file at that path.
- **R11.** When the default-named archive already exists, the command must refuse to overwrite it, report the collision, suggest an explicit destination, and exit non-zero.
- **R12.** On success, `archive` must print exactly one line on stdout — the path of the created archive.
- **R13.** When the target directory does not exist, `archive` must report the missing path, create no archive file, and exit non-zero.
- **R14.** Archiving must not modify, move, or delete anything in the source directory.

### General behavior

- **R15.** All errors must be reported as human-readable messages on stderr with non-zero exit codes; stdout stays reserved for the single result line.
- **R16.** Repeated invocations must be safe: path commands are deterministic; `archive` re-runs are subject to R11.
- **R17.** All `runtime` commands must run host-side, without launching containers and without requiring a container runtime.
- **R18.** The new command group must ship with CLI help consistent with the existing goga commands.

## Constraints

- **Location identity.** The new commands must expose the same runtime locations the build/pipeline commands actually use — the shared runtime formula with its sanitization rules and `default` branch fallback. No second, divergent path scheme may be introduced.
- **Deterministic, non-configurable locations.** Runtime artifact locations remain formula-derived and non-configurable; the change introduces no configuration surface for them.
- **Observer safety.** Path and archive operations must never create, modify, or delete runtime state; the state lifecycle (including `--clean`) stays owned by the build/pipeline commands.
- **Path-composition purity boundary.** Path composition remains a side-effect-free capability of the existing runtime utilities; effects (file creation, packaging) belong to the command layer. This established product boundary must be preserved.
- **Scripting contract.** The established CLI query contract applies: exactly one stdout line per query command, no banners or progress chatter on stdout (as with `goga history path`).
- **Working-directory anchoring.** Commands are host-side and derive project identity from the current working directory, as the build/pipeline commands do.
- **Archive portability.** Archives must be self-contained `.tar.gz` files openable with standard tools without goga.

## Scope

### In Scope

- The new top-level `goga runtime` command group with subcommands `build`, `pipeline <name>`, and `archive` (exactly one target per archive invocation).
- Deterministic archive naming, the `-o/--output` destination override, and the collision behavior.
- Failure behavior: usage errors, missing-target errors, unwritable-destination errors, and single-line success output.
- CLI help for the new group, consistent with existing commands.

### Out of Scope

- Any lifecycle control over runtime state: no clean/wipe command, no changes to `--clean` in build/pipeline.
- Listing or enumerating pipelines/builds that have existing state.
- Archive extraction or restore (unpacking on another machine).
- Changes to the runtime location formula, identity rules, or the existing build/pipeline commands.
- Configurability of runtime locations (no config keys, no environment overrides).
- A bulk `--all` archiving mode (explicitly rejected during definition).
- Container involvement, archive content filters/exclusions, size limits.

## Success Criteria

- **SC1.** From a project working directory, `goga runtime build` prints exactly one stdout line equal to the directory `goga build` actually uses for its state for this project and branch.
- **SC2.** `goga runtime pipeline <name>` prints exactly one stdout line equal to the directory `goga pipeline` uses for that pipeline; names containing `:` match the run-time sanitized directory.
- **SC3.** Path commands return the deterministic path even when no run has ever happened, and create/modify nothing on disk.
- **SC4.** `goga runtime archive` with the build target produces a `.tar.gz` that opens with standard tools on a machine without goga and contains the full contents of the build artifacts directory with the same relative structure.
- **SC5.** `goga runtime archive` with a named pipeline target does the same for that pipeline's artifacts directory.
- **SC6.** Archiving leaves the source state unmodified.
- **SC7.** On success, `archive` prints exactly one stdout line — the created archive's path — and the file exists at that path.
- **SC8.** Archiving a missing target fails with a clear error naming the missing path, a non-zero exit, and no archive file created.
- **SC9.** A default-name collision is refused without overwriting, with a non-zero exit.
- **SC10.** Usage errors (missing pipeline name; missing or duplicate archive target selection) produce usage errors with non-zero exits.
