# Design Document: `add-runtime-command`

Design of the `goga runtime` command group — host-side path queries and a
single-target archiver over the shared runtime formula — from the CODEMANIFEST
changes materialized by the apply-architecture stage.

Behavioral sources (normative): `prd.md` (R1–R18), `adr.md`, `task.md` in this
topic directory. Contract sources: `goga/runtime/CODEMANIFEST`,
`goga/commands/runtime/CODEMANIFEST`, `goga/commands/CODEMANIFEST`,
`goga/CODEMANIFEST` (as of this design).

Verified library runtime: click 8.5.1, Python stdlib `tarfile` (Python 3.10+
per project convention).

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/runtime/CODEMANIFEST`: `resolve_runtime_dir` signature extended with a
  keyword-only `branch: str | None = None` parameter (explicit-or-derived branch
  segment, slugified by the same `/` → `-` rule, git-free when explicit); global
  `Annotations` paragraph and footer `Description` updated accordingly.
- `goga/commands/runtime/CODEMANIFEST`: **new** — the `runtime(branch)` click
  group entity with `build` / `pipeline` / `archive` methods plus five support
  routines; Imports from `goga/runtime` (`resolve_runtime_dir`,
  `resolve_git_branch`, usage `runtime-paths`) and `goga/docker` (`is_in_docker`);
  Usages `convention`, `click`, `tarfile`.
- `goga/commands/CODEMANIFEST`: facade — new Imports entry (`runtime` + usages
  `path-queries`, `archive` from `goga/commands/runtime`), two practice
  paragraphs in the global `Annotations`, `->runtime: {}` embedding.
- `goga/CODEMANIFEST`: root — `runtime` added to the `goga/commands` Types list
  and to the `app()` Commands list.

### New Entities

All in `goga/commands/runtime`:

- `runtime(branch: str | None = None)` — Entity, `location: runtime.py`. The
  click.Group container carrying the branch scope shared by every subcommand.
  Methods: `build() -> exit_code:int`, `pipeline(name: str) -> exit_code:int`,
  `archive(build: bool = False, pipeline: str | None = None, output: str | None = None) -> exit_code:int`.
- `resolve_effective_branch(branch: str | None = None) -> segment: str` —
  Routine, `location: targets.py`.
- `resolve_build_target_dir(branch_segment: str) -> target_dir: Path` — Routine,
  `location: targets.py`.
- `sanitize_pipeline_name(name: str) -> sanitized: str` — Routine,
  `location: targets.py`.
- `resolve_pipeline_target_dir(pipeline_name: str, branch_segment: str) -> target_dir: Path` —
  Routine, `location: targets.py`.
- `resolve_archive_destination(archive_stem: str, output: str | None = None) -> destination: Path` —
  Routine, `location: archive.py`.
- `package_runtime_archive(target_dir: Path, wrapper_root: str, destination: Path) -> archive_path: Path` —
  Routine, `location: archive.py`.

### Changed Entities

- `resolve_runtime_dir` (`goga/runtime`, `location: paths.py`) — signature
  `(...suffix_parts: str, branch: str | None = None)`. Behavior for existing
  callers (no `branch`) is bit-identical: the parameter defaults to `None`,
  existing positional calls `resolve_runtime_dir("builds")` and
  `resolve_runtime_dir("pipelines", name)` bind unchanged.

### Deleted Entities

None.

### Usages and Annotations Changes

- `goga/runtime/.usages/runtime-paths.md` — extended: explicit-branch facade
  section ("Addressing another branch's state"), updated API list,
  preconditions, side effects, failure modes.
- `goga/commands/runtime/.usages/path-queries.md` — **new** (one functional
  domain: path queries).
- `goga/commands/runtime/.usages/archive.md` — **new** (one functional domain:
  archiving).
- `goga/commands/.usages/cli-commands.md` — 18 → 19 commands, `runtime` in all
  import/registration snippets and the command table.
- `.goga/usages/cooks/click.md` — new section "Option positioning in nested
  groups" (the dual `-b` rationale).
- `.goga/usages/cooks/tarfile.md` — **new** cook (w:gz creation, wrapper root
  via `arcname`, failure cleanup, built-in guards).
- Global `Annotations` of `goga/commands` — two new practice paragraphs
  (`path-queries`, `archive`).

## Applied Fixes

### Fixed CODEMANIFEST Defects

Both defects were surfaced by Phase-4 tracing (empirical verification against
the installed libraries) and fixed with user approval during this design:

1. `goga/commands/runtime/CODEMANIFEST`, entity `runtime(branch...)`:
   - **Before**: "A bare group invocation prints help and exits 0."
   - **After**: "A bare group invocation prints help and exits non-zero — the
     click group default, matching a bare goga history invocation."
   - Reason: contract-vs-reality inconsistency. The ADR assumed the click group
     default is exit 0; on click 8.5.1 a bare group prints help and exits **2**,
     and the cited precedent — a bare `goga history` (and bare `goga`) — exits 2
     today (verified with CliRunner). The PRD requires only non-zero exits for
     errors (R15) and consistency with existing commands (R18); a standard
     `@click.group()` would have violated the manifest's own "exits 0" claim.
     The reference to `goga history` is plain text (no backticks) — a backtick
     reference must resolve inside the current manifest (`annotation_links_exists`
     lint rule).
2. `goga/commands/runtime/CODEMANIFEST`, routine `package_runtime_archive`,
   Requirements — one line added:
   - "The failure cleanup removes only an archive file this routine created — a
     failure before the destination is opened leaves any pre-existing file at
     the destination untouched."
   - Reason: the `tarfile` cook's cleanup snippet (`except BaseException:
     archive_path.unlink(missing_ok=True); raise`) applied verbatim deletes a
     pre-existing destination file when the failure happens at open (reachable
     via explicit `-o` at a read-only file: `PermissionError` at open, unlink
     succeeds because the *directory* is writable). The strict-destination
     semantics ("an existing file under an explicit destination is legitimate")
     require the guarded cleanup; the manifest is now unambiguous.

Validation after fixes: `goga lint` → 94 cells, 0 errors; `goga schema` resolves
the new cell with exactly the planned dependency map.

### Fixed at Design Review

All five review remarks were verified empirically (click 8.5.1 CliRunner
probes; tarfile/pathlib live experiments) and applied with user approval:

1. **Empty pipeline segment** (High, design + manifest) — an empty NAME
   (`["pipeline", ""]`) or empty `-p` value reaches the callbacks, and path
   composition silently drops an empty suffix part (`Path("/a/b") / ""` →
   `/a/b`), so without a guard the branch-level directory is printed as a
   pipeline's directory — and `archive -p ""` packages the whole branch
   state under stem `goga-runtime--<segment>`. The `pipeline` and `archive`
   command layers now reject an empty name as a clean error (manifest
   Requirements/Algorithm updated); two negative tests added.
2. **OSError wrap point** (Medium, design + manifest) — the archive
   algorithm now pins the wrap: the packaging call is wrapped in
   `TRY/EXCEPT OSError → ClickException` (exit 1, no traceback), matching
   the cross-cutting rule and R15; the manifest's archive Requirements
   state it explicitly.
3. **Archive dash-guard test gap** (Test Gap) — added
   `test_runtime_archive_pipeline_dash_value_is_clean_error`; the dash
   value is reachable via the plain `-p -weird` form (verified: click
   takes a dash-leading token as the option's value) and via
   `--pipeline=-weird`.
4. **Stale exit-0 claims in behavioral sources** (Low) — `task.md`
   (description item 6 and the acceptance criterion) and `adr.md`
   (CLI-conventions decision) corrected to the non-zero click group
   default (exit 2 on click 8.5.1), keeping the records consistent with
   Fix 1 of this document.
5. **tarfile cook cleanup snippet** (Low) — `.goga/usages/cooks/tarfile.md`
   now teaches the guarded cleanup (unlink only after a successful open),
   removing the source of the defect Fix 2 had to guard against.

## Entity Interaction and Data Flow

### Interaction Diagram

```
                         CLI argv
                            │
                goga/cli.py app (root group)
                            │ app.add_command(runtime)
                            ▼
        goga/commands facade ── re-export ──► runtime (click.Group)
                                                  │ ctx.obj = _RuntimeScope(branch)
                     ┌────────────────────────────┼─────────────────────────────┐
                     ▼                            ▼                             ▼
              build (runtime.py)          pipeline (runtime.py)         archive (runtime.py)
                     │                            │                             │
                     │  is_in_docker() ── refuse inside image (all three) ◄─────┤
                     ▼                            ▼                             ▼
          resolve_effective_branch(branch)  [same]                  [same]
                     │                            │                             │
                     ▼                            ▼                             ▼
          resolve_build_target_dir   resolve_pipeline_target_dir    target label: "build" /
                     │                ├─ sanitize_pipeline_name     sanitize_pipeline_name(name)
                     │                └─ resolve_runtime_dir                   │
                     │        ("pipelines", sanitized,                  stem = "goga-runtime-"
                     │         branch=segment)                          <label>-<segment>
                     ▼                                                     ▼
             resolve_runtime_dir("builds", branch=segment)   resolve_archive_destination(stem, output)
                     │                                                     │
                     ▼                                                     ▼
               click.echo(target_dir)                       package_runtime_archive(
                                                              target_dir, wrapper_root=stem,
                                                              destination)
                                                                                     │
                                                                                     ▼
                                                                          click.echo(archive_path)
