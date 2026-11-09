# Change Plan + Execution Report — `goga drift` failed with `AST parsing failed with 264 error(s)`

## Task Classification

Type: bugfix (producer configuration threading; one production routine, no CLI surface change).

## Task Summary

`goga drift` failed with `AST parsing failed with 264 error(s)` (exit 2) while `goga schema` and
`goga codegraph` succeeded on the same worktree (branch `release/2.1.0`). The task: find the root
cause and restore the drift report without regressing the family behavior.

## Root Cause

`drift()` (`goga/drift/drift.py`) built its declared view via `schema([], None, [])` with no
`ignore`, so the AST walk parsed every directory holding a `CODEMANIFEST` — including
`.venv/**` (third-party `swax`/`resq` packages ship their own manifests with unresolvable
imports/usages), `build/lib/goga/**` (stale build artifacts), and `example/`. Their rule
violations accumulated to exactly 264 errors and tripped the errors gate at
`goga/schema/schema.py:196` → `ValueError` → CLI exit 2.

The exclusion list (`lint.ignore: [build/, .venv/, example/]` in `.goga/config.yml`) reaches both
siblings — the schema CLI threads it into `schema()` (`goga/commands/schema/schema.py:85-88`), and
`codegraph()` reads the config itself (`goga/codegraph/codegraph.py:111-121`) — but had no
data-flow edge into `drift()`. Verified: `AST('.', ignore=None)` → 264 errors;
`AST('.', ignore=['build/', '.venv/', 'example/'])` → 0.

## Affected Cells

| Cell | Files Modified | What Changes |
|------|----------------|--------------|
| `goga/drift` | `goga/drift/drift.py` | Resolve `lint.ignore` via one `load_project_config()` call (mirroring `codegraph()`), deliver to both `schema()` calls (complete + filtered views); docstring updates |
| `goga/drift` | `goga/drift/CODEMANIFEST` | `drift` routine annotations: algorithm step 2 gains the exclusion resolution; requirements gain the same-directory-universe guarantee; constraints clarify the config read |
| `goga/drift` | `goga/drift/.usages/drift-usage.md` | Document that `lint.ignore` scopes both views (paragraph, guarantee bullet, failure-gate note) |
| tests | `tests/drift/conftest.py`, `tests/drift/test_drift.py`, `tests/commands/drift/test_drift.py` | Planter support (`lint_ignore`, dirty/agreeing vendor trees); three logic-level and one CLI-level scenario |

## Implemented Changes

| Change | File | Description |
|--------|------|-------------|
| Exclusion resolution | `goga/drift/drift.py` | Inside the existing `try`: `config = load_project_config()`; `ignore = None if config.lint is None else config.lint.ignore`; passed to both `schema()` calls; relative import `from ..config import load_project_config` |
| Module/routine docstrings | `goga/drift/drift.py` | State the one own read (project config, for the shared `lint.ignore` exclusion) and the same-directory-universe guarantee |

## Tests Added

| Test | File | What It Validates |
|------|------|-------------------|
| `test_drift_ignored_dirty_tree_does_not_abort` | `tests/drift/test_drift.py` | Rule-violating manifest under an excluded `vendor/` → empty report, no `ValueError` (fails pre-fix) |
| `test_drift_honors_lint_ignore_on_both_views` | `tests/drift/test_drift.py` | Valid excluded tree → no phantom `schema_only` entry — view symmetry (fails pre-fix) |
| `test_drift_dirty_tree_without_ignore_still_fails` | `tests/drift/test_drift.py` | Without a `lint` section the errors gate stands — `AST parsing failed` still raised (stable pre/post-fix) |
| `test_drift_cli_ignored_dirty_tree_exit_0` | `tests/commands/drift/test_drift.py` | CLI on the excluded dirty tree → exit 0, `[]`, no parse failure on stderr (fails pre-fix) |
| `_write_config(..., lint_ignore=...)`, `_plant_ignored_dirty_tree`, `_plant_ignored_agreeing_vendor` | `tests/drift/conftest.py` | Zone-style planted-project scaffolding (real producers, real config) |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|------|---------------------|---------------|
| `goga/drift` | `drift` annotations: algorithm step 2 (resolve exclusion list once, deliver to both `schema` calls), +1 requirement (same directory universe; ignored dirs contribute no cells/errors/entries), constraint clarification (config read resolves the exclusion list only). Signature, header, footer unchanged | `drift-usage.md`: `lint.ignore` paragraph in "Running the comparison", "Same directory universe" guarantee bullet, failure-list note that excluded directories never reach the manifest-validation gate |
| `goga/commands/drift` | none (annotations remain accurate) | none |

## Validation Results

**VERIFIED.** Full suite 8 270 passed / 8 skipped / 0 failed (7 817 main + 453 build zones);
`ruff check .` and `ruff format --check` clean (1 063 files); `goga lint` — 92 cells, 0 errors;
`goga drift goga/drift` → `[]` (modified cell shows zero drift); manual regression on the real
worktree — `drift` prints the 7-entry genuine content-drift report (exit 1) instead of the crash,
`schema` (exit 0) and `codegraph` (exit 0) unchanged. New fix-specific tests verified failing
against the pre-fix code via stash round-trip.

## Compatibility Status

Backward compatible at the API level (signature, defaults, return type, output format, paths,
messages, exit codes, checkpoint ordering, failure taxonomy — all preserved; 169 pre-existing
drift-zone tests green). One deliberate behavior correction, approved explicitly by the user:
on `lint.ignore`-configured projects `drift()` with the same arguments no longer aborts (the
reported bug) and no longer fabricates `schema_only` entries for ignored-but-parseable trees.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| `FileNotFoundError` on absent config now fires from drift's own read (earlier within the same stage) | Low | Same loader, same message, still inside the `try` — crashed completion moment still fires; pinned by the existing uninitialized-project CLI test |
| ConfigHooks overlay on `lint.ignore` (schema CLI) not applied to drift's declared view | Low | Pre-existing family trait — `codegraph()` reads raw config identically; drift stays symmetric with its code-derived view; out of scope, documented |
| Double config load per run | Negligible | One small YAML read; producers stay decoupled |

## Updated Files

- `goga/drift/drift.py`
- `goga/drift/CODEMANIFEST`
- `goga/drift/.usages/drift-usage.md`
- `tests/drift/conftest.py`
- `tests/drift/test_drift.py`
- `tests/commands/drift/test_drift.py`
