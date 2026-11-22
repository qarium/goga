# Runtime commands: host-side path queries and single-target archiver (`goga runtime`)

## Current State

The runtime location identity is owned by the pure leaf cell `goga/runtime`:
`resolve_runtime_dir(purpose, *suffix_parts)` composes
`~/.goga/runtime/<purpose>/<normalized_project>/<branch>/<*suffix_parts>`
from two atomic helpers — `normalize_project_path` (leading slash dropped,
every `/` replaced with `-`) and `resolve_git_branch` (slugified current git
branch, literal `default` fallback outside a repository / detached HEAD /
git missing). Everything there is pure: paths are returned, nothing is ever
created on disk.

`goga build` computes its state directory as `resolve_runtime_dir("builds")`
and bind-mounts it into the container at `/workspace/.ralphex`;
`goga pipeline` computes
`resolve_runtime_dir("pipelines", <name>.replace(":", "-"))` — the
`:` → `-` sanitization lives on the pipeline command side, at the exact
place the host path segment is built.

The CLI never reveals these locations: no command prints them, no archiving
code exists anywhere in the project, and the `--clean` flags of build and
pipeline destroy the state irrecoverably. Users reverse-engineer the
internal formula and hand-roll archives to inspect, report, back up, or move
run state.

Commands are registered by re-export through the `goga/commands` facade and
`app.add_command(...)` in `goga/cli.py`. In-project precedents:
`goga history` — a click group carrying a group-level option (`-y/--year`)
before the subcommand token; `goga history path` — the one-line stdout
scripting contract.

## Description

Add a host-side, stateless top-level command group `goga runtime` with three
subcommands, run from the project working directory. Behavior is fully fixed
by this topic's PRD (R1–R18) and ADR; both are normative for this task.

1. **`goga runtime build`** — prints exactly one stdout line: the absolute
   host path of the build artifacts directory for the current project and
   effective branch. No side effects; the path is printed even when the
   directory does not yet exist (R3, R5).
2. **`goga runtime pipeline <name>`** — the same one-line query for a named
   pipeline's artifacts directory; `<name>` is sanitized `:` → `-` exactly
   as at run time, so the printed path is the directory the run actually
   uses. A missing `<name>` is a usage error (R4); a `<name>` starting with
   `-` is a clean error (ADR).
3. **`goga runtime archive`** — packages exactly one target per invocation:
   the build artifacts (`-b/--build`) or one named pipeline's artifacts
   (`-p/--pipeline <name>`), mutually exclusive flags with no positional
   target; none or both is a usage error (R6). The full recursive contents
   of the target directory go into one `.tar.gz` (R7, R8) via Python stdlib
   `tarfile` + gzip in-process, special files preserved as encountered — no
   dereference, no content filters. The archive holds a single wrapper root
   directory `goga-runtime-<target>-<branch>/` so a bare extraction cannot
   scatter files (ADR). By default it is written to the current working
   directory as `goga-runtime-<target>-<branch>.tar.gz` (R9); an existing
   file under that default name is a refused collision pointing to `-o`
   (R11). `-o/--output` takes an explicit destination that may overwrite an
   existing file (R10); an `-o` naming an existing directory, or an `-o`
   with a missing parent directory, is a clean error — no implicit `mkdir`
   (ADR). A mid-packaging failure removes the partial archive file (ADR). An
   existing but empty target directory is packaged successfully; only a
   missing target directory is an error reporting the missing path, with no
   archive file created (R13, ADR). Success prints exactly one stdout line —
   the absolute path of the created archive (R12).
4. **Group option `-b/--branch <name>`** — placed before the subcommand (as
   `-y/--year` on `goga history`). The effective branch is the explicit
   value slugified by the same `/` → `-` rule, with no git validation (the
   formula stays pure and git-free; state of a deleted branch is a
   legitimate archive target; typos surface as `archive`'s missing-target
   error). Without the option the branch is git-derived; the `default`
   fallback applies only when the option is absent and derivation fails; an
   empty value means "not given" (ADR).
5. **In-image refusal** — inside the goga image the state does not live by
   the runtime formula, so every `runtime` subcommand fails there with a
   clean "host-side only" error. The detection mechanism is a design-stage
   concern (ADR); `goga/docker` exposes `is_in_docker` as an available fact.