```

### Data Flows

1. **Path query (build)**: argv → group callback stores `branch: str | None` in
   `ctx.obj` (`_RuntimeScope`) → `build` reads scope.branch →
   `resolve_effective_branch` (`str | None` → `str` segment) →
   `resolve_build_target_dir(segment)` (`str` → `Path`) → `click.echo(Path)` —
   exactly one stdout line.
2. **Path query (pipeline)**: same, with `name: str` → dash-check →
   `resolve_pipeline_target_dir(name, segment)` → `Path` → echo.
3. **Archive**: scope.branch → segment → target selection (`build` flag XOR
   `pipeline` value) → target dir (`Path`) + existence check → stem (`str`) →
   `resolve_archive_destination(stem, output)` (`Path`) →
   `package_runtime_archive(target_dir, stem, destination)` (`Path`) → echo.

### Entity Dependencies

Implementation order (leaves first): `goga/runtime/paths.py` (add `branch`) →
`goga/commands/runtime/targets.py` → `goga/commands/runtime/archive.py` →
`goga/commands/runtime/runtime.py` (group; imports `.targets`/`.archive`) →
`goga/commands/runtime/__init__.py` → `goga/commands/__init__.py` (facade
re-export) → `goga/cli.py` (`app.add_command(runtime)`).

## Code Stack Trace

All traces verified against the actual implementation files and library
behavior (click 8.5.1 via CliRunner experiments; tarfile via a live
self-archiving experiment).

### Trace: `runtime` (group constructor/callback)

#### Chain

1. **Input**: `goga runtime [-b <branch>] <subcommand> ...` — click invokes the
   group callback before dispatching the subcommand.
2. **Step**: `@click.group()` + `@click.option("--branch", "-b", default=None)`
   + `@click.pass_context`; callback does `ctx.ensure_object(_RuntimeScope)`
   and stores `branch` → checkpoint: verified empirically — group options bind
   only before the subcommand token; `["-b", "main", "archive", "-b"]` parses
   with group branch `"main"` and subcommand `build=True` (dual `-b` disjoint).
   **passed**
3. **Step**: empty `--branch=` arrives as `""` (verified) → treated as
   "not given" downstream in `resolve_effective_branch`. **passed**
4. **Step**: bare `goga runtime` (no subcommand): click prints help, exit code
   2 (verified on click 8.5.1; identical to bare `goga history` and bare `goga`).
   **passed** (after Fix 1 — manifest aligned with reality)
5. **Output**: `ctx.obj` carries the branch scope; subcommands registered via
   `@runtime.command(...)` decorators (the `history` pattern, `history.py:54-79`).

#### Checkpoint Summary

- Dual `-b` parse positions: **passed** (empirical CliRunner proof).
- Group option placement before subcommand token: **passed** (`history`
  precedent + cook section "Option positioning in nested groups").
- Bare-group exit code: **defect found → fixed** (ADR assumption wrong for
  click 8.5.1; manifest corrected).

### Trace: `runtime.build`

#### Chain

1. **Input**: `runner.invoke(runtime, ["build"])` (or `["-b", "release/1.2", "build"]`).
2. **Step**: `is_in_docker()` — `os.environ.get("GOGA_DOCKER") == "1"`
   (`goga/docker/env.py:9-22`) → `True` ⇒ `click.ClickException` (stderr,
   exit 1) → checkpoint: imported type exists, marker rule verified. **passed**
3. **Step**: `resolve_effective_branch(scope.branch)` → `str` segment →
   checkpoint: `str | None` → `str`. **passed**
4. **Step**: `resolve_build_target_dir(segment)` → `resolve_runtime_dir("builds",
   branch=segment)` → checkpoint: purpose `"builds"` matches the run's actual
   call `goga/commands/build/build.py:274` (`resolve_runtime_dir("builds")`) —
   same directory for the same branch. **passed**
5. **Step**: `click.echo(target_dir)` — one line; `Path` echoes as the absolute
   posix path (`Path.home()`-rooted, absolute). **passed**
6. **Output**: stdout = the absolute path; nothing created on disk (the formula
   is pure — `paths.py` performs no mkdir). **passed**

#### Checkpoint Summary

- Type flow `str → Path → echo`: **passed**.
- Location parity with `goga build`: **passed** (same purpose, same formula).

### Trace: `runtime.pipeline`

#### Chain

1. **Input**: `runner.invoke(runtime, ["pipeline", "pybuggy:api-feature"])`.
2. **Step**: missing NAME ⇒ click UsageError, exit 2 (verified: "Error: Missing
   argument 'NAME'") — a non-zero usage error. **passed**
3. **Step**: empty-or-`startswith("-")` guard — the dash form is reachable
   via the `--` separator (`["pipeline", "--", "-weird"]` delivers
   `name="-weird"`, verified); without `--`, click itself rejects `-weird`
   as an unknown option (exit 2). The empty form arrives directly
   (`["pipeline", ""]` delivers `name=""`, verified); path composition
   silently drops an empty suffix part (`Path("/a/b") / ""` → `/a/b`,
   verified), so without the guard the branch-level directory would be
   printed as the pipeline's directory. This is the project's
   argv-parsability precedent (`pipeline.py:305-319` step 2.5). **passed**
4. **Step**: `resolve_effective_branch` → segment. **passed**
5. **Step**: `resolve_pipeline_target_dir(name, segment)` →
   `sanitize_pipeline_name(name)` (`:` → `-`) → `resolve_runtime_dir("pipelines",
   sanitized, branch=segment)` → checkpoint: parity with the run's actual
   composition `run_pipeline_container.py:153`
   (`resolve_runtime_dir("pipelines", pipeline_name.replace(":", "-"))`) — the
   printed path is the directory the run actually uses. **passed**
6. **Step**: `click.echo(target_dir)`. **passed**
7. **Output**: one stdout line; no filesystem effects. **passed**

#### Checkpoint Summary

- Sanitization parity with the run: **passed** (verified at source).
- Dash-leading name: **passed** (both click-native and `--`-reached paths clean).

### Trace: `runtime.archive`

#### Chain

1. **Input**: `runner.invoke(runtime, ["archive", "-b"])` (or `-p NAME`,
   `-o DEST`, group `-b BRANCH` before `archive`).
2. **Step**: `is_in_docker()` refusal — as `build`. **passed**
3. **Step**: target selection validation — `build XOR pipeline`; neither or
   both ⇒ `click.ClickException` (exit 1, message on stderr). An empty or
   dash-leading `-p` value ⇒ clean error (same argv rule: the empty value
   would address the branch-level directory, `Path / ""` drops the segment
   — verified). Empirical note: a bare `-p` with no value is consumed by
   click itself as a missing-option usage error; the guard covers the plain
   (`-p -weird` — click delivers a dash-leading token as the value,
   verified), `=`-attached (`--pipeline=-weird`), and empty (`-p ""`)
   forms. **passed**
4. **Step**: `resolve_effective_branch(scope.branch)` → segment. **passed**
5. **Step**: target resolution — build: `resolve_build_target_dir(segment)`,
   label `"build"`; pipeline: `resolve_pipeline_target_dir(name, segment)`,
   label `sanitize_pipeline_name(name)`. → checkpoint: `Path` + `str`. **passed**
6. **Step**: target existence — `not target_dir.is_dir()` ⇒ `ClickException`
   naming the path, no archive created; an existing empty directory proceeds. **passed**
7. **Step**: `stem = f"goga-runtime-{label}-{segment}"` — shared base of the
   default filename and the wrapper root. → checkpoint: `str`. **passed**
8. **Step**: `resolve_archive_destination(stem, output)` → `destination: Path`
   (see its own trace). **passed**
9. **Step**: `package_runtime_archive(target_dir, wrapper_root=stem,
   destination)` → `archive_path: Path` (see its own trace). **passed**
10. **Step**: `click.echo(archive_path)` — the absolute path, one line. **passed**
11. **Output**: stdout = archive path; exactly one new artifact on disk; source
    untouched. **passed**

#### Checkpoint Summary

- Mutual exclusion: **passed** (one check, ClickException).
- Stem/label/segment type flow: **passed**.

### Trace: `resolve_effective_branch`

#### Chain

1. **Input**: `branch: str | None` (the raw group option; `None` or `""` =
   not given).
2. **Step**: non-empty → `return branch.replace("/", "-")` — no git, no
   validation; idempotent for already-slugified input (`"feature-x"` passes
   through). → checkpoint: same rule as `resolve_git_branch`
   (`paths.py:43` — `.replace("/", "-")`). **passed**
3. **Step**: empty/None → `resolve_git_branch()` — slugified current branch or
   `"default"` (never raises; `FileNotFoundError` → `"default"`,
   `paths.py:39-40`; only `PermissionError`-class subprocess failures
   propagate — pre-existing leaf behavior, outside this cell's contract). **passed**
4. **Output**: `segment: str` — a single filesystem-safe component. **passed**

### Trace: `resolve_build_target_dir`

#### Chain

1. **Input**: `branch_segment: str` (from `resolve_effective_branch`).
2. **Step**: `resolve_runtime_dir("builds", branch=branch_segment)` — keyword
   call; no suffix parts. → checkpoint: `Path`. **passed**
3. **Output**: `target_dir: Path`, absolute; pure. **passed**

### Trace: `sanitize_pipeline_name`

#### Chain

1. **Input**: `name: str`.
2. **Step**: literal `name.replace(":", "-")` — one-to-one, no collapsing, no
   trimming. → checkpoint: identical to `run_pipeline_container.py:153`. **passed**
3. **Output**: `sanitized: str` — host path segment and archive target label. **passed**

### Trace: `resolve_pipeline_target_dir`

#### Chain

1. **Input**: `pipeline_name: str`, `branch_segment: str`.
2. **Step**: `sanitize_pipeline_name(pipeline_name)` → suffix. **passed**
3. **Step**: `resolve_runtime_dir("pipelines", sanitized, branch=branch_segment)`. **passed**
4. **Output**: `target_dir: Path` — the directory the run actually uses. **passed**

### Trace: `resolve_runtime_dir` (changed; `goga/runtime/paths.py`)

#### Chain

1. **Input**: `purpose: str`, `*suffix_parts: str`, `branch: str | None = None`
   (keyword-only after `*args`).
2. **Step**: `segment = branch.replace("/", "-") if branch else
   resolve_git_branch()` — `""` is falsy ⇒ derived form; no git subprocess when
   explicit. → checkpoint: one formula, no second scheme — the explicit branch
   produces exactly what the git-derived form produces for that branch. **passed**
3. **Step**: `Path.home() / ".goga" / "runtime" / purpose / normalized /
   segment / *suffix_parts`. **passed**
4. **Output**: absolute `Path`; no filesystem effects. Existing callers
   (`build.py:274`, `run_pipeline_container.py:153`) pass no `branch` and are
   unaffected (positional binding unchanged, keyword-only addition). **passed**

### Trace: `resolve_archive_destination`

#### Chain

1. **Input**: `archive_stem: str`, `output: str | None`.
2. **Step** (default, `output is None`): `destination = Path.cwd() / f"{stem}.tar.gz"`;
   `destination.exists()` (any existing file) ⇒ `ClickException`-equivalent
   clean error naming the path and pointing to `-o/--output`. → checkpoint:
   collision check happens before any packaging; the default path never
   pre-exists at packaging time. **passed**
3. **Step** (explicit `output`): resolve `Path(output)` relative to cwd when not
   absolute (`Path.cwd() / output`); then:
   - `destination.is_dir()` ⇒ clean error;
   - `not destination.parent.is_dir()` ⇒ clean error (no implicit mkdir);
   - existing file ⇒ legitimate (overwrite intent).
   **passed**
4. **Output**: absolute `destination: Path`; nothing written (validation only). **passed**

Edge: `output=""` — non-None ⇒ explicit branch; `Path("")` normalizes to `.`,
`Path.cwd() / ""` = cwd, which `is_dir()` ⇒ clean error. Acceptable and
consistent with "existing directory under -o is an error".

### Trace: `package_runtime_archive`

#### Chain

1. **Input**: `target_dir: Path` (exists — caller-checked), `wrapper_root: str`
   (the stem), `destination: Path` (validated).
2. **Step**: `tarfile.open(destination, "w:gz")` — creates/truncates the file
   at open; an unwritable destination raises `OSError` here, before any data is
   written (cook-documented, tarfile semantics). Failure at this point must
   **not** unlink a pre-existing destination file (Fix 2). **passed**
3. **Step**: `tar.add(target_dir, arcname=wrapper_root)` — `recursive=True`
   default adds the full tree; `dereference=False` default preserves symlinks;
   no filter ⇒ full contents as encountered; the root member is named
   `wrapper_root/` so the tree lands under one directory. Verified live: an
   archive written *inside* the packaged tree does not include itself
   (tarfile's self-archiving guard). **passed**
4. **Step**: close (the `with` block), return `destination` (absolute). **passed**
5. **Step** (failure after successful open): close, `destination.unlink(missing_ok=True)`,
   re-raise — no partial file kept. Failure before open: re-raise without
   unlink (Fix 2 — a file the routine did not create is not "partial archive"). **passed**
6. **Output**: `archive_path: Path`; the file exists there on success. **passed**

#### Checkpoint Summary

- Wrapper-root layout: **passed** (verified: members `["<root>", "<root>/a.txt"]`).
- Self-inclusion: **passed** (verified guard).
- Cleanup semantics: **defect found → fixed** (guarded unlink).

## Algorithm Design

### `runtime` (group) — implementation shape (`runtime.py`)

**Responsibility**: click.Group container; carries the branch scope; registers
the three subcommands.

**Algorithm:**
```
1. module runtime.py — imports: click; from ..docker import is_in_docker
   (relative per `convention`); from .targets import ...; from .archive import ...
