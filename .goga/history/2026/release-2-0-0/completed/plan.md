# usages sync force filters — Change Plan + Execution Report

Task: make `goga usages sync --force` honor the `--group`/`--dep` filters — the destructive clean must remove only the specified group and/or dep subtree, then re-sync only the matching deps.
Executed: 2026-09-27, branch `release/2.0.0`.

---

# Change Plan

## Task Classification

Type: feature (behavioral amendment of an existing documented contract — user-approved breaking change)

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| `goga/usages/sync` | `goga/usages/sync/clean.py` | `clean_usages_dir` gains optional `group`/`dep` filter params; removal scoped to matching subtrees |
| `goga/usages/sync` | `goga/usages/sync/sync.py` | `_sync_work` passes filters to `clean_usages_dir`; docstrings updated |
| `goga/usages/sync` | `goga/usages/sync/CODEMANIFEST` | `sync` step 5 + `force` param + Requirements; `clean_usages_dir` contract rewritten |
| `goga/commands/usages` | `goga/commands/usages/usages.py` | `--force` help text reflects filter-scoped clean |
| `goga/commands/usages` | `goga/commands/usages/CODEMANIFEST` | `sync` method annotations (`force` / CLI option text) |
| practice | `goga/usages/.usages/sync-usages.md` | Modes + Filters sections |
| docs | `docs/features/usages/cli.md` | force paragraph, Modes table, `--force` option row, example |
| tests | `tests/usages/sync/test_clean.py`, `tests/usages/sync/test_sync.py`, `tests/usages/test_integration.py` | signature/behavior matrix; replace wipe-pinning test; add force+filter integration case |

## Root Cause Analysis

`_sync_work` (sync.py) called `clean_usages_dir(usages_root)` without the filters; `clean_usages_dir` had no filter parameters and removed every subdirectory of `.goga/usages/` except `cooks`. Manifest, practice, docs, and a pinning test codified the unscoped clean — the change amends the contract deliberately (user approval q2, 2026-09-27).

## Change Strategy

1. `clean.py` — `clean_usages_dir(usages_root, group=None, dep=None) -> int`: no filters → full clean (all subdirs except `cooks`, root files kept); `group` only → remove `usages_root/<group>`; `dep` only → remove `<g>/<dep>` for every group dir `<g>` except `cooks`; both → remove `usages_root/<group>/<dep>`. Idempotent; `cooks` never removed in any mode; directories only.
2. `sync.py` — thread filters into the clean call; update docstrings.
3. CLI `--force` help text update.
4. CODEMANIFEST ×2, practice, and end-user docs updated in lockstep.
5. Tests rewritten/extended; gates: `pytest tests/usages`, `ruff`, `goga lint`.

## Compatibility Verification

Breaking for `force` + filter calls only (same args → non-matching synced trees now preserved). Unfiltered `sync` / `sync --force` byte-identical. Signature source-compatible. User override recorded (q2: minimal variant — no subcommand-level options).

---

# Change Execution Report

## Summary

The `goga usages sync --force` destructive clean is now scoped by the `--group`/`--dep` filters: it removes only the specified group and/or dep subtree under `.goga/usages/` and then re-syncs only the matching declared deps. Previously the clean wiped every synced subtree regardless of filters, so a filtered force destroyed all other groups/deps. The change was executed as a specification-governed amendment: CODEMANIFEST contracts, the cell practice, end-user docs, and the pinning test were updated in lockstep with the code.

## Root Cause

`_sync_work` passed no filters to `clean_usages_dir`, whose contract was "remove every subdirectory except cooks" — the filters reached the re-sync loop and the hooks moments but not the destructive clean.

## Modified Cells

