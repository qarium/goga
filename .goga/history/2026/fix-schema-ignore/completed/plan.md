# Change Execution Report — fix-schema-ignore

## Summary

`goga schema` failed with `AST parsing failed with 160 error(s)` because the schema path built the project AST without the configured ignore list, so traversal descended into `.venv/` where the manually installed `swax` and `resq` pip packages ship their own CODEMANIFESTs; their contracts validated against the goga repo root produced 160 rule errors, tripping the routine's fail-fast contract. The fix delivers the `lint.ignore` list from `.goga/config.yml` to every AST consumer — `schema`, `contract`, and `tool` now reuse the delivery chain `lint` already had (`load_project_config` → `ConfigHooks.amend_config` → `AST(".", ignore)`) — without touching `AST` semantics (default `ignore=None` traversal unchanged, per the `goga/ast` CODEMANIFEST constraint). The plan was fully approved by the user, including the two flagged compatibility items (CLI behavior change — the fix itself — and the signature-pin test updates).

## Root Cause

`schema()` in `goga/schema/schema.py:185` constructed `AST(".")` with no ignore list; with `ignore=None`, `AST.load()` prunes nothing and `os.walk` enters `.venv/`, loading 22 foreign manifests. Rules resolve import/usage paths against the repo root (cwd), yielding 140 × `import_has_valid_from_path` + 13 × `usage_filepath_exists` + 7 × `embedded_type_has_low_level` = 160 errors; `schema()` raises `ValueError` per its manifest requirement. Verified live: unfiltered → 160 errors; filtered with the exact `lint.ignore` entries (`build/`, `.venv/`, `example/`) → 0 errors. Root cause class: AST consumers other than lint never delivered `lint.ignore` (`contract` loaded config but discarded it; `tool` loaded no project config).

## Modified Cells

| Cell | Files Modified |
|---|---|
| `goga/schema` | `goga/schema/schema.py`, `goga/schema/CODEMANIFEST` |
| `goga/commands/schema` | `goga/commands/schema/schema.py`, `goga/commands/schema/CODEMANIFEST` |
| `goga/commands/contract` | `goga/commands/contract/contract.py`, `goga/commands/contract/CODEMANIFEST` |
| `goga/commands/tool` | `goga/commands/tool/tool.py`, `goga/commands/tool/CODEMANIFEST` |
| `goga/config` | `goga/config/.usages/project-configuration.md` (usage file only) |
| `goga/commands/lint` | `goga/commands/lint/.usages/lint.md` (usage file only) |
| tests | `tests/schema/test_schema.py`, `tests/schema/test_contract.py`, `tests/commands/schema/test_schema.py`, `tests/commands/contract/test_contract.py`, `tests/commands/tool/test_tool.py`, `tests/integration/test_integration_split.py` |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| Optional ignore parameter | `goga/schema/schema.py` | `schema(cells, max_depth, depends_on, ignore: list[str] \| None = None)`; `ignore` flows verbatim to `AST(".", ignore=ignore)`; default `None` keeps traversal unfiltered |
| Config delivery in schema CLI | `goga/commands/schema/schema.py` | Lint-style: optional config load (loader exceptions swallowed → `ignore=None`), `ConfigHooks.amend_config` checkpoint on successful load (hard failure → clean `ClickException`), summary lines → stderr, `ignore` derived from `overlay.config.lint` and forwarded to `schema_logic` |
| Ignore delivery in contract | `goga/commands/contract/contract.py` | Derives `ignore` from the already-loaded overlay (`lint is None → None; else lint.ignore`) and builds `AST(".", ignore=ignore)` |
| Loader-only config in tool | `goga/commands/tool/tool.py` | `_build_ast()` reads config with swallow semantics (no checkpoint, no output — injection stays transparent) and passes `ignore` to `AST`; error pass-through contract preserved |

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| `test_ignore_excludes_directory_from_tree` (parametrized) | `tests/schema/test_schema.py` | `ignore` excludes the directory from the tree; trailing-separator form (`.venv/` style) matches |
| `test_ignore_none_keeps_unfiltered_traversal` | `tests/schema/test_schema.py` | Default `None` loads everything — the `goga/ast` contract default; broken manifests still raise |
| `test_schema_honors_lint_ignore_from_config` | `tests/commands/schema/test_schema.py` | CLI honors `lint.ignore`; generation succeeds; foreign cell absent; stdout data-clean |
| `test_schema_without_config_runs_unfiltered` | `tests/commands/schema/test_schema.py` | No config → unfiltered → exit 1 with error count (pre-fix behavior preserved) |
| `test_schema_config_without_lint_section_unfiltered` | `tests/commands/schema/test_schema.py` | Config without `lint` → `ignore=None` |
| `test_schema_invalid_config_is_swallowed_not_fatal` | `tests/commands/schema/test_schema.py` | Invalid YAML swallowed; unfiltered; no traceback |
| `test_contract_honors_lint_ignore_from_config` | `tests/commands/contract/test_contract.py` | Ignored cell misses the document lookup; requested cell unaffected |
| `TestBuildAstIgnore` (3 tests) | `tests/commands/tool/test_tool.py` | `_build_ast` honors / no config / invalid config |
| `test_schema_ignore_param_type` | `tests/schema/test_contract.py` | `ignore: list[str] \| None` type pin |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| `goga/schema` | Signature +`ignore`; `documents` practice states the optional verbatim delivery; Requirements: verbatim flow, no normalization/glob, ignored dirs contribute no cells/errors | — |
| `goga/commands/schema` | +Imports (`load_project_config`, `ProjectConfig`, `project-configuration`; `ConfigHooks`, `ConfigOverlay`); Annotations; 5-step Algorithm (ignore derivation first); Requirements (verbatim, config-less unchanged) | — |
| `goga/commands/contract` | Algorithm: derive ignore (step 2), pass to `AST` (step 3); Requirements: verbatim, no documents from ignored dirs | — |
| `goga/commands/tool` | `build_injections` ast bullet: loader-only read, swallow semantics, silent; Requirements: never fails on invalid config | — |
| `goga/config` | — | `project-configuration.md`: `lint.ignore` honored by the four AST-consuming commands; traversal-root wording |
| `goga/commands/lint` | — | `lint.md`: one bullet naming the sibling consumers |