2. dataclass(kw_only=True) _RuntimeScope: branch: str | None = None
   (the `history` pattern — `_HistoryScope`, history.py:24-28)
3. @click.group() + @click.option("--branch", "-b", default=None, help=...)
   + @click.pass_context → def runtime(ctx, branch=None):
   ctx.ensure_object(_RuntimeScope); ctx.obj.branch = branch
   docstring = the --help text (convention CLI docstring rule:
   no Args/Returns/Raises; document both -b meanings)
4. subcommands via @runtime.command("build" | "pipeline" | "archive"),
   each @click.pass_obj → def build(scope): ...
5. errors: raise click.ClickException("...") → stderr "Error: ...", exit 1
6. result line: click.echo(path); return (click derives exit 0)
```

**Errors:** every documented failure is a `ClickException` (exit 1) except
click-native usage failures (missing NAME, unknown option) which exit 2 — the
project-wide CLI behavior; the manifest's "`exit_code`: 0 on success, 1 on
error" phrasing follows the project's established manifest convention
(`history`, `topics`) meaning success vs failure, with click's usage errors (2)
being the framework's own non-zero usage exit.

**Edge cases:** bare group → help, exit 2 (as `goga history`); `-b` before the
subcommand binds the group, after it binds the subcommand (verified disjoint).

### `runtime.build`

**Algorithm:**
```
1. IF is_in_docker(): raise ClickException(host-side-only message) → exit 1
2. segment = resolve_effective_branch(scope.branch)
3. target_dir = resolve_build_target_dir(segment)
4. click.echo(target_dir) → exactly one stdout line
```

**Errors:** in-image refusal → `ClickException`, exit 1.

**Edge cases:** directory never created by the query (prints even when absent).

### `runtime.pipeline`

**Algorithm:**
```
1. IF is_in_docker(): refuse (as build)
2. IF name == "" OR name.startswith("-"):
     raise ClickException(f"invalid pipeline name {name!r}")
   (the pipeline.py:313 precedent; the dash form is reachable via `--`
   separator; the empty form arrives directly — click delivers an empty
   positional — and would otherwise address the branch-level directory,
   because path composition silently drops an empty suffix part)