6. **CLI conventions** — a bare `goga runtime` prints help and exits
   non-zero (the click group default — exit 2 on click 8.5.1, matching a
   bare `goga history`; corrected at design review: the original exit-0
   assumption did not hold); all
   errors are human-readable messages on stderr with non-zero exits; stdout
   is reserved for the single result line in every command (R15, ADR); CLI
   help is consistent with the existing goga commands (R18).

The short alias `-b` deliberately carries two meanings — group-level
`--branch` and `archive`'s `--build`; click binds group options only before
the subcommand token and subcommand options only after it, so the parse
positions are disjoint and can never collide (ADR, accepted human-only
ambiguity).

Path subcommands stay pure queries: no `-a/--archive` shortcut and no
tree/listing output — rejected in the ADR.

## Scope

**In scope:**

- The new top-level `goga runtime` command group with subcommands `build`,
  `pipeline <name>`, and `archive` (exactly one target per invocation).
- The group-level `-b/--branch <name>` option and its slugification /
  fallback semantics.
- Deterministic archive naming, the wrapper-root archive layout, the
  `-o/--output` destination override, and the collision behavior.
- Strict destination semantics: existing directory under `-o` is an error;
  missing `-o` parent is an error; partial archives are removed on failure.
- The "host-side only" in-image refusal for all `runtime` subcommands.
- Failure behavior: usage errors, missing-target errors,
  unwritable-destination errors, single-line success output.
- CLI help for the new group, consistent with existing commands.

**Out of scope:**

- Any lifecycle control over runtime state: no clean/wipe command, no
  changes to `--clean` in build/pipeline.
- Listing or enumerating pipelines/builds that have existing state.
- Archive extraction or restore.
- Changes to the runtime location formula, identity rules, or the existing
  build/pipeline commands.
- Configurability of runtime locations (no config keys, no environment
  overrides).
- A bulk `--all` archiving mode.
- Container involvement, archive content filters/exclusions, size limits.
- Modifiers on path subcommands (`-a/--archive` shortcut, tree/listing
  output).
- Code placement decisions (cells, contracts, wiring) — design/prototype
  stage.

## Acceptance Criteria

- From a project working directory, `goga runtime build` prints exactly one
  stdout line equal to the directory `goga build` actually uses for its
  state for this project and effective branch.
- `goga runtime pipeline <name>` prints exactly one stdout line equal to the
  directory `goga pipeline` uses for that pipeline; names containing `:`
  match the run-time sanitized directory.
- Path commands return the deterministic path even when no run has ever
  happened, and create/modify nothing on disk.
- `goga runtime archive` with the build target produces a `.tar.gz` openable
  with standard tools on a machine without goga, containing the full
  recursive contents of the build artifacts directory under the single
  wrapper root `goga-runtime-<target>-<branch>/`, with the same relative
  structure and special files preserved as encountered; the same holds for
  a named pipeline target.
- Archiving leaves the source state unmodified.
- On success, `archive` prints exactly one stdout line — the created
  archive's absolute path — and the file exists at that path.
- Archiving a missing target fails with a clear error naming the missing
  path, a non-zero exit, and no archive file created; an existing but empty
  target directory is packaged successfully.
- A default-name collision is refused without overwriting, with a non-zero
  exit and a pointer to `-o`.
- An explicit `-o` destination may overwrite an existing file; `-o` naming
  an existing directory fails cleanly; a missing `-o` parent fails cleanly
  with no implicit `mkdir`; an unwritable destination (the default name in
  a read-only working directory, or an `-o` path without write permission)
  fails cleanly with no partial archive file kept; a mid-packaging failure
  leaves no partial archive file.
- Usage errors (missing pipeline name; missing or duplicate archive target
  selection; a `<name>` starting with `-`) produce usage errors with
  non-zero exits.
- `--branch <name>` overrides the branch segment as the slugified value
  (same `/` → `-` rule) addressing the directory the run on that branch
  created; when absent, the git-derived branch applies with the `default`
  fallback only on derivation failure; an empty value is treated as not
  given; no git validation is performed.
- `goga runtime -b <name> archive -b` parses with both `-b` meanings bound
  at their own levels (group vs subcommand).