## Validation Results

**VERIFIED** (see `completed/reports/validation_report.md`). Live gates: `goga schema` exit 0, 91 cells, clean stderr, `.venv` absent from output (was: exit 1, 160 errors); `goga lint` cells 91 / errors 0 (unchanged); `goga contract goga/schema` exit 0. Affected suites 321/321 passed; `ruff check goga/ tests/` clean; `goga lint` on manifests 0 errors. Full suite: 7522 passed, 68 failed — byte-identical to the pre-change baseline (build/pipeline/docker integration tests outside this scope, verified via `git stash` A/B).

## Compatibility Status

Python-level backward compatible (optional parameter, default `None`; return type and defaults preserved; config-less projects byte-identical). Two user-approved deviations: (1) CLI `goga schema` behavior change — the same invocation now honors `lint.ignore` (success + exclusion instead of the crash) — the core purpose of the fix; (2) signature/delegation pin tests updated (`tests/schema/test_schema.py`, `tests/schema/test_contract.py`, `tests/integration/test_integration_split.py`). The `goga/ast` CODEMANIFEST constraint ("Do NOT change traversal for consumers that pass ignore=None") is preserved by design.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Users relying on unfiltered schema output see the cell set shrink by ignored dirs | Low | This is the fix's purpose; `ignore=None` API default preserved; behavior documented in manifests/usages |
| Config checkpoint now runs on the schema path (first time) | Low | Same surface lint/contract already deliver; hard failure = clean ClickException; schema tests pin the package environment |
| Duplicated ~15-line ignore-derivation block (lint ↔ schema) | Low | Follows the project's per-command delivery idiom; a shared helper is a deliberate out-of-scope refactor |
| Deployed `goga` CLI (`/opt/goga`) runs an older installed snapshot | Medium (deployment, not code) | Fix is in the repo; the CLI picks it up after reinstall/rebuild via the project's release process |

## Updated Files

- `goga/schema/schema.py`
- `goga/schema/CODEMANIFEST`
- `goga/commands/schema/schema.py`
- `goga/commands/schema/CODEMANIFEST`
- `goga/commands/contract/contract.py`
- `goga/commands/contract/CODEMANIFEST`
- `goga/commands/tool/tool.py`
- `goga/commands/tool/CODEMANIFEST`
- `goga/config/.usages/project-configuration.md`
- `goga/commands/lint/.usages/lint.md`
- `tests/schema/test_schema.py`
- `tests/schema/test_contract.py`
- `tests/commands/schema/test_schema.py`
- `tests/commands/contract/test_contract.py`
- `tests/commands/tool/test_tool.py`
- `tests/integration/test_integration_split.py`
- `.goga/history/2026/fix-schema-ignore/completed/plan.md` (this document)
- `.goga/history/2026/fix-schema-ignore/completed/reports/*.md` (stage artifacts)

---

# Change Plan (approved)

## Task Classification