3. segment = resolve_effective_branch(scope.branch)
4. target_dir = resolve_pipeline_target_dir(name, segment)
5. click.echo(target_dir)
```

**Errors:** missing NAME → click UsageError (exit 2); empty or dash-leading
name → `ClickException` (exit 1).

**Edge cases:** names with `:` sanitize to the run-time segment.

### `runtime.archive`

**Algorithm:**
```
1. IF is_in_docker(): refuse
2. IF (build == pipeline_given) i.e. neither or both:
     raise ClickException("exactly one target: -b/--build or -p/--pipeline NAME")
   IF pipeline is not None and (pipeline == "" OR pipeline.startswith("-")):
     raise ClickException(f"invalid pipeline name {pipeline!r}")
   (the empty value would address the branch-level directory — path
   composition silently drops an empty suffix part — and package the whole
   branch state)
3. segment = resolve_effective_branch(scope.branch)
4. IF build: target_dir = resolve_build_target_dir(segment); label = "build"
   ELSE:     target_dir = resolve_pipeline_target_dir(pipeline, segment)
             label = sanitize_pipeline_name(pipeline)
5. IF not target_dir.is_dir():
     raise ClickException(f"target directory does not exist: {target_dir}")
   (existing-but-empty directory proceeds)
6. stem = "goga-runtime-{label}-{segment}"
7. destination = resolve_archive_destination(stem, output)
8. TRY: archive_path = package_runtime_archive(target_dir, wrapper_root=stem,
                                               destination=destination)
   EXCEPT OSError:
     raise ClickException(f"cannot write archive to {destination}")
   (packaging writes a file — its OS-level failures become a clean error
   here, exit 1, no traceback)
9. click.echo(archive_path)
```

**Errors:** in-image; neither/both targets; empty or dash-leading `-p` value;
missing target (names the path, no archive created); default-name collision
(points to `-o`); destination is an existing directory; missing `-o` parent;
unwritable destination (OSError at packaging open, wrapped into a
ClickException by the command layer — exit 1, no traceback, no partial file).

**Edge cases:** explicit `-o` over an existing file = intended overwrite; empty
target directory packages successfully; `-o ""` → cwd → "existing directory"
clean error.

### `resolve_effective_branch` (`targets.py`)

**Algorithm:**
```
1. IF branch (non-empty): RETURN branch.replace("/", "-")
2. RETURN resolve_git_branch()
```

**Errors:** none of its own (the derived form never raises; unexpected
subprocess errors propagate from the leaf as-is — pre-existing leaf behavior).

**Edge cases:** `""`/`None` → derived; already-slugified input passes through
(idempotent).

### `resolve_build_target_dir`

**Algorithm:**
```
1. RETURN resolve_runtime_dir("builds", branch=branch_segment)
```

### `sanitize_pipeline_name`

**Algorithm:**
```
1. RETURN name.replace(":", "-")
```

### `resolve_pipeline_target_dir`

**Algorithm:**
```
1. sanitized = sanitize_pipeline_name(pipeline_name)
2. RETURN resolve_runtime_dir("pipelines", sanitized, branch=branch_segment)
```

### `resolve_archive_destination` (`archive.py`)

**Algorithm:**
```
1. IF output is None:
     destination = Path.cwd() / f"{archive_stem}.tar.gz"
     IF destination.exists(): raise ClickException(collision, point to -o/--output)
     RETURN destination