| Cell | Files Modified |
|---|---|
| `goga/usages/sync` | `clean.py`, `sync.py`, `CODEMANIFEST` |
| `goga/commands/usages` | `usages.py`, `CODEMANIFEST` |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| Filter-aware clean | `goga/usages/sync/clean.py` | `clean_usages_dir(usages_root, group=None, dep=None)`: full wipe without filters; group/dep/both scoped removal with a `cooks` guard in every branch; helpers `_clean_all`, `_clean_group_target`, `_clean_dep_everywhere`, `_remove_dir` |
| Filters threaded | `goga/usages/sync/sync.py` | `clean_usages_dir(usages_root, group=group, dep=dep)`; `sync`/`_sync_work` docstrings updated |
| Help text | `goga/commands/usages/usages.py` | `--force`: "Clean the --group/--dep targets (all of .goga/usages/ when unfiltered) then re-sync them." |

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| `TestCleanUsagesDirFiltered` (8 tests) | `tests/usages/sync/test_clean.py` | group-only / dep-only / both scoping, `cooks` guards (incl. explicit `group=cooks`, dep under cooks), no-op filters, root-file name collision, idempotence |
| `test_sync_force_with_filter_cleans_only_matching_and_keeps_others` | `tests/usages/sync/test_sync.py` | inverse-pinning: non-matching tree + cooks survive a filtered force (replaces the old wipe-pinning test) |
| `test_sync_force_dep_filter_keeps_other_deps_in_same_group` | `tests/usages/sync/test_sync.py` | dep-only force preserves sibling deps |
| `test_sync_force_passes_filters_to_clean` | `tests/usages/sync/test_sync.py` | filters are threaded into `clean_usages_dir` |
| `test_flow_b_force_with_group_filter_cleans_only_that_group` | `tests/usages/test_integration.py` | real-FS + real clean/deploy: matching group re-deployed fresh, non-matching group and cooks preserved |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| `goga/usages/sync` | `sync`: `force`/`group`/`dep` param semantics, Algorithm step 5 (scoped clean), new Requirement, Constraints; `clean_usages_dir`: new signature + filter-aware algorithm, requirements, constraints | — |
| `goga/commands/usages` | `usages.sync` method: `force` param + CLI option text | — |
| `goga/usages` | — | `sync-usages.md`: Modes/Filters rewritten (scoped force matrix, orphan guidance), Constraints updated |
| docs | — | `docs/features/usages/cli.md`: force paragraph, Modes table, `--force` row, filtered-force example |

## Validation Results

VERIFIED. `pytest tests/usages` — 180 passed. Full suite — 6167 passed, 9 failed (identical failure set to the pre-change baseline, verified via stash-diff; environment failures in docker/onboarding/agents/cli-version, all out of scope). `ruff check` + `format` — clean. `goga lint` — 81 cells, 0 errors. End-to-end CLI verification on real local git remotes: group+dep force refreshed the target and preserved the other group's local edit; group-only force re-deployed the whole group; dep-only force re-synced the dep across groups; unfiltered force full-wiped while preserving `cooks` and root files.

## Compatibility Status

Breaking change (user-approved): `force`+filter calls now preserve non-matching synced subtrees. API signatures source-compatible; unfiltered behavior unchanged; exit codes, moments, logs, rendering unchanged. Override recorded in q2 (2026-09-27): minimal variant, `--group/--dep` remain group-level options only.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Orphaned subtrees no longer removed by a filtered force | Low | Documented: run an unfiltered `sync --force` to wipe orphans/stale groups |
| `cooks` accidentally reachable by a filter | High if unguarded | Explicit guard in every filtered branch + two dedicated tests |
| Future regression to the full wipe | Medium | Inverse-pinning test + filters-threaded assertion + integration test |

## Updated Files

- goga/usages/sync/clean.py
- goga/usages/sync/sync.py
- goga/usages/sync/CODEMANIFEST
- goga/commands/usages/usages.py
- goga/commands/usages/CODEMANIFEST
- goga/usages/.usages/sync-usages.md
- docs/features/usages/cli.md
- tests/usages/sync/test_clean.py
- tests/usages/sync/test_sync.py
- tests/usages/test_integration.py