- Inside the goga image, every `runtime` subcommand fails with a clean
  "host-side only" error.
- A bare `goga runtime` prints help and exits non-zero (the click group
  default — exit 2 on click 8.5.1, matching a bare `goga history`;
  corrected at design review: the original exit-0 assumption did not hold).
- All errors are human-readable on stderr with non-zero exits; stdout stays
  reserved for the single result line in all commands.

## Stack

- **Frameworks:** click (existing project CLI framework)
- **Libraries:** Python stdlib `tarfile` + gzip, in-process — no new
  third-party dependencies, no `pyproject.toml` changes
- **Infrastructure:** none — host-side only; no containers are launched and
  no container runtime is required (R17)
- **Testing:** pytest with `CliRunner`, ruff (project conventions)

## External Dependencies

| Component | Usage file                          | Status           |
|-----------|-------------------------------------|------------------|
| click     | `.goga/usages/cooks/click.md`       | existing (updated this task: option positioning in nested groups) |
| tarfile   | `.goga/usages/cooks/tarfile.md`     | created this task |

Synced usage files are managed by `goga usages sync` — reference them read-only, never create or update them in the task.

## Risks and Constraints

- **Branch override integration.** `resolve_runtime_dir` derives the branch
  internally (via `resolve_git_branch`) and accepts no explicit branch
  parameter. The `--branch` override requires the formula reachable with an
  explicit branch segment; whether that is a parameter extension of
  `resolve_runtime_dir`, a new routine in `goga/runtime`, or composition of
  the atomic helpers at the command layer is a design-stage decision. No
  second, divergent path scheme may appear.
- **Path-composition purity boundary.** Path composition stays a
  side-effect-free capability of the existing runtime utilities; effects
  (archive file creation, packaging) belong to the command layer.
- **In-image detection.** The refusal mechanism is unfixed (ADR);
  `goga/docker.is_in_docker` is an available fact, not a settled choice.
- **Observer safety.** `runtime` commands never create, modify, or delete
  runtime state; the state lifecycle (including `--clean`) stays owned by
  build/pipeline.
- **Snapshot consistency** while a run is actively writing state is a
  documented limitation, not an enforced precondition.
- **Non-deterministic archive bytes** (metadata preserved as encountered) —
  determinism of the name and layout is the contract; nothing requires
  reproducible bytes.
- **Location identity is fixed and non-configurable** — formula-derived
  only; no configuration surface is introduced.
- Python 3.10+ compatibility (project convention).

## Scope Estimate

Single task — no decomposition. One cohesive CLI group over one existing
formula cell with no new subsystems and no new external dependencies;
additional topics are not created.

## Existing Architecture

- **`goga/runtime`** (pure leaf, no dependencies) — owner of the single
  path formula. Existing consumers: `goga/commands/build`
  (`resolve_runtime_dir("builds")`) and `goga/commands/pipeline`
  (`resolve_runtime_dir("pipelines", <sanitized name>)`), both importing
  `resolve_runtime_dir` with the `runtime-paths` usage. The new command
  group consumes the same location identity — never a second scheme.
- **`goga/commands` facade + the root `goga` cell (`goga/cli.py`)** —
  registration surface: the new `runtime` command group is re-exported
  through the facade and added via `app.add_command(...)` in `goga/cli.py`
  (owned by the root `goga` cell, whose `app` contract carries the full
  command table), as every existing command.
- **`goga/docker`** — exposes `is_in_docker`; a candidate fact for the
  in-image refusal, mechanism undecided by the ADR.
- **`goga/commands/history`** — the click-group with a group-level option
  and the one-line stdout query precedents the new group follows.
- Placement of the new code (cells, contracts, wiring) is deliberately a
  design/prototype-stage decision (ADR); this task fixes behavior and
  constraints only.

## Notes

- Input artifacts: `prd.md` (requirements R1–R18, scope, success criteria)
  and `adr.md` (all decisions the PRD left open) in this topic directory;
  both are normative for implementation.
- The deliberate dual meaning of `-b` (group `--branch` vs `archive`'s
  `--build`) is accepted and parse-safe; documented in the click usage.
- No code examples are included in this task by stage constraint; usage
  files carry the implementation patterns (`tarfile`, `click`).