2. path = Path(output); destination = path if path.is_absolute() else Path.cwd() / path
   IF destination.is_dir(): raise ClickException(existing directory)
   IF not destination.parent.is_dir(): raise ClickException(missing parent, no mkdir)
   RETURN destination
```

**Errors:** collision; existing directory; missing parent. Nothing written.

**Edge cases:** relative `-o` resolves against cwd; return value absolute.

### `package_runtime_archive` (`archive.py`)

**Algorithm:**
```
1. opened = False
2. TRY:
     WITH tarfile.open(destination, "w:gz") AS tar:      # raises OSError on
         opened = True                                   # unwritable destination
         tar.add(target_dir, arcname=wrapper_root)       # recursive, no deref
3. EXCEPT BaseException:
     IF opened: destination.unlink(missing_ok=True)      # only OUR partial file
     RAISE
4. RETURN destination
```

**Errors:** `OSError` at open (unwritable) — propagated; any packaging failure —
partial file removed, error propagated. The command layer wraps both into a
`ClickException` (stderr, exit 1).

**Edge cases:** archive written inside the target tree — tarfile's self-guard
skips it (verified); symlinks stored as symlinks (`dereference=False`).

### `resolve_runtime_dir` (`goga/runtime/paths.py`) — the one changed leaf

**Algorithm:**
```
1. cwd = Path.cwd(); normalized = normalize_project_path(cwd)
2. segment = branch.replace("/", "-") IF branch ELSE resolve_git_branch()
3. runtime_dir = Path.home()/".goga"/"runtime"/purpose/normalized/segment
4. for part in suffix_parts: runtime_dir = runtime_dir / part
5. RETURN runtime_dir
```

**Edge cases:** `branch=""` ⇒ derived; keyword-only parameter keeps every
existing positional call site source-compatible.

## Cross-cutting Concerns

- **Error handling**: one strategy for the whole cell — domain/semantic errors
  are `click.ClickException` (message on stderr with the `Error: ` prefix, exit
  1); argv-form errors are either click-native usage errors (exit 2, missing
  NAME / unknown option) or explicit dash-leading checks (exit 1, the
  pipeline.py precedent). stdout is never used for errors. No exception escapes
  the command layer to the user as a traceback.
- **Validation**: strictly ordered per subcommand — in-image refusal first,
  argv parsability, target selection, branch resolution, target existence,
  destination resolution, packaging. Ordering guarantees "no archive file
  created" for every pre-target failure and "no partial kept" for packaging
  failures.
- **Logging**: none. The cell is a thin CLI surface following `history`/
  `topics` — output is the single result line; errors are user-facing
  messages. No `logging` calls (a CLI observer command has no operational log
  consumers; the convention's logging rules apply to library code).
- **Caching**: none — commands are stateless queries; repeat invocations
  recompute (deterministic by contract).
- **Concurrency**: not applicable — single-process, no shared mutable state;
  no thread-safety requirements. Snapshot consistency while a run writes its
  state is a documented limitation (ADR), not enforced.

## Usages Analysis

### `convention`
- **What it provides**: project-wide Python rules — relative imports, Google
  docstrings, the CLI-command docstring rule, dataclass `kw_only=True` models,
  test structure/mocking rules, Python 3.10+ compatibility.
- **Where used**: global `Annotations` (all entities); the `runtime` entity's
  `--help` docstring rule.
- **Why chosen**: mandatory project baseline; the `click.Group` scope dataclass
  and the test layout derive from it.
- **How exactly**: `_RuntimeScope` as `@dataclass(kw_only=True)` with
  `branch: str | None = None` (None = explicit absence); command docstrings
  omit Args/Returns/Raises; tests mirror source at
  `tests/commands/runtime/test_{runtime,targets,archive}.py`; mocks only at
  external boundaries (`subprocess.run`, `GOGA_DOCKER` env, `Path.home`).

### `click`
- **What it provides**: group/command decorators, `ctx.obj` state passing,
  option/argument surfaces, echo/ClickException error surfaces, CliRunner
  testing; the new "Option positioning in nested groups" section (dual `-b`).
- **Where used**: `runtime` entity and all three methods.
- **Why chosen**: the project CLI framework (R-stack; `history` precedent).
- **How exactly**: `@click.group()` + `@click.option("--branch","-b",default=None)`
  + `@click.pass_context` + `ctx.ensure_object(_RuntimeScope)`; subcommands via
  `@runtime.command(...)` + `@click.pass_obj`; `click.echo` for the single
  result line; `click.ClickException` for clean errors; `CliRunner` in tests.

### `tarfile`
- **What it provides**: stdlib compressed-archive creation — `w:gz` open
  semantics (truncate-at-open, OSError on unwritable), `arcname` wrapper root,
  recursive add with `dereference=False`, self-archiving guard, the
  cleanup-on-failure pattern.
- **Where used**: `package_runtime_archive`.
- **Why chosen**: ADR — stdlib, in-process, no new dependency, no PATH/platform
  variance.
- **How exactly**: `tarfile.open(destination, "w:gz")` + `tar.add(target_dir,
  arcname=wrapper_root)`; guarded cleanup — unlink only after a successful open
  (Fix 2 refines the cook's unconditional snippet for the explicit-destination
  overwrite case).

### `runtime-paths` (imported usage)
- **What it provides**: the consumer-facade pattern over the shared formula —
  fixed purpose, optional suffix, explicit branch; the path shape and purity
  guarantees.
- **Where used**: `resolve_build_target_dir`, `resolve_pipeline_target_dir`
  (annotations reference the facade pattern), global `Annotations`.
- **Why chosen**: the cell is the documented observer-consumer of `goga/runtime`.
- **How exactly**: thin delegating routines with the fixed purposes `"builds"`
  /`"pipelines"` and `branch=segment` keyword; no second path scheme.
- Path: `goga/runtime/.usages/runtime-paths.md`

### Imported types (context)
- `resolve_runtime_dir`, `resolve_git_branch` from `goga/runtime` — signatures
  verified against `goga/runtime/paths.py` (the extended signature is this
  topic's change).
- `is_in_docker` from `goga/docker` — verified at `goga/docker/env.py:9`
  (`GOGA_DOCKER == "1"`), re-exported by `goga/docker/__init__.py`.

## `.usages/` Update

### Cell: `goga/commands/runtime`

#### Existing Files — Consistency
- None (new cell).

#### New Files
- Both files exist already (created by the apply stage) and are **current**
  against the corrected manifest:
  - **`path-queries`** → `goga/commands/runtime/.usages/path-queries.md` —
    domain: the two path queries; one-line stdout contract, branch option,
    scripting patterns, failure modes. Consistent with the manifest (including
    after Fix 1 — the file never stated a bare-group exit code, so no update
    needed).
  - **`archive`** → `goga/commands/runtime/.usages/archive.md` — domain:
    archiving; single-target selection, wrapper-root naming, destination
    semantics, failure modes, non-reproducible-bytes note. Consistent with the
    manifest (including after Fix 2 — the file's "mid-packaging failure
    removes the partial archive" wording already matches the guarded reading).

### Cell: `goga/runtime`

- **`runtime-paths`** → current: documents the extended signature
  (`branch: str | None = None`), the observer section, purity guarantees.

### Cell: `goga/commands`

- **`cli-commands`** → current: 19 commands, `runtime` in every snippet and the
  table.

No `.usages/` updates required by this design beyond what the apply stage
already materialized.

## Test Stack Trace

### General Setup

- Framework: pytest + `click.testing.CliRunner` (project convention).
- Boundary mocks only: `mock.patch.object(subprocess, "run", ...)` for git,
  `monkeypatch.setenv("GOGA_DOCKER", "1")` / `monkeypatch.delenv("GOGA_DOCKER",
  raising=False)` for the image marker, `monkeypatch.chdir(tmp_path)` +
  `monkeypatch.setattr(Path, "home", lambda: Path("/Users/tester"))` for the
  location identity (the exact fixture style of `tests/runtime/test_paths.py`).
- `tests/conftest.py` already scrubs `GOGA_DOCKER` between tests (env hygiene).

### Source File Registry

- `goga/runtime/paths.py` — extended `resolve_runtime_dir` (tests extend
  `tests/runtime/test_paths.py`).
- `goga/commands/runtime/runtime.py`, `targets.py`, `archive.py` — new (tests
  at `tests/commands/runtime/test_runtime.py`, `test_targets.py`,
  `test_archive.py`, each with `__init__.py` per convention).
- Facade/root wiring — `tests/commands/test_commands_facade.py` extension.

Note for the implementation agent: the existing
`tests/runtime/test_paths.py::TestPathsContract::test_resolve_runtime_dir_signature`
asserts `params == ["purpose", "suffix_parts"]` — it must be updated to
`["purpose", "suffix_parts", "branch"]` with `branch` of kind
`KEYWORD_ONLY` (annotation `Optional[str]`, default `None`). This is the only
pre-existing test the leaf change touches.

---

### Positive Tests

#### `test_runtime_build_prints_build_dir_single_line`

**Setup**: `monkeypatch.chdir(tmp_path)`;
`monkeypatch.setattr(Path, "home", lambda: Path("/Users/tester"))`; git mocked
to return `feature/x\n` (CompletedProcess pattern from `tests/runtime/test_paths.py`);
`GOGA_DOCKER` deleted.

**Input**: `CliRunner().invoke(runtime, ["build"])`

**Trace**:
```
invoke(runtime, ["build"])
  → runtime group callback          # scope.branch = None
  → build(scope)
    → is_in_docker()                # False (no marker)
    → resolve_effective_branch(None)
      → resolve_git_branch()        # mocked subprocess → "feature-x"
    → resolve_build_target_dir("feature-x")
      → resolve_runtime_dir("builds", branch="feature-x")
        returns: /Users/tester/.goga/runtime/builds/<cwd-seg>/feature-x
    → click.echo(target_dir)        # one stdout line
