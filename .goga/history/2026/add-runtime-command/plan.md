# Plan: `add-runtime-command` — the `goga runtime` command group

<!-- Topic: `add-runtime-command` — a host-side `goga runtime` command group
     (path queries `build` / `pipeline` and a single-target `archive` over the
     shared runtime formula) plus the one keyword-only `branch` extension of
     `resolve_runtime_dir`. Source:
     `.goga/history/2026/add-runtime-command/design.md` (design-review
     completed — 5 remarks fixed, all approved; see the design-review
     execution summary and the design's "Applied Fixes" sections). This plan
     compiles the design into ralphex-executable tasks. CODEMANIFEST changes
     and all `.usages/` docs are ALREADY APPLIED in the working tree — this
     plan touches code and tests only. -->

## Purpose

Implement the `goga runtime` command group end-to-end against the already
applied CODEMANIFEST contracts: a host-side, stateless observer surface over
the runtime location formula with three subcommands — `build` (print the
build artifacts directory), `pipeline NAME` (print the named pipeline's
artifacts directory, sanitized exactly as at run time), and `archive`
(package exactly one target into a single wrapper-rooted `.tar.gz` and print
its path) — carried by a click group whose `-b/--branch` option (before the
subcommand token) overrides the git-derived branch segment.

After implementation the project provides:

- `goga/runtime/paths.py` — `resolve_runtime_dir` gains a keyword-only
  `branch: str | None = None` parameter: a non-empty value is slugified
  (`/` → `-`) and used directly (git-free); `None`/`""` keep the git-derived
  behavior bit-identical for the existing callers.
- `goga/commands/runtime/` (new cell, code only — the manifest and `.usages/`
  already exist): `targets.py` (four pure target/branch routines), `archive.py`
  (destination resolution + guarded tarfile packaging), `runtime.py` (the
  click group `_RuntimeScope` + three subcommands), `__init__.py` (the cell
  facade).
- `goga/commands/__init__.py` — `runtime` re-exported through the commands
  facade; `goga/cli.py` — `app.add_command(runtime)`.

The most important gaps between contract and code: `goga/commands/runtime/`
contains only `CODEMANIFEST` + `.usages/` (no Python at all); the cell is not
importable (no `__init__.py`); `resolve_runtime_dir` accepts no `branch`;
the commands facade and the root app do not know `runtime`; the pre-existing
signature test pins the OLD two-parameter signature.

Strategy: leaves-first TDD in the design's mandated order — `goga/runtime`
(the `branch` extension) → `targets.py` → `archive.py` → `runtime.py` →
cell facade → commands facade + root registration → cross-entity integration
proof. Every task is gated by the Mandatory Rules below.

## Mandatory Rules

<!-- Extracted verbatim from the project convention
     `.goga/usages/conventions.md` (the `convention` practice, wired into the
     `goga/runtime`, `goga/commands/runtime`, and `goga/commands` manifests —
     for working with the codebase, organizing the REPL development cycle,
     debugging and testing, and the test infrastructure), the language rules
     (`goga-cell-python`), the ruff configuration (`pyproject.toml`), and the
     repo gates (`.github/workflows/lint.yml`, `.github/workflows/tests.yml`,
     `.githooks/`). These rules are MANDATORY for every task in this plan.
     Where a task restates a rule, the restatement is a reminder, not a
     replacement. -->

### Coding Style (strictly per `conventions.md`)

- **Python 3.10+ only**; all configuration lives in `pyproject.toml`; all
  code executes within a virtualenv — create it if missing.
- **Imports**: relative imports for ALL intra-package references inside
  `goga/` (`from .targets import resolve_effective_branch`, `from .archive
  import package_runtime_archive`, `from ...runtime import
  resolve_runtime_dir`, `from ...docker import is_in_docker`); absolute
  imports only for stdlib and third-party (`click`, `tarfile`,
  `pathlib.Path`, `dataclasses`). Exception — tests: cross-directory
  references inside `tests/` use absolute imports rooted at the `tests`
  package.
- **Data models**: stdlib `dataclasses` only; model classes use
  `@dataclass(kw_only=True)` (the `_HistoryScope` precedent,
  `goga/commands/history/history.py:24-28`); `None` only for the explicit
  absence of a value — `_RuntimeScope.branch: str | None = None` (None =
  the group option was not given). Do NOT use a dict for the scope.
- **Docstrings**: Google style, MANDATORY for every public function, method,
  and class. First line starts with a capital letter and ends with a period.
  Include `Args` when the function accepts parameters, `Returns` when it
  returns a value, `Raises` when it raises beyond built-in types. The
  CODEMANIFEST annotations are the source text for parameter descriptions.
- **CLI command docstrings are `--help` text** (the convention's CLI
  docstring rule): a click command callback's docstring renders verbatim as
  `--help` — omit `Args`/`Returns`/Raises` there (click auto-generates the
  options block; the callback has no user-facing return; internal exception
  types stay hidden), keep the concise summary line, use the `\f` marker for
  developer-facing notes. The group's help documents BOTH `-b` meanings
  (group `--branch` before the subcommand token, `archive`'s `--build`
  after it). The Google rules still apply unchanged to every OTHER public
  function in a command module (`resolve_effective_branch`, …,
  `package_runtime_archive`).
- **Code formatting**: inside function and method bodies, separate logical
  blocks by ONE blank line (initialization / conditions and loops / data
  preparation / processing / return).
- **Type hints**: mandatory everywhere (they drive facade signature
  extraction). Allowed shapes: `str`, `int`, `float`, `bool`, `list[T]`,
  `dict[str, T]`, `T | None`. Forbidden: `**kwargs`, bare `dict`, bare
  `list`. One contract-pinned exception: `*suffix_parts: str` of
  `resolve_runtime_dir` (VAR_POSITIONAL, pre-existing contract entity — the
  DSL `...suffix_parts` form; keep it, the new `branch` goes keyword-only
  after it).
- **Naming**: PascalCase classes, snake_case functions/methods/modules;
  private helpers one leading underscore (`_RuntimeScope`).
- **Facade**: each cell's `__init__.py` exposes the contract API through
  `__all__`; only identifiers in `__all__` constitute the facade. This
  feature adds the full `goga/commands/runtime` facade (7 names) and one
  `runtime` entry to `goga/commands/__all__`.
- **Logging**: NONE in this feature. The design's cross-cutting decision:
  the cell is a thin CLI observer surface (the `history`/`topics` pattern)
  — stdout is the single result line, errors are user-facing
  `click.ClickException` messages; the convention's logging rules apply to
  library code and no operational log consumers exist here. Use
  `click.echo`, never `print()`.
- **Error handling is contractual**: domain/semantic errors are
  `click.ClickException` (stderr, `Error: ` prefix, exit 1); argv-form
  errors are click-native usage errors (exit 2) or the explicit
  dash-leading/empty guards (exit 1, the `pipeline.py:305-319` precedent);
  stdout is never used for errors; no traceback ever reaches the user.
- **Dependencies**: NO new third-party dependencies — `click>=8.0` is
  already pinned; `tarfile` is stdlib (no `pyproject.toml` entry, per the
  tarfile cook). No `pyproject.toml` changes at all.
- **No public API beyond the contract**: no extra subcommands, no
  listing/tree modes, no `-a/--archive` shortcut on path queries, no bulk
  mode, no extraction (ADR-rejected; out of scope).

### Test Writing Rules (strictly per `conventions.md` — Testing)

- **Tools**: pytest (runner), ruff (lint + format of test code), pytest-cov
  (coverage). Test libraries live in `pyproject.toml`
  `[project.optional-dependencies]` under `test` (already pinned:
  `pytest>=8.0`, `pytest-cov>=5.0`, `ruff>=0.15.0`). Test code is Python
  3.10+ compatible and runs in the virtualenv.
- **Structure mirrors source directly** (`<src>/module/file.py` →
  `tests/module/test_file.py`): `goga/runtime/paths.py` → extends
  `tests/runtime/test_paths.py`; `goga/commands/runtime/targets.py` →
  `tests/commands/runtime/test_targets.py`; `goga/commands/runtime/
  archive.py` → `tests/commands/runtime/test_archive.py`;
  `goga/commands/runtime/runtime.py` → `tests/commands/runtime/
  test_runtime.py`. Create `tests/commands/runtime/__init__.py` (EVERY test
  directory MUST contain an `__init__.py`). Cross-package integration tests
  go to `tests/integration/test_runtime_command_end_to_end.py`.
- **Fixtures**: local fixtures in `tests/<package>/conftest.py`, shared
  fixtures in `tests/conftest.py`. Reuse, never duplicate:
  `tests/conftest.py` already scrubs `GOGA_DOCKER` between tests (env
  hygiene, `tests/conftest.py:61-66`) — do not re-scrub in a fixture; the
  exact fixture style of `tests/runtime/test_paths.py`
  (`monkeypatch.chdir(tmp_path)` +
  `monkeypatch.setattr(Path, "home", lambda: Path("/Users/tester"))` +
  the `subprocess.CompletedProcess` git mock).
- **Naming**: files `test_<module>.py`; functions
  `test_<what>_<scenario>`; grouping `class Test<Component>:`;
  self-documenting test names; keep comments minimal.
- **Test types**: Unit — every public function/method/class, main scenario
  and typical data. Edge cases — empty inputs (`""`, `None`), boundary
  values, expected exceptions via `pytest.raises`. Integration — only for
  interaction between modules/packages (Task 7).
- **CLI testing**: via `click.testing.CliRunner` invoking the command
  group (`runner.invoke(runtime, [...])`), asserting `result.exit_code`,
  `result.output` (stdout), and `result.stderr` — CliRunner separates the
  streams; the design's traces were verified this way on click 8.5.1.
- **Boundary tests**: the branch-mapping and destination-semantics domains
  use `@pytest.mark.parametrize` tables covering every boundary (the
  design's `test_resolve_effective_branch_contract_matrix` and
  `test_resolve_archive_destination_matrix`).
- **Mocks — only at external boundaries**: `mock.patch.object(subprocess,
  "run", ...)` for git (the CompletedProcess pattern), `monkeypatch.setenv/
  delenv("GOGA_DOCKER")` for the image marker, `monkeypatch.setattr(Path,
  "home", ...)` for the location identity, `tmp_path` for all file I/O,
  `mock.patch.object(tarfile.TarFile, "add", side_effect=OSError)` for the
  mid-packaging failure. Pure logic stays mock-free
  (`sanitize_pipeline_name`, `resolve_archive_destination`,
  `resolve_effective_branch` with explicit branches).
- **Golden values are grounded, never recalled**: every pinned behavior in
  this plan (exit codes 1/2, message fragments, path shapes, wrapper-root
  names, `Path("/a/b") / ""` dropping the empty segment) was verified by
  the design against the live libraries; if an assertion disagrees with a
  live REPL run during implementation, the live run wins and the
  disagreement is reported — never silently "aligned".
- **The one pre-existing test touched**: `tests/runtime/test_paths.py::
  TestPathsContract::test_resolve_runtime_dir_signature` currently asserts
  `params == ["purpose", "suffix_parts"]` — Task 2 updates it (HARD-FAILING
  change) to `["purpose", "suffix_parts", "branch"]` with `branch` of kind
  `KEYWORD_ONLY` (annotation `Optional[str]`, default `None`). No other
  pre-existing test is modified by the leaf change (verified: positional
  binding of both existing callers is unchanged).

### Linter and Formatter Enforcement (all development stages and local commits)

The following gates are MANDATORY at the end of EVERY task and BEFORE EVERY
local commit, across all development stages. A failing gate is an
actionable defect, never acceptable noise. Local git hooks do NOT enforce
formatting (only the commit-msg / pre-push Co-Authored-By policy does) —
the author runs the formatter deliberately:

1. `ruff check goga/ tests/` — zero violations (the CI gate of
   `.github/workflows/lint.yml`; rule set per `pyproject.toml`: E, W, F, I,
   N, UP, B, SIM, PL, PLR, C4, DTZ, PT, ARG, RUF, PTH, C90; line length
   120; target py310; mccabe max-complexity 10; the tests per-file-ignores
   apply: S101, ARG001, ARG002, PLR2004, RUF001, PLC0415).
2. `ruff format --check goga/ tests/` — zero reformattings; run
   `ruff format goga/ tests/` when it reports diffs (double quotes, space
   indent, LF line endings, magic trailing comma kept — per
   `[tool.ruff.format]`).
3. `goga lint` — cell-level lint, **0 errors over 94 cells** (verified
   green on the pre-change tree during planning; the host `goga` CLI at
   `/opt/goga/bin/goga` is an editable install of this workspace, so it
   sees workspace changes immediately).
4. Focused tests green, then `pytest tests/ -x` green (the full battery —
   verified baseline: 8391 passed, 8 skipped; the existing suites stay
   green except the ONE deliberate signature-test update of Task 2).
5. Facade import checks green (see Validation Commands).
6. **Commit policy**: commit only with all gates green; commit messages
   MUST NOT contain `Co-Authored-By:` trailers (`.githooks/commit-msg` and
   `pre-push` reject them). The applied CODEMANIFEST + `.usages/` changes
   currently uncommitted in the working tree are committed FIRST (Task 1)
   so every per-task commit isolates code changes.
7. `CODEMANIFEST` files are READ-ONLY for the implementer — the contract
   changes are already applied in the working tree; if code does not match
   the contract, fix the code, never the contract.

### REPL Cycle Rules (continuous interactive evaluation, hot reloading, migration to source)

The `convention` practice is wired into every cell of this feature for
"Organizing the REPL development cycle" (the manifests' global Annotations
say so verbatim). Every coding task in this plan follows the same loop:

1. **Virtualenv first**: all code executes inside a virtualenv — create it
   if missing. `.venv` was created and verified during planning (Python
   3.12.16, editable install with `[test]` extras, full battery green);
   Task 1 re-verifies (or recreates) it BEFORE any change. Every probe,
   test run, and lint run executes inside it (`.venv/bin/python`,
   `.venv/bin/pytest`, `.venv/bin/ruff`).
2. **Probe before writing**: verify each non-trivial behavior
   interactively against real inputs BEFORE the verified snippet is
   written into a source file or a golden is pinned into a test. The
   probes of this feature: live `resolve_runtime_dir("builds",
   branch="feature/x")` vs the derived form — one formula, git-free
   (Task 2); `Path("/a/b") / ""` silently dropping the empty segment —
   the reason both empty-name guards exist (Task 3 probe, reused by 5);
   live `tarfile.open(dest, "w:gz")` truncating at open, raising
   `PermissionError` on a `0o444` pre-existing file, `arcname` wrapper
   root layout, symlink preservation, and the self-archiving guard
   (Task 4); CliRunner probes of the group — dual `-b` disjoint parse
   positions (`["-b", "main", "archive", "-b"]`), bare group exit 2,
   `["pipeline", ""]` and `["pipeline", "--", "-weird"]` delivery,
   `-p -weird` taken as the option value, `--branch=` arriving as `""`
   (Task 5).
3. **Hot feedback after every edit**: immediately re-run the focused test
   file and the facade import check in the same virtualenv; iterate in
   small steps. A long-lived REPL session re-imports edited modules
   (`importlib.reload` or a fresh `.venv/bin/python -c`) — never trust
   stale module state as evidence; the click group object and
   `_RuntimeScope` demand a fresh interpreter after every edit.
4. **Migrate verified code to source files**: REPL-verified snippets are
   migrated into the target `location` file with type hints, Google
   docstrings, relative imports, and convention formatting; REPL scratch
   never ships and is never referenced by source.
5. **Close the loop per task**: probe → implement (migrate) → focused
   tests → full battery → lint/format gates → commit (gates green).

**The REPL never replaces the TDD gates**: contract tests are still written
FIRST (expected to fail) and logic tests AFTER the implementation — the
REPL shortens the debug loop between them (each task's first Code checkbox
embeds its probes).

## Context

### Entity Interaction and Data Flow (from the design, verbatim)

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

Data flows (from the design, verbatim):

1. **Path query (build)**: argv → group callback stores `branch: str | None`
   in `ctx.obj` (`_RuntimeScope`) → `build` reads scope.branch →
   `resolve_effective_branch` (`str | None` → `str` segment) →
   `resolve_build_target_dir(segment)` (`str` → `Path`) → `click.echo(Path)`
   — exactly one stdout line.
2. **Path query (pipeline)**: same, with `name: str` → dash-check →
   `resolve_pipeline_target_dir(name, segment)` → `Path` → echo.
3. **Archive**: scope.branch → segment → target selection (`build` flag XOR
   `pipeline` value) → target dir (`Path`) + existence check → stem (`str`)
   → `resolve_archive_destination(stem, output)` (`Path`) →
   `package_runtime_archive(target_dir, stem, destination)` (`Path`) → echo.

Entity dependencies — implementation order (leaves first), from the design
verbatim: `goga/runtime/paths.py` (add `branch`) →
`goga/commands/runtime/targets.py` → `goga/commands/runtime/archive.py` →
`goga/commands/runtime/runtime.py` (group; imports `.targets`/`.archive`) →
`goga/commands/runtime/__init__.py` → `goga/commands/__init__.py` (facade
re-export) → `goga/cli.py` (`app.add_command(runtime)`). One infrastructure
adjustment: a minimal `goga/commands/runtime/__init__.py` must exist BEFORE
`targets.py` is importable (a regular package's subpackage needs the
marker); it is created in Task 3 and grows to the full facade as entities
land.

### Contract Surface

**Entity: `runtime(branch: str | None = None)`** (cell
`goga/commands/runtime` — NEW, `location: runtime.py`)
- Type: click.Group Entity (class-like container with methods)
- Facade obligation: importable from `goga.commands.runtime`; re-exported
  by `goga/commands` (`->runtime: {}`); registered via
  `app.add_command(runtime)` in `goga/cli.py`
- Methods (the three subcommands):
  - `build() -> exit_code: int` — refuse in image; resolve branch segment;
    resolve build target dir; echo one line (see Task 5 algorithm)
  - `pipeline(name: str) -> exit_code: int` — refuse in image; reject
    empty/dash-leading name; resolve segment; resolve pipeline target dir;
    echo one line
  - `archive(build: bool = False, pipeline: str | None = None, output:
    str | None = None) -> exit_code: int` — refuse in image; XOR target
    selection + empty/dash pipeline guard; segment; target + existence;
    stem; destination; package (OSError → ClickException); echo archive path
- Semantic requirements (key): bare group → help, exit **2** (click group
  default, matches bare `goga history` — Fix 1); group options bind only
  before the subcommand token (dual `-b` disjoint); stdout = exactly one
  result line, never errors; `exit_code` phrasing "0 on success, 1 on
  error" is the project manifest convention — click-native usage errors
  exit 2; nothing created/modified on disk by the path queries; archive
  writes exactly one new artifact and never touches its source.
- Imported dependencies: `is_in_docker` (`goga/docker`); the cell's own
  routines via relative imports.
- Annotation cascade: global Annotations (relative imports; one result
  line; host-side observer semantics) → entity (group container, both `-b`
  meanings documented, CLI docstring rule) → method Algorithms/
  Requirements/Constraints (full text in `goga/commands/runtime/
  CODEMANIFEST` — read-only, in-repo).

**Entity: `resolve_effective_branch(branch: str | None = None) -> segment: str`**
(cell `goga/commands/runtime` — NEW, `location: targets.py`)
- Type: Routine (pure function)
- Facade obligation: importable from `goga.commands.runtime`
- Semantics: non-empty `branch` → `branch.replace("/", "-")` (no git, no
  validation, idempotent); `None`/`""` → `resolve_git_branch()` (slugified
  current branch or `"default"`, never raises for documented modes).
  Deterministic; pure w.r.t. the filesystem (only the derived form reads
  git).

**Entity: `resolve_build_target_dir(branch_segment: str) -> target_dir: Path`**
(cell `goga/commands/runtime` — NEW, `location: targets.py`)
- Type: Routine (pure function)
- Facade obligation: importable from `goga.commands.runtime`
- Semantics: `resolve_runtime_dir("builds", branch=branch_segment)` —
  keyword call, NO suffix parts (build has no namespace below the branch
  directory); pure (never creates). Parity: same purpose and formula as
  the run's actual call `goga/commands/build/build.py:274`
  (`resolve_runtime_dir("builds")`) — same directory for the same branch.

**Entity: `sanitize_pipeline_name(name: str) -> sanitized: str`**
(cell `goga/commands/runtime` — NEW, `location: targets.py`)
- Type: Routine (pure function)
- Facade obligation: importable from `goga.commands.runtime`
- Semantics: literal `name.replace(":", "-")` — one-to-one, no collapsing,
  no trimming. Identical to the run's composition at
  `goga/commands/pipeline/run_pipeline_container.py:153`
  (`pipeline_name.replace(":", "-")`).

**Entity: `resolve_pipeline_target_dir(pipeline_name: str, branch_segment: str) -> target_dir: Path`**
(cell `goga/commands/runtime` — NEW, `location: targets.py`)
- Type: Routine (pure function)
- Facade obligation: importable from `goga.commands.runtime`
- Semantics: `sanitize_pipeline_name(pipeline_name)` →
  `resolve_runtime_dir("pipelines", sanitized, branch=branch_segment)`;
  the printed path is the directory the run actually uses; pure.

**Entity: `resolve_archive_destination(archive_stem: str, output: str | None = None) -> destination: Path`**
(cell `goga/commands/runtime` — NEW, `location: archive.py`)
- Type: Routine (pure validation/resolution function)
- Facade obligation: importable from `goga.commands.runtime`
- Semantics: default (`output is None`) → `Path.cwd() / f"{stem}.tar.gz"`;
  an existing file there is a clean collision error naming the path and
  pointing to `-o/--output`. Explicit → resolve relative against cwd;
  existing directory ⇒ error; missing parent ⇒ error (no implicit mkdir);
  existing file ⇒ legitimate (overwrite intent). Returns absolute path;
  writes nothing. Edge: `output=""` → `Path.cwd()` → "existing directory"
  clean error (acceptable, consistent).

**Entity: `package_runtime_archive(target_dir: Path, wrapper_root: str, destination: Path) -> archive_path: Path`**
(cell `goga/commands/runtime` — NEW, `location: archive.py`)
- Type: Routine (effectful packaging function)
- Facade obligation: importable from `goga.commands.runtime`
- Semantics: `tarfile.open(destination, "w:gz")` (creates/truncates at
  open; unwritable ⇒ `OSError` here, before any data) → `tar.add(
  target_dir, arcname=wrapper_root)` (recursive default, `dereference=
  False` — symlinks preserved, no filter) → close → return `destination`
  (absolute). Failure AFTER a successful open: close, unlink the partial
  (only an archive file THIS routine created), re-raise. Failure BEFORE
  open: re-raise WITHOUT unlink (Fix 2 — a pre-existing destination file
  is not "partial archive"). The command layer wraps `OSError` into a
  `ClickException`.

**Entity: `resolve_runtime_dir(purpose: str, ...suffix_parts: str, branch: str | None = None) -> runtime_dir: Path`**
(cell `goga/runtime` — CHANGED, `location: paths.py`)
- Type: Routine (pure function) — signature extension only
- Facade obligation: importable from `goga.runtime` (unchanged `__all__`)
- Semantics: `segment = branch.replace("/", "-") if branch else
  resolve_git_branch()` (`""` is falsy ⇒ derived; no git subprocess when
  explicit) → `Path.home() / ".goga" / "runtime" / purpose / normalized /
  segment / *suffix_parts`. Existing callers (`build.py:274`,
  `run_pipeline_container.py:153`) pass no `branch` and are unaffected
  (positional binding unchanged, keyword-only addition). One formula — the
  explicit branch produces exactly what the git-derived form produces for
  that branch; slugification idempotent.

### Re-exports

- `->runtime: {}` in `goga/commands/CODEMANIFEST`: the `runtime` click
  group imported from `goga/commands/runtime` must be importable from the
  `goga.commands` facade (`from .runtime import runtime` + `__all__`
  entry).
- Root: `runtime` is in `goga/CODEMANIFEST`'s `goga/commands` Types list
  and in the `app()` Commands list — registration via
  `app.add_command(runtime)` in `goga/cli.py` (the `history` precedent).

### Usages Context

- `convention` → `.goga/usages/conventions.md` — the mandatory project
  baseline: relative imports, Google docstrings, the CLI-command docstring
  rule, `kw_only=True` dataclass models, test structure/naming/mocking
  rules, Python 3.10+ compatibility, validation commands. Wired into all
  three manifests' global Annotations (verbatim list: working with the
  codebase; organizing the REPL development cycle; debugging and testing;
  organizing the test infrastructure; general development/testing rules).
- `click` → `.goga/usages/cooks/click.md` — group/command decorators,
  `ctx.obj` state passing (`ctx.ensure_object`), option/argument surfaces,
  `click.echo` / `ClickException`, CliRunner testing, and the new "Option
  positioning in nested groups" section (group option binds only before
  the subcommand token — the dual `-b` rationale). Always specify `help`
  on every `--option`; never `print()`; never `sys.exit()` inside commands.
- `tarfile` → `.goga/usages/cooks/tarfile.md` — stdlib (no pyproject
  entry); `w:gz` open semantics (create/truncate at open, `OSError` on
  unwritable BEFORE any data); `arcname` wrapper root; recursive add with
  `dereference=False`; self-archiving guard; the GUARDED cleanup snippet
  (unlink only after a successful open — never the unconditional form).
- `cli-commands` → `goga/commands/.usages/cli-commands.md` — the 19-command
  facade documentation (import/registration snippets + command table);
  `runtime` is already listed (apply stage).

### Imported Usages

- `runtime-paths` from cell `goga/runtime` — source
  `goga/runtime/.usages/runtime-paths.md`. The consumer facade pattern over
  the shared formula (fixed purpose, optional suffix, explicit branch), the
  path shape `~/.goga/runtime/<purpose>/<normalized>/<branch>/<suffix>`,
  purity guarantees, failure modes. Relevant to
  `resolve_build_target_dir`, `resolve_pipeline_target_dir` (their manifest
  annotations reference it), and the Task 3 parity tests. Already updated
  by the apply stage for the extended signature ("Addressing another
  branch's state" section).

### Local Usages

- `goga/commands/runtime/.usages/path-queries.md` — category: the two path
  queries (one-line stdout contract, branch option, scripting patterns,
  failure modes). Status: new file, ALREADY materialized by the
  apply-architecture stage; current against the corrected manifest (it
  never stated a bare-group exit code). Related entities: `runtime.build`,
  `runtime.pipeline`. Verification: Task 5 truthfulness check.
- `goga/commands/runtime/.usages/archive.md` — category: archiving
  (single-target selection, wrapper-root naming, destination semantics,
  failure modes, non-reproducible-bytes note). Status: new file, ALREADY
  materialized; current (its "mid-packaging failure removes the partial
  archive" wording matches the guarded reading of Fix 2). Related entities:
  `runtime.archive`, `resolve_archive_destination`,
  `package_runtime_archive`. Verification: Task 5 truthfulness check.
- No `.usages/` creation or edit tasks exist — the design's `.usages/
  Update` section: "No `.usages/` updates required by this design beyond
  what the apply stage already materialized." Tasks only VERIFY truthfulness
  and report drift.

### External Dependencies

- `click>=8.0` (pinned in `pyproject.toml`; verified 8.5.1 in `.venv`) —
  the CLI framework; no version change.
- Python stdlib `tarfile` + gzip — in-process packaging; NO new pip
  dependency, NO `pyproject.toml` change (tarfile cook: "No installation
  and no `pyproject.toml` entry — it is stdlib").
- Test stack: `pytest>=8.0`, `pytest-cov>=5.0`, `ruff>=0.15.0` (already in
  `[project.optional-dependencies] test`; verified ruff 0.17.6 in `.venv`).
- Host tooling: the `goga` CLI (`/opt/goga/bin/goga`, editable install of
  this workspace) for `goga lint` / `goga schema` / `goga --help` smoke
  checks.

## Facts

- Contract state (all READ-ONLY, applied in the working tree):
  `goga/commands/runtime/CODEMANIFEST` (new cell — 7 entities),
  `goga/runtime/CODEMANIFEST` (`resolve_runtime_dir` extended),
  `goga/commands/CODEMANIFEST` (runtime import + 2 practice paragraphs +
  `->runtime: {}`), `goga/CODEMANIFEST` (runtime in Types + Commands list).
  `goga lint` → **94 cells, 0 errors**; `goga schema` resolves
  `goga/commands/runtime` with exactly the planned `goga/runtime` +
  `goga/docker` dependencies (both verified live during planning).
- `.usages/` state: `goga/commands/runtime/.usages/{path-queries,archive}.md`
  exist; `goga/runtime/.usages/runtime-paths.md` and
  `goga/commands/.usages/cli-commands.md` (19 commands, `runtime` in every
  snippet + the table) are current.
- `goga/commands/runtime/` contains NO Python — the cell is not importable
  (no `__init__.py`); `goga/commands/__init__.py` has no `runtime` export;
  `goga/cli.py` has no `runtime` registration (verified: `app.add_command`
  list at `goga/cli.py:70-87`).
- `resolve_runtime_dir` today: `def resolve_runtime_dir(purpose: str,
  *suffix_parts: str) -> Path` (`goga/runtime/paths.py:47`) — git-derived
  branch only.
- Parity call sites (the printed paths must equal what these produce):
  `goga/commands/build/build.py:274` → `resolve_runtime_dir("builds")`;
  `goga/commands/pipeline/run_pipeline_container.py:153` →
  `resolve_runtime_dir("pipelines", pipeline_name.replace(":", "-"))`.
- In-repo precedents to copy: `_HistoryScope` kw_only dataclass +
  `@click.group()` + `@click.pass_context` + `ctx.ensure_object` +
  `@history.command` + `@click.pass_obj` (`goga/commands/history/
  history.py:24-28, 54-79`); the dash-guard family
  `f"invalid pipeline name {name!r}"` (`goga/commands/pipeline/
  pipeline.py:305-319`); facade `__all__` pattern
  (`goga/commands/build/__init__.py`, `goga/commands/history/__init__.py`).
- `is_in_docker()` — `goga/docker/env.py:9-22`
  (`os.environ.get("GOGA_DOCKER") == "1"`), re-exported by
  `goga/docker/__init__.py`.
- Environment: `.venv` exists (created during planning; Python 3.12.16,
  editable install `.[test]`, click 8.5.1, ruff 0.17.6). Baseline battery
  verified green BEFORE any change: **8391 passed, 8 skipped**
  (`pytest tests/ -x`); `ruff check goga/ tests/` and
  `ruff format --check goga/ tests/` — zero findings.
- Test infrastructure: `tests/runtime/test_paths.py` (fixture style + the
  signature test to update); `tests/commands/test_commands_facade.py`
  (facade test pattern); `tests/conftest.py:61-66` scrubs `GOGA_DOCKER`
  between tests; `tests/commands/runtime/` does not exist yet.
- Library facts (verified empirically at design/review on click 8.5.1 /
  Python 3.12): bare `@click.group()` invocation → help + exit **2** (same
  as bare `goga` / `goga history` today); group options bind only before
  the subcommand token (`["-b", "main", "archive", "-b"]` parses — group
  branch `main`, subcommand `build=True`); `--branch=` delivers `""`;
  `["pipeline", ""]` delivers `name=""`; `["pipeline", "--", "-weird"]`
  delivers `name="-weird"`; `-p -weird` delivers a dash-leading value
  (even when it collides with another option name); `["build", "-b"]` →
  usage error (build carries no options); `Path("/a/b") / ""` → `/a/b`
  (empty segment silently dropped); `tarfile.open(dest, "w:gz")` raises
  `PermissionError` at open on a `0o444` file in a writable directory
  (unlink would succeed there — the guarded cleanup is what protects the
  pre-existing file); wrapper-root members `["<root>", "<root>/a.txt"]`;
  tarfile skips an archive written inside the packaged tree.
- Git/CI facts: working tree carries the uncommitted apply-stage contract/
  usage changes (to be committed in Task 1); `.githooks/commit-msg` +
  `pre-push` reject `Co-Authored-By:` trailers; CI lint gate =
  `ruff check` + `ruff format --check` on `goga/ tests/`
  (`.github/workflows/lint.yml`).

## Gap Analysis

- Missing contract entities (7): the whole `goga/commands/runtime` code
  surface — `runtime` group (+3 subcommands), `resolve_effective_branch`,
  `resolve_build_target_dir`, `sanitize_pipeline_name`,
  `resolve_pipeline_target_dir`, `resolve_archive_destination`,
  `package_runtime_archive`.
- Changed contract entity (1): `resolve_runtime_dir` lacks the keyword-only
  `branch` parameter.
- Missing facade exposure: cell `__init__.py` (none exists → package not
  importable); `goga/commands.__all__` lacks `runtime`; `goga/cli.py` lacks
  `app.add_command(runtime)`.
- API mismatches: none in existing code (the leaf extension is
  source-compatible with both existing callers — keyword-only addition).
- Test coverage gaps: no tests for any new entity; `tests/commands/runtime/`
  does not exist; `tests/runtime/test_paths.py::test_resolve_runtime_dir_
  signature` pins the OLD signature (deliberate hard-failing update in
  Task 2).
- Existing code that can be reused: `goga/runtime/paths.py` formula
  (extended, not duplicated — no second path scheme, ever);
  `resolve_git_branch` as the derived fallback; `_HistoryScope`/
  group-command pattern; the pipeline dash-guard message family; the
  `tests/runtime/test_paths.py` fixture trio; `tests/conftest.py` env
  scrub.
- Missing visibility in workspace or git: the apply-stage contract and
  usage files are present but UNCOMMITTED (Task 1 commits them; nothing in
  this plan modifies them).

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed
> before starting the next. Within each coding task, contract tests are
> written first (TDD workflow). Order: `goga/runtime` (Task 2) →
> `goga/commands/runtime` (Tasks 3–5) → facades (Task 6) → integration
> (Task 7).

### Task 1: Bootstrap the virtualenv, commit the applied contracts, verify the baseline gates (infrastructure)

This task creates/verifies the execution environment every subsequent task
runs in, commits the already-applied contract and usage artifacts so
per-task commits isolate code changes, and proves the PRE-change tree is
green, so any later failure is attributable to the change under test. No
contract entity is touched.

**Usages relevant to this task:**
- `convention`: virtualenv execution ("create it if missing"),
  `pyproject.toml` as the configuration home, validation-command table.
- `ralphex` (`.goga/usages/cooks/ralphex.md`): plans execute task-by-task
  with a commit after each completed task — the working tree must be clean
  apart from the plan file before execution starts.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Verify the virtualenv (create if missing): `.venv` with
  `.venv/bin/pip install -e ".[test]"` (verified during planning: Python
  3.12.16, click 8.5.1, pytest, ruff 0.17.6)
- [x] Verify the baseline test battery: `.venv/bin/pytest tests/ -x` —
  green BEFORE any change (planning baseline: 8391 passed, 8 skipped)
- [x] Verify the baseline lint gates: `.venv/bin/ruff check goga/ tests/`
  and `.venv/bin/ruff format --check goga/ tests/` — zero findings
- [x] Verify the cell-level lint: `goga lint` — 94 cells, 0 errors
- [x] Verify the pre-change facade imports of every touched cell:
  `.venv/bin/python -c "from goga.runtime import resolve_runtime_dir, resolve_git_branch; from goga.docker import is_in_docker; from goga.commands import history, build, pipeline"`
- [x] Commit the apply-stage contract/usage artifacts now present in the
  working tree (`goga/commands/runtime/` manifest + `.usages/`,
  `goga/runtime/CODEMANIFEST` + `.usages/runtime-paths.md`,
  `goga/commands/CODEMANIFEST` + `.usages/cli-commands.md`,
  `goga/CODEMANIFEST`, `.goga/usages/cooks/{click,tarfile}.md`) and the
  topic history artifacts `.goga/history/2026/add-runtime-command/`
  (adr.md, arch.md, design.md, prd.md, task.md, todo.md; plan.md itself
  may stay uncommitted — ralphex allows "except the plan file") — message
  without `Co-Authored-By:` trailers; working tree clean afterwards apart
  from the plan file
  (already satisfied by HEAD 4c0c9b9d "feat: specify the runtime command
  cell across contracts and usages" — all 17 artifacts verified in its
  stat; working tree clean)
- [x] Record the baseline results; a red baseline is reported, not
  silently absorbed
  (baseline recorded: Python 3.12.16, click 8.5.1, pytest 9.2.0,
  pytest-cov 7.1.0, ruff 0.17.6, editable install; battery 8391 passed,
  8 skipped in 51.93s; ruff check + format --check zero findings;
  goga lint 94 cells / 0 errors; facade imports green — all green, no
  red findings to report)

### Task 2: `resolve_runtime_dir` — the keyword-only `branch` extension (TDD)

This task implements the ONE changed leaf entity (cell `goga/runtime`,
`location: paths.py`): `resolve_runtime_dir` gains `branch: str | None =
None` as a keyword-only parameter after `*suffix_parts`. Behavior for
existing callers (no `branch`) is bit-identical: the parameter defaults to
`None`, existing positional calls bind unchanged. Every other task builds
on this (the target routines pass `branch=segment`).

**Usages relevant to this task:**
- `runtime-paths` (imported usage, `goga/runtime/.usages/runtime-paths.md`):
  the facade pattern gains the explicit-branch form —
  `resolve_runtime_dir("builds", branch="feature/x")` →
  `~/.goga/runtime/builds/<normalized>/feature-x`; "one formula, no second
  path scheme".
- `convention`: Google docstrings (document `branch` in `Args:`), relative
  imports N/A here (no new imports), REPL cycle (probe the one-formula
  invariant live before pinning).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): in
  `tests/runtime/test_paths.py` — UPDATE the hard-failing
  `TestPathsContract::test_resolve_runtime_dir_signature` to the extended
  signature: `params == ["purpose", "suffix_parts", "branch"]`;
  `sig.parameters["branch"].kind == inspect.Parameter.KEYWORD_ONLY`;
  annotation `Optional[str]`, default `None` (the file's existing
  `typing.get_type_hints` style); keep the `purpose`/`suffix_parts` kind
  assertions unchanged
- [x] **REPL probe** (before writing code): with cwd/home patched and git
  mocked — `resolve_runtime_dir("builds", branch="feature/x")` equals
  `resolve_runtime_dir("builds")` under a git mock returning `feature/x\n`
  (one formula); with `branch="feature/x"` the `subprocess.run` mock's
  `call_count` does not increase (git-free); `branch=""` still consults git
- [x] **Code**: change the signature to
  `def resolve_runtime_dir(purpose: str, *suffix_parts: str, branch: str | None = None) -> Path:`
  and the body to the manifest Algorithm (verbatim):
  ```
  1. cwd = Path.cwd(); normalized = normalize_project_path(cwd)
  2. segment = branch.replace("/", "-") IF branch ELSE resolve_git_branch()
  3. runtime_dir = Path.home()/".goga"/"runtime"/purpose/normalized/segment
  4. for part in suffix_parts: runtime_dir = runtime_dir / part
  5. RETURN runtime_dir
  ```
  (`""` is falsy ⇒ derived form; no git subprocess when explicit)
- [x] **Code**: extend the docstring `Args:` with `branch` per the manifest
  annotation (optional explicit branch segment; None or the empty string
  means "not given" — git-derived with the "default" fallback; a non-empty
  value is slugified by the same rule and used directly — no git, no
  validation) and the `Returns:` shape with the unchanged formula
- [x] **Interface verification**: `.venv/bin/pytest tests/runtime/ -x` —
  all pass
- [x] **Logic tests** (in `tests/runtime/test_paths.py`, verbatim from the
  design's Test Stack Trace):
  - `test_resolve_runtime_dir_explicit_branch_matches_derived_form` —
    Setup: cwd/home patched; git mocked to `feature/x\n`. Input:
    `resolve_runtime_dir("builds", branch="feature/x")` vs
    `resolve_runtime_dir("builds")`. Assert: `explicit == derived`; the git
    mock `call_count` is unchanged when `branch` is explicit (git-free
    path). Sufficiency: ADR "one formula" invariant + "no subprocess when
    explicit".
  - `test_resolve_runtime_dir_empty_branch_falls_back_to_derived` — Input:
    `branch=""` with git mocked to `main\n`. Assert: result segment ==
    `"main"` (empty string means not given).
  - `test_resolve_runtime_dir_slugification_idempotent` — Input:
    `branch="feature-x"` (already slugified). Assert: result segment ==
    `"feature-x"` (passes through unchanged).
- [x] **Debugging**: `.venv/bin/pytest tests/runtime/ tests/commands/build/
  tests/commands/pipeline/ -x` — fix implementation code until all pass
  (do NOT fix test code); the build/pipeline suites prove the two existing
  callers are unaffected (positional binding unchanged)
  (484 passed first try — no fix needed; the update to the signature test
  was the planned TDD edit, not a fix)
- [x] **Contract re-verification**: facade import
  `from goga.runtime import resolve_runtime_dir` green; signature kinds:
  `purpose` POSITIONAL_OR_KEYWORD, `suffix_parts` VAR_POSITIONAL, `branch`
  KEYWORD_ONLY; no other routine in `paths.py` changed
  (`git diff --stat goga/` → only `paths.py`, 11 insertions / 3 deletions)
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/` — fix formatting if
  necessary; then `.venv/bin/pytest tests/ -x` (full battery) and `goga
  lint` (94 cells, 0 errors) before committing
  (ruff zero findings; battery 8394 passed / 8 skipped — baseline 8391 +
  the 3 new logic tests; goga lint 94/0)
- [x] Verify `goga/runtime/.usages/runtime-paths.md` stays truthful for the
  extended surface (no edit expected — the apply stage already documented
  the explicit-branch section; report any drift)
  (verified against the implementation — extended signature, explicit-branch
  example, git-skip side effect, no-validation claims all truthful; no drift)

### Task 3: `goga/commands/runtime` cell skeleton + `targets.py` — the four target routines (TDD)

This task makes the new cell importable and implements its four pure
target/branch routines (entity block 1 of the cell contract, `location:
targets.py`): `resolve_effective_branch`, `resolve_build_target_dir`,
`sanitize_pipeline_name`, `resolve_pipeline_target_dir`. All four are thin,
pure delegations over the shared formula — no second path scheme. The
archive routines (Task 4) and the group (Task 5) import from this module.

**Usages relevant to this task:**
- `runtime-paths` (from Imports): the consumer facade pattern — fixed
  purpose, optional suffix, `branch=segment` keyword; the path shape and
  purity guarantees ("the directory is not created").
- `convention`: relative imports (`from ...runtime import
  resolve_runtime_dir, resolve_git_branch`), Google docstrings, mirror
  tests at `tests/commands/runtime/test_targets.py`, mocks only at the git
  subprocess boundary.
- `click` (context only): these routines carry no click surface — they are
  the pure layer beneath the group.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Cell skeleton** (infrastructure, before anything is importable):
  create `goga/commands/runtime/__init__.py` — module docstring + the four
  target-routine imports from `.targets` + `__all__` listing exactly those
  four names (the facade grows in Tasks 4–5 as entities land; the
  `goga/commands/build/__init__.py` pattern); create
  `tests/commands/runtime/__init__.py` (every test directory MUST carry
  one)
- [x] **Contract tests** (expected to fail at this stage): create
  `tests/commands/runtime/test_targets.py` — facade import of all four
  from `goga.commands.runtime`; signature pins (the
  `tests/runtime/test_paths.py` style): `resolve_effective_branch(branch:
  str | None = None) -> str`; `resolve_build_target_dir(branch_segment:
  str) -> Path`; `sanitize_pipeline_name(name: str) -> str`;
  `resolve_pipeline_target_dir(pipeline_name: str, branch_segment: str) ->
  Path` (parameter names, kinds, `get_type_hints` return types)
- [x] **REPL probe** (before writing code): confirm the empty-segment edge
  the guards of Task 5 exist for — `Path("/a/b") / ""` returns `/a/b`
  (path composition silently drops an empty suffix part; verified at
  design review — this is why an empty NAME must never reach the formula)
- [x] **Code**: create `goga/commands/runtime/targets.py` with the four
  routines, algorithms verbatim from the design:
  ```
  resolve_effective_branch(branch: str | None = None) -> str:
  1. IF branch (non-empty): RETURN branch.replace("/", "-")
  2. RETURN resolve_git_branch()

  resolve_build_target_dir(branch_segment: str) -> Path:
  1. RETURN resolve_runtime_dir("builds", branch=branch_segment)

  sanitize_pipeline_name(name: str) -> str:
  1. RETURN name.replace(":", "-")

  resolve_pipeline_target_dir(pipeline_name: str, branch_segment: str) -> Path:
  1. sanitized = sanitize_pipeline_name(pipeline_name)
  2. RETURN resolve_runtime_dir("pipelines", sanitized, branch=branch_segment)
  ```
  Google docstrings per the manifest annotations (each `Args:`/`Returns:`
  from the CODEMANIFEST text: e.g. `branch` — the raw group option value;
  None and the empty string mean no branch given; `sanitized` — the
  colon-free segment, the same transformation the run composes). Imports:
  `from ...runtime import resolve_git_branch, resolve_runtime_dir`
  (relative); `from pathlib import Path`
- [x] **Interface verification**: `.venv/bin/pytest
  tests/commands/runtime/test_targets.py -x` — all pass; facade check
  `.venv/bin/python -c "from goga.commands.runtime import
  resolve_effective_branch, resolve_build_target_dir,
  sanitize_pipeline_name, resolve_pipeline_target_dir"`
- [x] **Logic tests** (in `tests/commands/runtime/test_targets.py`,
  verbatim from the design's Test Stack Trace; git mocked only for the
  derived cases — pure logic stays mock-free):
  - `test_resolve_effective_branch_contract_matrix` — parametrized:
    `(None → derived)`, `("" → derived)`, `("a/b" → "a-b")`, `("a-b" →
    "a-b")`; each maps as stated; the derived cases mock git (the
    CompletedProcess pattern). Sufficiency: R2/ADR effective-branch
    semantics in one table.
  - `test_sanitize_pipeline_name_literal_replacement` — Input: `"py:bug:
    gy:"`, `"plain"`, `""`. Assert: `"py-bug-gy-"`, `"plain"`, `""` —
    literal 1:1, no collapsing/trimming.
  - Parity pins (the design's trace checkpoints, as direct assertions):
    `resolve_build_target_dir("feature-x")` equals
    `resolve_runtime_dir("builds", branch="feature-x")` (the
    `build.py:274` purpose); `resolve_pipeline_target_dir("pybuggy:api",
    "main")` equals `resolve_runtime_dir("pipelines", "pybuggy-api",
    branch="main")` — i.e. the exact composition of
    `run_pipeline_container.py:153`
    (`resolve_runtime_dir("pipelines", pipeline_name.replace(":", "-"))`)
    for that name/branch (same purpose, same sanitization, same formula).
  - Purity: none of the four creates anything on disk (`not
    result.exists()` in the tmp fixture world; the routines never mkdir).
- [x] **Debugging**: `.venv/bin/pytest tests/commands/runtime/ -x` — fix
  implementation code until all pass (do NOT fix test code)
  (14 passed first try — no fix needed)
- [x] **Contract re-verification**: facade `__all__` exposes exactly the
  four landed names; signatures match the manifest block above; no extra
  public names added to the module
  (verified — the module namespace carries only the four defs plus imports;
  the facade is `__all__`, exactly the four names)
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/` — fix formatting if
  necessary; then the full battery `.venv/bin/pytest tests/ -x` and `goga
  lint` before committing
  (one format finding collapsed by `ruff format`, gates clean after; battery
  8408 passed / 8 skipped — 8394 baseline + the 14 new tests; goga lint 94
  cells / 0 errors)

### Task 4: `archive.py` — `resolve_archive_destination` + `package_runtime_archive` (TDD)

This task implements entity block 2 of the cell contract (`location:
archive.py`): the destination resolver (pure validation) and the packaging
routine (the only effectful entity of the feature). The guarded cleanup is
CONTRACTUAL (design Fix 2): unlink the destination only when the archive
was successfully opened — never apply the tarfile cook's unconditional
snippet in the explicit-destination case.

**Usages relevant to this task:**
- `tarfile` (`.goga/usages/cooks/tarfile.md`): `tarfile.open(dest, "w:gz")`
  creates/truncates at open (unwritable ⇒ `OSError` before any data);
  `tar.add(target_dir, arcname=wrapper_root)` (recursive default,
  `dereference=False` — symlinks preserved, no filter — "full recursive
  contents, as encountered"); self-archiving guard; the GUARDED
  cleanup-on-failure snippet (`opened = False` … unlink only `if opened`).
- `convention`: mocks only at external boundaries (the mid-packaging
  failure is injected via `mock.patch.object(tarfile.TarFile, "add",
  side_effect=OSError)`); `tmp_path` for all file I/O; `pytest.raises` for
  expected exceptions.
- `runtime-paths` (context): the target_dir handed in is the formula's
  output; this module never recomputes paths.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): create
  `tests/commands/runtime/test_archive.py` — facade import of both routines
  from `goga.commands.runtime`; signature pins:
  `resolve_archive_destination(archive_stem: str, output: str | None =
  None) -> Path`; `package_runtime_archive(target_dir: Path, wrapper_root:
  str, destination: Path) -> Path`; extend the cell facade
  `goga/commands/runtime/__init__.py` with the two names (`__all__` grows
  to six)
  (verified red first — ImportError on the two names; green after the facade
  grew to six; the Task 3 facade pin test updated accordingly — the planned
  hard-failing change, renamed to `test_facade_all_lists_exactly_the_landed_names`)
- [x] **REPL probes** (before writing code; all under `tmp_path` via
  `.venv/bin/python -c`): `tarfile.open(dest, "w:gz")` on a `0o444`
  pre-existing file in a writable directory raises `PermissionError` at
  open (and `unlink` would succeed there — the guard is what protects the
  file); `tar.add(dir, arcname="root")` yields members `["root",
  "root/a.txt", …]` (wrapper-root layout); a symlink lands with
  `.issym()`; an archive written INSIDE the packaged tree does not include
  itself (built-in guard)
  (all four probes re-verified live — PermissionError at open + unlink
  succeeds in the writable dir; members `["root", "root/a.txt", "root/sub",
  "root/sub/b.log"]` with `root` first; `issym()` True with linkname
  `"a.txt"`; self-inclusion False)
- [x] **Code**: create `goga/commands/runtime/archive.py`, algorithms
  verbatim from the design:
  ```
  resolve_archive_destination(archive_stem: str, output: str | None = None) -> Path:
  1. IF output is None:
       destination = Path.cwd() / f"{archive_stem}.tar.gz"
       IF destination.exists(): raise ClickException(collision, point to -o/--output)
       RETURN destination
  2. path = Path(output); destination = path if path.is_absolute() else Path.cwd() / path
     IF destination.is_dir(): raise ClickException(existing directory)
     IF not destination.parent.is_dir(): raise ClickException(missing parent, no mkdir)
     RETURN destination

  package_runtime_archive(target_dir: Path, wrapper_root: str, destination: Path) -> Path:
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
  Per the manifest: `resolve_archive_destination` raises
  `click.ClickException`-compatible clean errors (the command layer
  requires every failure to surface as `ClickException` — raising
  `click.ClickException` here directly matches the design's trace wording
  "ClickException-equivalent clean error"); `package_runtime_archive`
  propagates raw (`OSError`) — the COMMAND layer wraps (Task 5 step 8).
  Nothing is written by the resolver; the packager writes exactly the one
  archive file. Google docstrings from the manifest annotations.
  Imports: `tarfile`, `pathlib.Path`, `click` (relative-intra rule N/A —
  no intra-package imports needed in this module)
- [x] **Interface verification**: `.venv/bin/pytest
  tests/commands/runtime/test_archive.py -x` — all pass; facade check for
  the two names
- [x] **Logic tests** (in `tests/commands/runtime/test_archive.py`;
  verbatim from the design's Test Stack Trace):
  - `test_resolve_archive_destination_matrix` — parametrized against
    `tmp_path`: default+absent → `cwd/<stem>.tar.gz`; default+exists →
    raises; explicit+relative → absolute under cwd; explicit+existing file
    → returned (overwrite intent); explicit+dir → raises; explicit+missing
    parent → raises. Sufficiency: R9–R11 + strict destination semantics in
    one boundary table.
  - `test_package_runtime_archive_wrapper_root_layout` (the routine-level
    positive from the design's package trace): target with `a.txt` and
    nested `sub/b.log` → returned path is the destination, file exists,
    `tarfile.open(dest).getnames()[0] == wrapper_root` and both
    `<root>/a.txt`, `<root>/sub/b.log` present. Sufficiency: checkpoint
    "members `["<root>", "<root>/a.txt"]` — passed".
  - `test_package_runtime_archive_failure_leaves_no_partial` — Setup:
    target with files; destination = fresh path; make `tar.add` raise
    mid-packaging (`mock.patch.object(tarfile.TarFile, "add",
    side_effect=OSError)`). Trace: open succeeds (file created) → add
    raises → except: unlink → raise. Assert: `pytest.raises(OSError)`;
    `not destination.exists()` (partial removed). Sufficiency: ADR —
    nothing partial is kept.
  - `test_package_runtime_archive_open_failure_keeps_preexisting_file` —
    Setup: destination pre-created with content and made read-only
    (`chmod 0o444`) in a writable dir (explicit-`-o` overwrite scenario).
    Trace: open raises `PermissionError` (`opened == False`) → guarded
    cleanup: NO unlink → raise. Assert: `pytest.raises(PermissionError)`;
    `destination.exists()`; `destination.read_text() == original content`.
    Sufficiency: Fix 2 regression guard — a failure before open never
    deletes a pre-existing destination file.
  - `test_package_runtime_archive_symlinks_preserved` — Setup: target
    contains a symlink `link -> a.txt`. Assert:
    `tarfile.open(dest).getmember("<root>/link").issym()` is True (no
    dereference). Sufficiency: R7 "special files preserved as encountered".
- [x] **Debugging**: `.venv/bin/pytest tests/commands/runtime/ -x` — fix
  implementation code until all pass (do NOT fix test code)
  (implementation needed no fix — two TEST-AUTHORING defects corrected, both
  making assertions stricter, never weaker: the `default-exists` matrix row
  never created its collision precondition, and the purity test asserted an
  empty `tmp_path` that the autouse `_isolate_home` fixture seeds with
  `.pytest_home` — the check moved to a dedicated `work/` cwd)
- [x] **Contract re-verification**: facade `__all__` = the six landed
  names; `resolve_archive_destination` writes NOTHING (validation only);
  the cleanup is the guarded form (unlink only after a successful open);
  the source directory is read-only throughout (no modification, move,
  deletion inside `target_dir`)
  (verified live: facade exposes exactly the six names; the purity and
  source-snapshot assertions are pinned in `test_archive.py`)
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/` — fix formatting if
  necessary; then the full battery and `goga lint` before committing
  (one I001 import-order autofix + SIM117/PT011 test edits + two collapsed
  lines by `ruff format`; gates clean after; battery 8423 passed / 8 skipped
  — 8408 baseline + the 15 new archive tests; goga lint 94 cells / 0 errors)

### Task 5: `runtime.py` — the click group with `build` / `pipeline` / `archive` (TDD)

This task implements the cell's headline entity (`location: runtime.py`):
the `runtime` click.Group carrying the branch scope, and its three
subcommands. It wires the Task 3/4 routines into the CLI surface with the
project's cross-cutting error strategy. The two review guards (empty NAME,
empty/dash `-p` value) and the OSError wrap live HERE — without them the
branch-level directory is printed/packaged (empty segment silently
dropped) or a traceback escapes.

**Usages relevant to this task:**
- `click` (`.goga/usages/cooks/click.md`): `@click.group()` +
  `@click.option("--branch", "-b", default=None, help=...)` (ALWAYS give
  `help`) + `@click.pass_context` + `ctx.ensure_object(_RuntimeScope)`;
  subcommands via `@runtime.command("build"|"pipeline"|"archive")` +
  `@click.pass_obj`; "Option positioning in nested groups" (group options
  bind only before the subcommand token — dual `-b` is safe); state class
  instead of a dict; `click.echo` (never `print`); `click.ClickException`
  for errors (never `sys.exit`); `CliRunner` in tests.
- `convention`: the CLI-command docstring rule (docstring = `--help` text;
  no Args/Returns/Raises; `\f` for dev notes; the group's help documents
  both `-b` meanings); `_RuntimeScope` as `@dataclass(kw_only=True)`;
  boundary mocks in tests (`GOGA_DOCKER` via monkeypatch, git via
  `mock.patch.object(subprocess, "run")`, `Path.home` via monkeypatch).
- `tarfile` (via `package_runtime_archive`): the OSError wrap point.
- `runtime-paths`: the location identity behind every printed path.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (expected to fail at this stage): create
  `tests/commands/runtime/test_runtime.py` — `from
  goga.commands.runtime import runtime`: `isinstance(runtime,
  click.Group)`; subcommands `{"build", "pipeline", "archive"}` registered
  (`set(runtime.commands) == {...}`); the group carries a `--branch/-b`
  option; `pipeline` carries the required NAME argument; `archive` carries
  `-b/--build` (flag), `-p/--pipeline`, `-o/--output`;
  `test_bare_runtime_group_prints_help_nonzero` — `invoke(runtime, [])` →
  `result.exit_code == 2` (click group default — matches bare `goga
  history`; pins corrected Fix 1, prevents re-introducing the ADR's wrong
  exit-0 assumption); help text rendered. Extend the cell facade
  `__init__.py` with `runtime` (`__all__` = all seven contract names)
  (verified red first — ImportError on `runtime`; green after the facade
  grew to the seven names; the Task 3/4 facade pin test updated to the
  seven names — the planned hard-failing change)
- [x] **REPL probes** (before writing code; fresh `.venv/bin/python -c`
  per probe — never trust stale module state): `["-b", "main", "archive",
  "-b"]` parses with group branch `"main"` and subcommand `build=True`
  (dual `-b` disjoint); `--branch=` arrives as `""`; `["pipeline", ""]`
  delivers `name=""`; `["pipeline", "--", "-weird"]` delivers
  `name="-weird"`; `-p -weird` delivers a dash-leading value;
  `["build", "-b"]` is a usage error (build carries no options)
  (all six re-verified live on click 8.5.1 with a scratch group mirroring
  the surface: dual `-b` exit 0 with `build=True`; `--branch=` → `""`;
  empty/dash NAME delivered verbatim; `-p -weird` taken as the value;
  `["q", "-b"]` → exit 2 "No such option '-b'"; bare group → exit 2)
- [x] **Code**: create `goga/commands/runtime/runtime.py`, implementation
  shape verbatim from the design:
  ```
  1. module runtime.py — imports: click; from ...docker import is_in_docker
     (relative per `convention`; three dots — the module lives in
     `goga.commands.runtime`, one level deeper than `goga/commands/*.py`
     modules like `pipeline.py`; the `history` precedent
     `goga/commands/history/history.py:10` uses the same depth); from
     .targets import ...; from .archive import ...
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
  Subcommand algorithms verbatim from the design:
  ```
  build(scope):
  1. IF is_in_docker(): raise ClickException(host-side-only message) → exit 1
  2. segment = resolve_effective_branch(scope.branch)
  3. target_dir = resolve_build_target_dir(segment)
  4. click.echo(target_dir) → exactly one stdout line

  pipeline(scope, name):
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

  archive(scope, build, pipeline, output):
  1. IF is_in_docker(): refuse
  2. IF (build == pipeline_given) i.e. neither or both:
       raise ClickException("exactly one target: -b/--build or -p/--pipeline NAME")
     IF pipeline is not None and (pipeline == "" OR pipeline.startswith("-")):
       raise ClickException(f"invalid pipeline name {pipeline!r}")
     (the empty value would address the branch-level directory — path
     composition silently drops an empty suffix part — and package the
     whole branch state)
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
  In-image refusal message: human-readable, contains "host" (e.g. "goga
  runtime is a host-side command — state does not live at the runtime
  formula inside the goga image"); click decorators per the surfaces:
  `pipeline` gets `@click.argument("name")`; `archive` gets
  `--build/-b` `is_flag=True`, `--pipeline/-p` `default=None`,
  `--output/-o` `default=None` — every option with `help`. Docstrings =
  `--help` texts per the convention CLI rule
- [x] **Interface verification**: `.venv/bin/pytest
  tests/commands/runtime/test_runtime.py -x` — all pass; facade check
  `.venv/bin/python -c "from goga.commands.runtime import runtime"`
  (27 passed in test_runtime.py; the group import and the full 7-name
  facade import both green)
- [x] **Logic tests** (in `tests/commands/runtime/test_runtime.py`;
  verbatim from the design's Test Stack Trace — General Setup: pytest +
  CliRunner; boundary mocks only: git via `mock.patch.object(subprocess,
  "run", ...)` with the CompletedProcess pattern, `GOGA_DOCKER` via
  `monkeypatch.setenv/delenv`, `Path.home` via
  `monkeypatch.setattr(Path, "home", lambda: Path("/Users/tester"))` +
  `monkeypatch.chdir(tmp_path)`; `tests/conftest.py` already scrubs
  `GOGA_DOCKER`):
  - **Positives**
    - `test_runtime_build_prints_build_dir_single_line` — Setup:
      chdir+home patched; git mocked `feature/x\n`; `GOGA_DOCKER`
      deleted. Input: `invoke(runtime, ["build"])`. Assert:
      `exit_code == 0`; `output.strip() == str(Path("/Users/tester/
      .goga/runtime/builds") / cwd_segment / "feature-x")`;
      `len(output.strip().splitlines()) == 1`; `not target.exists()`
      (purity). Sufficiency: SC1/SC3 — the printed line equals the
      directory `goga build` uses (same purpose/formula as `build.py:274`);
      single-line stdout; purity.
    - `test_runtime_pipeline_sanitizes_colons_like_run_time` — Setup: git
      mocked `main\n`. Input: `invoke(runtime, ["pipeline",
      "pybuggy:api-feature"])`. Assert: `exit_code == 0`;
      `output.strip().endswith("/pipelines/<cwd-seg>/main/
      pybuggy-api-feature")`. Sufficiency: SC2 — `:` sanitization parity
      with `run_pipeline_container.py:153`.
    - `test_runtime_archive_build_target_creates_wrapper_root_archive` —
      Setup: `home_dir = tmp_path/"home"` with `Path.home` patched to it;
      target `home_dir/".goga/runtime/builds"/<cwd-seg>/"feature-x"`
      containing `a.txt` ("hello") and nested `sub/b.log`; cwd = separate
      `tmp_path/"work"`. Input: `invoke(runtime, ["archive", "-b"])`.
      Assert: `exit_code == 0`; `archive = Path(output.strip())`;
      `archive.is_file()`; `tarfile.open(archive).getnames()`:
      `names[0] == "goga-runtime-build-feature-x"`, contains
      `.../a.txt` and `.../sub/b.log`. Sufficiency: SC4/SC7/SC9-positive —
      wrapper-root layout, standard-tool openability, one-line stdout.
    - `test_runtime_archive_pipeline_target_and_explicit_output` — Setup:
      target under `pipelines/.../<name>`; pre-existing file at the
      explicit destination (overwrite intent); git → `main`. Input:
      `invoke(runtime, ["archive", "-p", "pybuggy:api", "-o",
      str(out_path)])`. Assert: `exit_code == 0`; `out_path.is_file()`;
      `tarfile.open(out_path).getnames()[0] ==
      "goga-runtime-pybuggy-api-main"`. Sufficiency: SC5 + R10.
    - `test_runtime_branch_option_overrides_segment` — Setup: git mocked
      `main\n` (must NOT be consulted); build target tree exists for
      `release-1.2` under `builds/<cwd-seg>/release-1.2`. Input:
      `invoke(runtime, ["-b", "release/1.2", "build"])`. Assert:
      `exit_code == 0`; `output.strip().endswith("/builds/<cwd-seg>/
      release-1.2")` (`/`→`-` slugification; no git call — the mock
      asserts git unused). Sufficiency: ADR branch override.
    - `test_runtime_dual_b_parses_at_both_levels` — Setup: git → `main`;
      build target exists. Input: `invoke(runtime, ["-b", "main",
      "archive", "-b"])`. Assert: `exit_code == 0`; output contains
      `"goga-runtime-build-main"`. Sufficiency: task acceptance — dual
      `-b` binds at its own level.
  - **Negatives**
    - `test_runtime_subcommands_refuse_inside_image` — Setup:
      `monkeypatch.setenv("GOGA_DOCKER", "1")`. Input: `invoke(runtime,
      [x])` for `x` in `["build"]`, `["pipeline", "p"]`, `["archive",
      "-b"]`. Assert: `exit_code == 1` for each; `"host" in
      result.stderr.lower()`; `result.stdout == ""`. Sufficiency: in-image
      refusal for every subcommand (task item 5).
    - `test_runtime_archive_target_selection_usage_errors` — Input:
      `invoke(runtime, ["archive"])` and `invoke(runtime, ["archive",
      "-b", "-p", "x"])`. Assert: `exit_code != 0` for both; `"exactly
      one"` (or equivalent) in stderr; `list(cwd.glob("*.tar.gz")) ==
      []`. Sufficiency: R6/SC10.
    - `test_runtime_pipeline_dash_leading_name_is_clean_error` — Input:
      `invoke(runtime, ["pipeline", "--", "-weird"])`. Assert:
      `exit_code == 1`; `"invalid pipeline name"` in stderr. Sufficiency:
      ADR argv-parsability; mirrors `pipeline.py:313`.
    - `test_runtime_pipeline_empty_name_is_clean_error` — Input:
      `invoke(runtime, ["pipeline", ""])`. Trace: click delivers `name=""`
      → guard → `ClickException("invalid pipeline name ''")` → stderr,
      exit 1; no path composed, no stdout. Assert: `exit_code == 1`;
      `"invalid pipeline name"` in stderr; `result.stdout == ""`.
      Sufficiency: review fix (empty-segment guard) — without it,
      `Path("/a/b") / ""` silently drops the segment and the branch-level
      directory is printed.
    - `test_runtime_archive_empty_pipeline_value_is_clean_error` — Setup:
      git → `feature-x`; cwd empty. Input: `invoke(runtime, ["archive",
      "-p", ""])`. Assert: `exit_code == 1`; `"invalid pipeline name"` in
      stderr; `list(cwd.glob("*.tar.gz")) == []`. Sufficiency: review fix
      — without it the whole branch state is packaged under stem
      `goga-runtime--<segment>`.
    - `test_runtime_archive_pipeline_dash_value_is_clean_error` — Setup:
      git → `feature-x`; cwd empty; no in-image marker. Input:
      `invoke(runtime, ["archive", "-p", "-weird"])`. Trace: click
      delivers `pipeline="-weird"` (verified: a dash-leading token is
      taken as the option's value, even when it matches another option
      name) → dash guard → ClickException. Assert: `exit_code == 1`;
      `"invalid pipeline name"` in stderr; `result.stdout == ""`;
      `list(cwd.glob("*.tar.gz")) == []`. Sufficiency: pins the archive
      arm of the argv-parsability guard (the `--pipeline=-weird` form
      reaches the same guard).
    - `test_runtime_pipeline_missing_name_is_usage_error` — Input:
      `invoke(runtime, ["pipeline"])`. Assert: `result.exit_code == 2`
      (click usage error; non-zero — R4).
    - `test_runtime_archive_missing_target_names_path_no_archive` —
      Setup: git → `feature-x`; no `builds/<cwd-seg>/feature-x`
      directory; cwd empty. Input: `invoke(runtime, ["archive", "-b"])`.
      Assert: `exit_code == 1`; `str(expected_missing_path)` in stderr;
      `list(cwd.glob("*.tar.gz")) == []`. Sufficiency: R13/SC8.
    - `test_runtime_archive_default_name_collision_refused` — Setup:
      pre-create `cwd/goga-runtime-build-<seg>.tar.gz`; target exists.
      Input: `invoke(runtime, ["archive", "-b"])`. Assert: `exit_code ==
      1`; `-o`/`--output` referenced in stderr; pre-existing file content
      unchanged. Sufficiency: R11/SC9.
    - `test_runtime_archive_output_directory_is_error` — Input:
      `invoke(runtime, ["archive", "-b", "-o", str(tmp_path)])` (an
      existing directory). Assert: `exit_code == 1`; directory unmodified;
      no archive elsewhere.
    - `test_runtime_archive_output_missing_parent_is_error` — Input: `-o
      <tmp_path>/no/such/dir/a.tar.gz`. Assert: `exit_code == 1`;
      `"no/such/dir"` not created (no implicit mkdir).
    - `test_runtime_archive_unwritable_destination_is_clean_error` (pins
      the manifest Requirement "An OSError from the packaging step
      surfaces as a clean error — no traceback reaches the user"; design
      archive trace step 8 / review Fix 2's end-to-end arm) — Setup:
      target exists; destination pre-created read-only (`chmod 0o444`) in
      a writable dir; git → `feature-x`. Input: `invoke(runtime,
      ["archive", "-b", "-o", str(dest)])`. Assert: `exit_code == 1`;
      `"Error:"` in stderr (ClickException rendering); no `Traceback` in
      output; the pre-existing file's content unchanged (guarded cleanup).
  - **Edge**
    - `test_runtime_archive_empty_target_directory_packages` — Setup:
      target dir exists, empty. Assert: exit 0; archive contains only the
      wrapper root member. Sufficiency: ADR — "directory exists → we
      package it".
    - `test_runtime_group_option_only_before_subcommand` — Input:
      `invoke(runtime, ["build", "-b"])`. Assert: non-zero exit, usage
      error — `build` carries no options; the dual `-b` exists only on
      `archive` (after the token) and the group (before).
- [x] **Debugging**: `.venv/bin/pytest tests/commands/runtime/ -x` — fix
  implementation code until all pass (do NOT fix test code)
  (56 passed first try — no fix needed; the one `ruff format` pass
  collapsed four test signatures to single lines, formatting only)
- [x] **Contract re-verification**: `runtime` is a `click.Group` in the
  cell facade `__all__` (7 names total); bare group exits 2; every
  documented failure is a `ClickException` (exit 1) except click-native
  usage failures (exit 2); stdout carries exactly one result line on
  success and nothing on failure; validation strictly ordered (in-image →
  argv → selection → branch → existence → destination → packaging)
  (verified — the ordering is literal in the callback bodies; the
  exit-1/exit-2 split, empty stdout on failure, and single-line stdout on
  success are pinned by the 20 logic scenarios)
- [x] **Lint**: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/` — fix formatting if
  necessary; then the full battery and `goga lint` before committing
  (ruff check zero findings; one format pass then zero reformattings;
  battery 8450 passed / 8 skipped — 8423 baseline + the 27 new tests;
  goga lint 94 cells / 0 errors)
- [x] Verify `goga/commands/runtime/.usages/path-queries.md` and
  `.usages/archive.md` stay truthful against the implemented behavior (no
  edit expected — both are current per the design's `.usages/` Update
  section; report any drift)
  (verified against the implementation — one-line stdout, branch override
  with empty-means-not-given, sanitization parity, dual `-b`, destination
  semantics, collision/-o pointer, no-partial guarantees, host-side
  refusal all truthful; no drift)

### Task 6: Facade re-export and root registration — `goga/commands` + `goga/cli.py` (TDD)

This task completes the wiring demanded by `goga/commands/CODEMANIFEST`
(the `->runtime: {}` embedding and the `runtime` import) and the root
`goga` cell (`runtime` in the `app()` Commands list): the commands facade
re-exports `runtime`, and `goga/cli.py` registers it. After this task the
command is a real `goga` CLI surface.

**Usages relevant to this task:**
- `click` (`.goga/usages/cooks/click.md`): "Registering Commands in the
  Root Group" — import + `app.add_command(command)`; every new command
  MUST go through the registration procedure.
- `cli-commands` (`goga/commands/.usages/cli-commands.md`): the 19-command
  facade documentation — `runtime` is already in every snippet and the
  table; this task makes the code match the documentation.
- `convention`: facade rule — only identifiers in `__all__` constitute the
  facade; mirror facade tests.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (expected to fail at this stage): extend
  `tests/commands/test_commands_facade.py` — `runtime` re-exported from
  the facade (`from goga.commands import runtime as runtime_reexport`;
  `runtime_reexport is runtime_source` — the same object, not a copy);
  `"runtime" in commands.__all__`; `isinstance(runtime_reexport,
  click.Group)` with exactly the three subcommands; and the ROOT app
  carries it: `from goga import app` → `"runtime" in app.commands` (the
  existing test file's `Test*Facade` class pattern)
- [ ] **Code**: `goga/commands/__init__.py` — add `from .runtime import
  runtime` (import block is alphabetical: after `.pipeline`, before
  `.schema`) and the `"runtime"` entry in `__all__` (alphabetical, between
  `"pipeline"` and `"schema"`)
- [ ] **Code**: `goga/cli.py` — add `runtime` to the
  `from .commands import (...)` import list and
  `app.add_command(runtime)` (the existing block, `goga/cli.py:70-87`)
- [ ] **Interface verification**: `.venv/bin/pytest
  tests/commands/test_commands_facade.py tests/test_cli.py -x` — all pass
- [ ] **Smoke checks** (the design's Additional Instructions, verbatim):
  `.venv/bin/python -c "from goga.commands.runtime import runtime"` green;
  `goga --help` lists `runtime`; `goga runtime --help` renders the group
  help; `goga schema --depends-on goga/commands/runtime` shows the new
  subcell with its `goga/runtime` + `goga/docker` dependencies
- [ ] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation
  code until all pass (do NOT fix test code)
- [ ] **Contract re-verification**: `goga lint` — 94 cells, 0 errors;
  `goga schema` resolves the full dependency map; facade imports of all
  three touched cells green (see Validation Commands)
- [ ] **Lint**: `.venv/bin/ruff check goga/ tests/` and
  `.venv/bin/ruff format --check goga/ tests/` — fix formatting if
  necessary; then the full battery before committing
- [ ] Verify `goga/commands/.usages/cli-commands.md` stays truthful (no
  edit expected — 19 commands documented, `runtime` in every snippet;
  report any drift)

### Task 7: Integration tests — root-app end-to-end and run-parity scenarios

Cross-entity scenarios spanning multiple cells (root `goga` app →
`goga/commands` facade → the runtime group → `targets`/`archive` → the
`goga/runtime` formula → the `goga/docker` marker): the registered CLI
surface driven through the REAL root app, and the location-parity
guarantees against the actual build/pipeline call sites — the acceptance
criteria that no single-cell unit test can prove.

**Usages relevant to this task:**
- `convention`: integration tests live in `tests/integration/`
  (`test_<scenario>.py`); mocks only at external boundaries (git
  subprocess, `GOGA_DOCKER` env, `Path.home`).
- `click`: CliRunner end-to-end invocations through the root group.
- `runtime-paths`: the parity contract — "one formula, no second path
  scheme".

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create `tests/integration/test_runtime_command_end_to_end.py` (the
  directory already has `__init__.py` and `conftest.py`) with a module
  docstring mapping the stitched path: root app → commands facade →
  runtime group → targets/archive → `goga/runtime` formula → docker marker
- [ ] Test the registered surface end-to-end:
  `CliRunner().invoke(app, ["runtime", "build"])` (git mocked, home/cwd
  patched, `GOGA_DOCKER` absent) → exit 0, one stdout line equal to the
  formula's output for the mocked branch; the same for
  `["runtime", "pipeline", "pybuggy:api"]` and (with a target tree in
  place) `["runtime", "archive", "-b"]` → the archive file exists at the
  printed path with the wrapper-root layout
- [ ] Test location parity with the REAL call sites (the acceptance
  criteria): with git mocked to a fixed branch and cwd/home patched,
  `invoke(app, ["runtime", "build"]).output.strip()` equals
  `resolve_build_runtime_dir()` from `goga.commands.build`
  (`build.py:274` — the directory `goga build` actually bind-mounts), and
  `invoke(app, ["runtime", "pipeline", "pybuggy:api"]).output.strip()`
  equals `resolve_pipeline_runtime_dir("pybuggy:api")` from
  `goga.commands.pipeline.run_pipeline_container`
  (`run_pipeline_container.py:153`) for the same branch — one formula, no
  second scheme
- [ ] Test the branch override end-to-end:
  `invoke(app, ["runtime", "-b", "release/1.2", "build"])` equals the
  build-parity path computed for the slugified segment `release-1.2`
  (deleted-branch state stays addressable; git unused)
- [ ] Test the in-image refusal through the root app:
  `GOGA_DOCKER=1` + `invoke(app, ["runtime", "build"])` → exit 1, "host"
  in stderr, stdout empty (the marker consult is the docker cell's, not a
  reimplementation)
- [ ] Run validation: `.venv/bin/pytest tests/integration/
  test_runtime_command_end_to_end.py -v` — all pass; then the full battery
  `.venv/bin/pytest tests/ -x`, the ruff gates, and `goga lint` (94 cells,
  0 errors) before the final commit

---

## Validation Commands

All commands run in the virtualenv (Task 1); `goga` runs on the host CLI
(`/opt/goga/bin/goga`, an editable install of this workspace):

- `.venv/bin/pytest tests/ -x`: Run all tests (the full battery)
- `.venv/bin/pytest tests/runtime/ -x`: The runtime leaf suites
- `.venv/bin/pytest tests/commands/runtime/ -x`: The new cell suites
- `.venv/bin/pytest tests/commands/test_commands_facade.py tests/test_cli.py -x`:
  The facade and root-CLI suites
- `.venv/bin/pytest tests/integration/test_runtime_command_end_to_end.py -x`:
  The integration suite
- `.venv/bin/ruff check goga/ tests/`: Lint — zero violations (the CI gate)
- `.venv/bin/ruff format --check goga/ tests/`: Format — zero
  reformattings (the CI gate)
- `goga lint`: Cell-level lint — 0 errors over 94 cells
- `.venv/bin/python -c "from goga.commands.runtime import runtime, resolve_effective_branch, resolve_build_target_dir, sanitize_pipeline_name, resolve_pipeline_target_dir, resolve_archive_destination, package_runtime_archive"`:
  New cell facade check (all 7 contract names)
- `.venv/bin/python -c "from goga.commands import runtime"`: Commands
  facade re-export check
- `.venv/bin/python -c "from goga import app; assert 'runtime' in app.commands; assert 'runtime' in app.commands['runtime'].commands"`:
  Root registration check (group + subcommands)
- `.venv/bin/python -c "from goga.runtime import resolve_runtime_dir; import inspect; assert inspect.Parameter.KEYWORD_ONLY is inspect.signature(resolve_runtime_dir).parameters['branch'].kind"`:
  Leaf signature check (keyword-only `branch`)
- `goga --help` (must list `runtime`) and `goga runtime --help`: CLI smoke
  checks
- `goga schema --depends-on goga/commands/runtime`: Dependency-map check
  (`goga/runtime` + `goga/docker` dependencies)

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
  (`runtime.py`, `targets.py`, `archive.py`, and the `paths.py` extension)
- [ ] Every contract entity is accessible from its facade
  (`goga.commands.runtime` exposes all 7 names; `goga.commands`
  re-exports `runtime`; `goga.runtime` unchanged)
- [ ] Properties and methods match the declared API (signatures pinned by
  contract tests, including the keyword-only `branch`)
- [ ] Descriptions are reflected in behavior (all manifest Algorithms,
  Requirements, and Constraints implemented — including the empty-name
  guards, the guarded cleanup, and the OSError wrap)
- [ ] Contract dependencies are met (`resolve_runtime_dir`,
  `resolve_git_branch` from `goga/runtime`; `is_in_docker` from
  `goga/docker`; `runtime-paths` imported usage applied)
- [ ] Re-exports are accessible from the facade (`->runtime: {}`)
- [ ] Every coding task followed the TDD workflow (contract tests → code →
  verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior
  within each coding task (31 named scenarios: the design's 29 — 6
  positive, 11 negative, 12 edge — plus the wrapper-root routine test and
  the unwritable-destination command test; plus contract, facade, and
  integration tests)
- [ ] Integration tests exist for the cross-entity scenarios (Task 7:
  root-app end-to-end, run-parity, branch override, in-image refusal)
- [ ] No package boundary was expanded (no new cells beyond the applied
  `goga/commands/runtime`; no new public names beyond the contract; no
  `pyproject.toml` changes)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass (full battery, ruff check + format,
  `goga lint` 94/0, facade checks, smoke checks)
- [ ] Every Usages entry is mentioned in at least one task (`convention`,
  `click`, `tarfile`, `runtime-paths`, `cli-commands`; the local usages
  `path-queries`/`archive` are verified for truthfulness)
- [ ] The Mandatory Rules held for every task and every commit: coding
  style per `conventions.md`, test rules per `conventions.md` — Testing,
  ruff lint + format gates green at each stage, no `Co-Authored-By:`
  trailers, and the REPL cycle (probe → migrate → hot feedback) followed
  in every coding task
