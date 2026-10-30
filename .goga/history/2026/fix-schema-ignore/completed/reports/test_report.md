# Test Report

## Changes Requiring Coverage

| Change | Type |
|---|---|
| `schema()` passes `ignore` to `AST`; default `None` keeps unfiltered traversal | behavior + regression (default) |
| CLI `goga schema` derives ignore from optional config (`lint.ignore`), swallows loader failures, checkpoints on successful load | behavior + edge |
| CLI `goga schema` without config / without lint section → unfiltered (old behavior) | regression |
| `goga contract` delivers already-loaded ignore to `AST`; ignored cell not a document | behavior |
| `tool._build_ast` loader-only config read; absent/invalid config unfiltered; no failure on invalid config | behavior + edge |
| Delegation pins: CLI forwards `ignore` to `schema_logic` | manifest |

## Tests Added

| Test Name | File | What It Validates |
|---|---|---|
| `TestSchemaFunction::test_ignore_excludes_directory_from_tree` (parametrized: `foreign`, `foreign/`) | `tests/schema/test_schema.py` | `schema(..., ignore=...)` excludes the directory from the output tree; trailing-separator entries (the `.venv/` config form) match |
| `TestSchemaFunction::test_ignore_none_keeps_unfiltered_traversal` | `tests/schema/test_schema.py` | Default `ignore=None` loads everything — the `goga/ast` contract default; the broken foreign manifest still raises the contract ValueError |
| `test_schema_honors_lint_ignore_from_config` | `tests/commands/schema/test_schema.py` | CLI reads `lint.ignore` from `.goga/config.yml`, generation succeeds, foreign cell absent, stdout data-clean |
| `test_schema_without_config_runs_unfiltered` | `tests/commands/schema/test_schema.py` | No config → nothing loaded → unfiltered → exit 1 with error count, stdout empty (pre-fix behavior preserved) |
| `test_schema_config_without_lint_section_unfiltered` | `tests/commands/schema/test_schema.py` | Config without `lint` section → `ignore=None` → unfiltered |
| `test_schema_invalid_config_is_swallowed_not_fatal` | `tests/commands/schema/test_schema.py` | Invalid YAML → swallowed → unfiltered, exit 1, no traceback |
| `test_contract_honors_lint_ignore_from_config` | `tests/commands/contract/test_contract.py` | Requested cell compares fine; the ignored cell is not a document (`document not found`, exit 1) |
| `TestBuildAstIgnore::test_build_ast_honors_lint_ignore` | `tests/commands/tool/test_tool.py` | `_build_ast` honors `lint.ignore` — root present, foreign lookup raises `DocumentNotFoundError` |
| `TestBuildAstIgnore::test_build_ast_without_config_unfiltered` | `tests/commands/tool/test_tool.py` | No config → foreign document present (pre-fix behavior) |
| `TestBuildAstIgnore::test_build_ast_invalid_config_unfiltered` | `tests/commands/tool/test_tool.py` | Invalid config → swallowed → unfiltered |
| `TestSchemaContract::test_schema_ignore_param_type` | `tests/schema/test_contract.py` | `ignore: list[str] | None` type hint pin |

## Tests Modified

| Test Name | File | Change |
|---|---|---|
| `TestSchemaContract::test_schema_has_correct_signature` | `tests/schema/test_contract.py` | Param list pin → `["cells", "max_depth", "depends_on", "ignore"]` (user-approved) |
| `TestGateWiringContract::test_schema_keeps_the_declared_signature` | `tests/schema/test_schema.py` | Same pin update (user-approved) |
| `TestSchemaDelegation::test_schema_delegates_to_schema_logic` | `tests/integration/test_integration_split.py` | Delegation pin → `assert_called_once_with([], None, [], ignore=None)` |
| `TestSchemaDelegation::test_schema_delegates_with_cells_and_options` | `tests/integration/test_integration_split.py` | → `(["pkg_a"], 2, ["lib"], ignore=None)` |
| `TestAllCommandsDelegationViaApp::test_schema_via_app_delegates` | `tests/integration/test_integration_split.py` | → `([], None, [], ignore=None)` |

Note: the plan predicted one signature-pin update; delegation pins in `tests/integration/test_integration_split.py` (3 more) surfaced only in the full-suite run — they pin the same approved contract (CLI forwards `ignore`), same category, no scope change.

## Test Results

| Run | Status | Details |
|---|---|---|
| Affected suites (`tests/schema`, `tests/commands/{schema,contract,tool}`, `tests/integration/test_integration_split.py`) | 321 passed | including 11 new + 5 updated tests |
| Full suite (`pytest tests/`) | 7522 passed, 68 failed, 8 skipped | the 68 failures are byte-identical to the pre-change baseline (verified via `git stash` A/B: 68 without the change, same test IDs) — all in `tests/build` / `tests/integration` / `tests/commands/{build,pipeline}`, infrastructure-dependent (docker/build orchestration), unrelated to this change |
| `ruff check goga/ tests/` | All checks passed | |
| `ruff format --check` (changed files) | clean | |
| Live gate: `/tmp/goga-test-venv/bin/goga schema` | exit 0, 91 cells, stderr clean | was: exit 1, 160 errors; `.venv` cells absent from output |
| Live gate: `goga lint` (test venv) | cells: 91, errors: 0, exit 0 | unchanged |
| Live gate: `goga contract goga/schema` (test venv) | exit 0 | unchanged, now with ignore delivered |

Interpreter note: the repo `.venv` is a broken macOS symlink venv (kept untouched — it holds the swax/resq packages that reproduce the bug); tests ran in a fresh `/tmp/goga-test-venv` (editable install of `/workspace` + `.[test]` extras). The system `goga` CLI (`/opt/goga/bin/goga`) still runs the previously installed package snapshot, not `/workspace` — picking up the fix there requires a reinstall/rebuild (user's release process).

## Coverage Gaps

| Changed Behavior | Covered? | Notes |
|---|---|---|
| `schema()` ignore pass-through | Yes | exclude + default + trailing separator forms |
| CLI schema config delivery (load/checkpoint/derive) | Yes | happy path, absent config, absent lint section, invalid config; checkpoint hard-failure path NOT directly tested (mirrors lint's implementation; lint owns its own checkpoint failure tests) |
| contract ignore delivery | Yes | ignored cell not a document; requested cell unaffected |
| tool `_build_ast` ignore | Yes | honored / no config / invalid config |
| ConfigHooks checkpoint failure → ClickException in schema CLI | Indirect | Same wrapper as lint (`ValueError`/`ImportError` → `ClickException`); lint's suite covers the shared `ConfigHooks` failure semantics; a schema-specific broken-tool-package test exists already for the schema walk (`_install_broken_package`), not for the config checkpoint |

## Missing Coverage Analysis

The only untested-new branch is the schema CLI's config-checkpoint hard-failure conversion. It is a verbatim copy of lint's proven wrapper (same exception tuple, same ClickException), and the underlying `ConfigHooks.amend_config` failure semantics are covered by `tests/config`. Direct coverage would require installing a misbehaving tool package pinned to the config checkpoint — meaningful, but marginal for a hotfix; flagged for the follow-up backlog rather than expanding scope now.