```

**Assertions**:
```
result.exit_code == 0
result.output.strip() == str(Path("/Users/tester/.goga/runtime/builds") / cwd_segment / "feature-x")
len(result.output.strip().splitlines()) == 1
not target.exists()                 # purity — nothing created
```

**Sufficiency**: SC1/SC3 — the printed line equals the directory `goga build`
uses (same purpose/formula as `build.py:274`); single-line stdout contract;
purity.

#### `test_runtime_pipeline_sanitizes_colons_like_run_time`

**Setup**: as above; git mocked to `main\n`.

**Input**: `invoke(runtime, ["pipeline", "pybuggy:api-feature"])`

**Trace**:
```
→ pipeline(scope, name="pybuggy:api-feature")
  → is_in_docker() → False
  → name.startswith("-") → False
  → resolve_effective_branch(None) → "main"
  → resolve_pipeline_target_dir("pybuggy:api-feature", "main")
    → sanitize_pipeline_name(...) → "pybuggy-api-feature"
    → resolve_runtime_dir("pipelines", "pybuggy-api-feature", branch="main")
  → click.echo(...)
```

**Assertions**:
```
result.exit_code == 0
result.output.strip().endswith("/pipelines/<cwd-seg>/main/pybuggy-api-feature")
```

**Sufficiency**: SC2 — `:` sanitization parity with
`run_pipeline_container.py:153` (the printed path is the run-time directory).

#### `test_runtime_archive_build_target_creates_wrapper_root_archive`

**Setup**: as above (git → `feature-x`); create the target tree:
`home_dir = tmp_path/"home"` with `Path.home` patched to it;
`target = home_dir/".goga/runtime/builds"/<cwd-seg>/"feature-x"` containing
`a.txt` ("hello") and nested `sub/b.log`; cwd = a separate `tmp_path/"work"`
dir.

**Input**: `invoke(runtime, ["archive", "-b"])`

**Trace**:
```
→ archive(scope, build=True, pipeline=None, output=None)
  → is_in_docker() → False
  → XOR(build, pipeline) → ok (exactly one)
  → resolve_effective_branch(None) → "feature-x"
  → resolve_build_target_dir("feature-x") → target (exists)
  → stem = "goga-runtime-build-feature-x"
  → resolve_archive_destination(stem, None) → work/goga-runtime-build-feature-x.tar.gz (absent)
  → package_runtime_archive(target, wrapper_root=stem, destination)
    → tarfile.open(dest, "w:gz"); tar.add(target, arcname=stem)
  → click.echo(archive_path)
```

**Assertions**:
```
result.exit_code == 0
archive = Path(result.output.strip()); archive.is_file()
with tarfile.open(archive) as t:
    names = t.getnames()