**Type: bugfix** (defect: AST consumers other than lint never deliver the configured `lint.ignore` list to `AST`, making `goga schema` fail outright on this repo).

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| `goga/schema` | `goga/schema/schema.py`, `goga/schema/CODEMANIFEST` | `schema()` gains optional `ignore: list[str] \| None = None` param, passed to `AST(".", ignore=ignore)`; manifest signature/annotations/`documents` practice updated |
| `goga/commands/schema` | `goga/commands/schema/schema.py`, `goga/commands/schema/CODEMANIFEST` | Command loads config lint-style (optional, swallow loader errors; `ConfigHooks` checkpoint on successful load; summary lines → stderr), derives `ignore`, forwards it to `schema_logic`; manifest gains Imports and the algorithm step |
| `goga/commands/contract` | `goga/commands/contract/contract.py`, `goga/commands/contract/CODEMANIFEST` | Derive `ignore` from the already-loaded `overlay.config.lint` and pass to `AST(".", ignore=ignore)`; manifest algorithm step 3 updated |
| `goga/commands/tool` | `goga/commands/tool/tool.py`, `goga/commands/tool/CODEMANIFEST` | `_build_ast()` loads config loader-only (swallow semantics, **no** checkpoint — injection stays transparent), derives `ignore`, passes to `AST`; manifest `build_injections` annotations updated |
| `goga/ast` | — | **No change** — constraint "Do NOT change traversal for consumers that pass ignore=None" preserved; `AST` already implements ignore correctly |
| `goga/config` | `goga/config/.usages/project-configuration.md` | Wording only: `lint.ignore` described as honored by all AST-consuming commands (lint, schema, contract, tool), not only `goga lint` |

## Root Cause Analysis

From Investigation Report (confidence HIGH): `schema()` constructs `AST(".")` without an ignore list (`goga/schema/schema.py:185`). With `ignore=None`, `AST.load()` prunes nothing and `os.walk` descends into `.venv/`, where the manually installed `swax`/`resq` packages ship 22 CODEMANIFESTs. Their contracts are validated against the goga repo root (rules resolve paths from cwd), yielding 140 `import_has_valid_from_path` + 13 `usage_filepath_exists` + 7 `embedded_type_has_low_level` = 160 errors; `schema()` then raises `ValueError` per its fail-fast contract. Verified live: unfiltered → 160 errors; filtered with the exact `lint.ignore` entries → 0 errors. `goga lint` works because it alone delivers `lint.ignore` (`goga/commands/lint/lint.py:30-51`); `goga contract` loads config but discards `lint.ignore`; `goga tool` loads no project config.

## Change Strategy

1. **`goga/schema/schema.py`** — add `ignore: list[str] | None = None` as the 4th parameter of `schema()`; construct `AST(".", ignore=ignore)`; document the parameter in the docstring (passed verbatim; `AST` owns matching semantics).
2. **`goga/commands/schema/schema.py`** — replicate lint's delivery block before the `schema_logic` call: optional config load (any loader exception swallowed → `ignore=None`); on successful load deliver `ConfigHooks().amend_config(config=cfg)` (hard failure → clean `click.ClickException`); print `overlay.summary_lines` to stderr; derive `ignore = None if overlay.config.lint is None else overlay.config.lint.ignore`; forward to `schema_logic`.
3. **`goga/commands/contract/contract.py`** — after the existing config delivery, derive `ignore` the same way and construct `AST(".", ignore=ignore)`.
4. **`goga/commands/tool/tool.py`** — `_build_ast()` gains a loader-only config read with swallow semantics; derive `ignore` from `cfg.lint`; construct `AST(".", ignore=ignore)`. No checkpoint, no output.
5. **Manifest reconciliation** — per cell above (see Specification Updates in the report).
6. **Usage reconciliation** — `project-configuration.md` wording; `goga/ast/.usages/loading.md` needs no change.

## Test Strategy

Add: logic tests (exclude/default), CLI schema tests (honors config, absent config, absent lint section, invalid config), contract test (ignored cell misses lookup), tool tests (`_build_ast` honored/unfiltered/invalid). Update signature pins. Validation: affected suites, full suite, ruff, live gates (`goga schema` exit 0/91 cells; `goga lint` 91/0).

## Compatibility Verification

Python-level backward compatible (`ignore` defaults to `None` → unfiltered, per the `goga/ast` constraint). Two flagged, user-approved points: CLI behavior change (the intended fix) and signature-pin test updates. Config key `lint.ignore` reused as-is — no config schema change, no user migration.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Behavior change at CLI level surprises users | Low | Medium | This is the fix's purpose; documented; `ignore=None` default preserved at API level |
| Config checkpoint first run on the schema path | Low | Medium | Same surface lint/contract already run; clean failure mode |
| Duplication of the ignore-derivation block | Certain | Low | Follows the per-command delivery idiom; shared helper out of hotfix scope |
| Tool injection gains a config read | Low | Low | Loader-only, swallow-all; worst case = today's behavior |
| Scope creep (config-key rename, rule redesign) | Ruled out | — | Rejected in Investigation Report; `lint.ignore` reused verbatim |