names[0] == "goga-runtime-build-feature-x"
"goga-runtime-build-feature-x/a.txt" in names
"goga-runtime-build-feature-x/sub/b.log" in names
```

**Sufficiency**: SC4/SC7/SC9-positive — wrapper-root layout, standard-tool
openability, one-line stdout, file exists at the printed path.

#### `test_runtime_archive_pipeline_target_and_explicit_output`

**Setup**: target under `pipelines/.../<name>`; pre-existing file at the
explicit destination path (overwrite intent); git → `main`.

**Input**: `invoke(runtime, ["archive", "-p", "pybuggy:api", "-o", str(out_path)])`

**Trace**: as above with label `pybuggy-api` → stem
`goga-runtime-pybuggy-api-main`; destination = the explicit path (existing
file → legitimate); packaging truncates and rewrites it.

**Assertions**:
```
result.exit_code == 0
out_path.is_file()
tarfile.open(out_path).getnames()[0] == "goga-runtime-pybuggy-api-main"
```

**Sufficiency**: SC5 + R10 — pipeline target, explicit overwrite destination.

#### `test_runtime_branch_option_overrides_segment`

**Setup**: git mocked to return `main\n` (must NOT be consulted for the
branch); target tree for `release-1.2` exists under `builds/<cwd-seg>/release-1.2`.

**Input**: `invoke(runtime, ["-b", "release/1.2", "build"])`

**Trace**:
```
→ group: scope.branch = "release/1.2"
→ build → resolve_effective_branch("release/1.2") → "release-1-2"?? NO —
  "/"→"-" gives "release-1.2"; no git call
→ resolve_build_target_dir("release-1.2") → echo
```

**Assertions**:
```
result.exit_code == 0
result.output.strip().endswith("/builds/<cwd-seg>/release-1.2")
subprocess.run not called for branch (mock asserts git unused)
```

**Sufficiency**: ADR branch override — slugified explicit value, git-free,
same directory the run on `release/1.2` created.

#### `test_runtime_dual_b_parses_at_both_levels`

**Setup**: in-image refusal mock NOT set; git → `main`; build target exists.

**Input**: `invoke(runtime, ["-b", "main", "archive", "-b"])`

**Assertions**:
```
result.exit_code == 0                      # group -b bound as branch,
result.output contains "goga-runtime-build-main"   # subcommand -b as --build
```

**Sufficiency**: task acceptance — dual `-b` binds at its own level (verified
possible; test pins it for the real command).

---

### Negative Tests

#### `test_runtime_subcommands_refuse_inside_image`

**Setup**: `monkeypatch.setenv("GOGA_DOCKER", "1")`.

**Input**: `invoke(runtime, [x])` for `x` in `["build"]`, `["pipeline", "p"]`,
`["archive", "-b"]`.

**Trace**:
```
→ subcommand → is_in_docker() → True
  → ClickException(host-side-only message) → stderr, exit 1
```

**Assertions**:
```
result.exit_code == 1 for each
"host" in result.stderr.lower()          # human-readable refusal
result.stdout == ""                       # stdout stays reserved
```

**Sufficiency**: in-image refusal for every subcommand (task item 5).

#### `test_runtime_archive_target_selection_usage_errors`

**Input**: `invoke(runtime, ["archive"])` and `invoke(runtime, ["archive",
"-b", "-p", "x"])`.

**Assertions**:
```
result.exit_code != 0 for both
"exactly one" (or equivalent) in stderr
no *.tar.gz created in cwd
```

**Sufficiency**: R6/SC10 — neither/both target selections are usage errors
with no artifact.

#### `test_runtime_pipeline_dash_leading_name_is_clean_error`

**Input**: `invoke(runtime, ["pipeline", "--", "-weird"])`

**Trace**: click delivers `name="-weird"` via `--` → dash guard →
`ClickException`.

**Assertions**:
```
result.exit_code == 1
"invalid pipeline name" in result.stderr
```

**Sufficiency**: ADR argv-parsability; mirrors `pipeline.py:313` precedent.
(Without `--`, click itself exits 2 — covered by
`test_runtime_pipeline_missing_name_is_usage_error` below.)

#### `test_runtime_pipeline_empty_name_is_clean_error`

**Setup**: as the dash test (git may be mocked to anything — the guard fires
before branch resolution).

**Input**: `invoke(runtime, ["pipeline", ""])`

**Trace**:
```
→ click delivers name="" (an empty positional passes through — verified)
→ pipeline(scope, name="") → is_in_docker() → False
→ empty-name guard: name == "" → ClickException("invalid pipeline name ''")
→ stderr "Error: ...", exit 1; no path composed, no stdout
```

**Assertions**:
```
result.exit_code == 1
"invalid pipeline name" in result.stderr
result.stdout == ""
```

**Sufficiency**: review fix (empty-segment guard) — without it,
`Path("/a/b") / ""` silently drops the segment (verified) and the printed
path becomes the branch-level directory, violating the "named pipeline's
artifacts directory" contract.

#### `test_runtime_archive_empty_pipeline_value_is_clean_error`

**Setup**: git → `feature-x`; a build/pipeline state tree exists (the guard
fires before target resolution, but the fixture keeps the case realistic);
cwd empty.

**Input**: `invoke(runtime, ["archive", "-p", ""])`

**Trace**:
```
→ archive(scope, build=False, pipeline="", output=None)
→ is_in_docker() → False
→ XOR ok (pipeline given) → empty-value guard: pipeline == "" →
  ClickException("invalid pipeline name ''") → stderr, exit 1
```

**Assertions**:
```
result.exit_code == 1
"invalid pipeline name" in result.stderr
list(cwd.glob("*.tar.gz")) == []          # nothing packaged
```

**Sufficiency**: review fix (empty-segment guard) — without it the target
resolves to the branch-level directory (empty suffix dropped, verified) and
the whole branch state is packaged under stem `goga-runtime--<segment>`.

#### `test_runtime_archive_pipeline_dash_value_is_clean_error`

**Setup**: git → `feature-x`; cwd empty; no in-image marker.

**Input**: `invoke(runtime, ["archive", "-p", "-weird"])`

**Trace**:
```
→ click delivers pipeline="-weird" (verified: a dash-leading token is
  taken as the option's value, even when it matches another option name)
→ archive(scope, build=False, pipeline="-weird", output=None)
→ is_in_docker() → False
→ XOR ok (pipeline given) → dash guard: pipeline.startswith("-") →
  ClickException("invalid pipeline name '-weird'") → stderr, exit 1
```

**Assertions**:
```
result.exit_code == 1
"invalid pipeline name" in result.stderr
result.stdout == ""
list(cwd.glob("*.tar.gz")) == []
```

**Sufficiency**: pins the archive arm of the manifest's argv-parsability
guard (Algorithm step 2); without this test, removing the guard goes
unnoticed — the dash value would flow into the formula as a pipeline name
(the `--pipeline=-weird` form reaches the same guard).

#### `test_runtime_pipeline_missing_name_is_usage_error`

**Input**: `invoke(runtime, ["pipeline"])`

**Assertions**: `result.exit_code == 2` (click usage error; non-zero — R4).

#### `test_runtime_archive_missing_target_names_path_no_archive`

**Setup**: git → `feature-x`; no `builds/<cwd-seg>/feature-x` directory
exists; cwd empty.

**Input**: `invoke(runtime, ["archive", "-b"])`

**Trace**: target existence check fails → `ClickException` naming the path.

**Assertions**:
```
result.exit_code == 1
str(expected_missing_path) in result.stderr
list(cwd.glob("*.tar.gz")) == []
```

**Sufficiency**: R13/SC8 — missing target reported by path, no archive file.

#### `test_runtime_archive_default_name_collision_refused`

**Setup**: pre-create `cwd/goga-runtime-build-<seg>.tar.gz`; target exists.

**Input**: `invoke(runtime, ["archive", "-b"])`

**Assertions**:
```
result.exit_code == 1
"-o" / "--output" referenced in result.stderr
pre-existing file content unchanged
```

**Sufficiency**: R11/SC9 — refused collision, pointer to `-o`.

#### `test_runtime_archive_output_directory_is_error`

**Input**: `invoke(runtime, ["archive", "-b", "-o", str(tmp_path)])` (an
existing directory).

**Assertions**: `result.exit_code == 1`; directory unmodified; no archive
elsewhere.

#### `test_runtime_archive_output_missing_parent_is_error`

**Input**: `-o <tmp_path>/no/such/dir/a.tar.gz`.

**Assertions**: `result.exit_code == 1`; `"no/such/dir"` not created (no
implicit mkdir).

---

### Edge Case Tests

#### `test_resolve_runtime_dir_explicit_branch_matches_derived_form`

**Setup**: cwd/home patched; git mocked to `feature/x\n`.

**Input**: `resolve_runtime_dir("builds", branch="feature/x")` vs
`resolve_runtime_dir("builds")`.

**Assertions**:
```
explicit == derived            # one formula, no second path scheme
git mock call_count unchanged when branch is explicit (git-free path)
```

**Sufficiency**: ADR "one formula" invariant + "no subprocess when explicit".

#### `test_resolve_runtime_dir_empty_branch_falls_back_to_derived`

**Input**: `branch=""` with git mocked to `main\n`.

**Assertions**: result segment == `"main"` (empty string means not given).

#### `test_resolve_runtime_dir_slugification_idempotent`

**Input**: `branch="feature-x"` (already slugified).

**Assertions**: result segment == `"feature-x"` (passes through unchanged).

#### `test_resolve_effective_branch_contract_matrix`

**Input** (parametrized): `(None → derived)`, `("" → derived)`,
`("a/b" → "a-b")`, `("a-b" → "a-b")`.

**Assertions**: each maps as stated; derived cases mock git.

**Sufficiency**: R2/ADR effective-branch semantics in one table.

#### `test_sanitize_pipeline_name_literal_replacement`

**Input**: `"py:bug:gy:"`, `"plain"`, `""`.

**Assertions**: `"py-bug-gy-"`, `"plain"`, `""` — literal 1:1, no
collapsing/trimming.

#### `test_resolve_archive_destination_matrix`

**Input** (parametrized against tmp_path): default+absent →
`cwd/<stem>.tar.gz`; default+exists → raises; explicit+relative → absolute
under cwd; explicit+existing file → returned (overwrite intent); explicit+dir →
raises; explicit+missing parent → raises.

**Sufficiency**: R9–R11 + strict destination semantics in one boundary table.

#### `test_package_runtime_archive_failure_leaves_no_partial`

**Setup**: target with files; destination = fresh path; make `tar.add` raise
mid-packaging (`mock.patch.object(tarfile.TarFile, "add", side_effect=OSError)`).

**Trace**:
```
→ tarfile.open(dest, "w:gz") succeeds (file created)
→ tar.add raises → except: unlink → raise
```

**Assertions**:
```
pytest.raises(OSError); not destination.exists()   # partial removed
```

**Sufficiency**: ADR — nothing partial is kept.

#### `test_package_runtime_archive_open_failure_keeps_preexisting_file`

**Setup**: destination pre-created with content and made read-only
(`chmod 0o444`) in a writable dir (explicit-`-o` overwrite scenario).

**Trace**:
```
→ tarfile.open(dest, "w:gz") raises PermissionError (opened == False)
→ guarded cleanup: NO unlink → raise
```

**Assertions**:
```
pytest.raises(PermissionError)
destination.exists(); destination.read_text() == original content
```

**Sufficiency**: Fix 2 regression guard — a failure before open never deletes
a pre-existing destination file.

#### `test_package_runtime_archive_symlinks_preserved`

**Setup**: target contains a symlink `link -> a.txt`.

**Assertions**: `tarfile.open(dest).getmember("<root>/link").issym()` is True
(no dereference).

**Sufficiency**: R7 "special files preserved as encountered".

#### `test_runtime_archive_empty_target_directory_packages`

**Setup**: target dir exists, empty.

**Assertions**: exit 0; archive contains only the wrapper root member.

**Sufficiency**: ADR — "directory exists → we package it".

#### `test_bare_runtime_group_prints_help_nonzero`

**Input**: `invoke(runtime, [])`.

**Assertions**: `result.exit_code == 2` (click group default — matches bare
`goga history`); help text rendered.

**Sufficiency**: pins the corrected contract (Fix 1) and the project
precedent; prevents re-introducing the ADR's wrong exit-0 assumption.

#### `test_runtime_group_option_only_before_subcommand`

**Input**: `invoke(runtime, ["build", "-b"])`.

**Assertions**: non-zero exit, usage error — `build` carries no options; the
dual `-b` exists only on `archive` (after the token) and the group (before).

---

## Additional Instructions for the Implementation Agent

- Implement strictly in the dependency order: `goga/runtime/paths.py` →
  `targets.py` → `archive.py` → `runtime.py` → `__init__.py` → facade →
  `goga/cli.py`. Run `ruff check` and `pytest tests/ -x` after each cell.
- `resolve_runtime_dir`'s new parameter is keyword-only (`*suffix_parts` stays
  first): `def resolve_runtime_dir(purpose: str, *suffix_parts: str, branch:
  str | None = None) -> Path`. Update the existing signature contract test in
  `tests/runtime/test_paths.py` (see the note above) — it is the only
  pre-existing test touched by the leaf change.
- `_RuntimeScope` is a `@dataclass(kw_only=True)` with `branch: str | None =
  None` — the `_HistoryScope` pattern (`history.py:24-28`). Do not use a dict.
- All intra-package imports are relative (`from ..docker import is_in_docker`,
  `from ..runtime import resolve_runtime_dir`, `from .targets import ...`).
- The guarded cleanup in `package_runtime_archive` is contractual (Fix 2):
  unlink the destination only when the archive was successfully opened. Do not
  apply the `tarfile` cook's unconditional-unlink snippet verbatim in the
  explicit-destination case.
- Do not add a bare-group exit-0 handler — the standard `@click.group()`
  default (help, exit 2) is the corrected contract (Fix 1) and matches
  `goga history`.
- The command docstrings are the `--help` texts: no Args/Returns/Raises; the
  group's help documents both `-b` meanings (group `--branch` before the
  subcommand token, `archive`'s `--build` after it).
- `resolve_archive_destination` and `package_runtime_archive` raise plain
  exceptions/`ClickException`-compatible errors per the manifest; the command
  layer must ensure every failure surfaces as a `ClickException` (stderr, exit
  1) — never a traceback.
- Smoke checks from the architecture plan's verification checklist:
  `python -c "from goga.commands.runtime import runtime"`,
  `goga --help` lists `runtime`, `goga schema` shows the new subcell with its
  `goga/runtime` + `goga/docker` dependencies, `goga lint` project-wide clean.
