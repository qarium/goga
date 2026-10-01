# Change Execution Report — restore the ruff format gate

## Summary

`ruff format --check goga/ tests/` reported `54 files would be reformatted, 787 files already formatted`. Root-cause analysis showed ~30 commits (2026-09-21 → 2026-09-29) merged into `release/2.0.0` without running `ruff format`, while the only CI format gate (`.github/workflows/lint.yml`) triggers on `[0-9]+.[0-9]+.x` branch names only — the `release/*` line never passed it. ruff 0.16's new Markdown code-block formatting added the 5 `.usages/*.md` files to the gate. The fix reformatted exactly the 54 flagged files (whitespace-only), restoring the gate. The optional CI-trigger fix and ruff version pinning were proposed and declined by the user (core-only approval).

## Root Cause

1. **Direct cause** — ~30 commits merged into `release/2.0.0` without `ruff format` on touched files.
2. **Enabling cause** — `.github/workflows/lint.yml` (only ruff gate) triggers on push/PR to `[0-9]+.[0-9]+.x`; `release/2.0.0` does not match → 218 commits since 2026-09-15 never gated.
3. **Gate redefinition** — floating `ruff>=0.15.0`; ruff 0.16 added Markdown python-block formatting (ruff 0.15.0: 49 files/584 checked; 0.16.9: 54 files/787 checked).

Confidence: HIGH (reproduction, per-file commit attribution, workflow trigger analysis, version comparison).

## Modified Cells

| Cell | Files Modified |
|---|---|
| goga/commands | commands/topics/render.py |
| goga/build | review_config.py, hooks/events.py, .usages/build-usage.md |
| goga/config | project/loader.py, hooks/overlay.py, .usages/registering-hooks.md, hooks/.usages/checkpoints.md |
| goga/topics | updating.py, propagating.py, git/exchange.py, deletion.py, board.py |
| goga/schema | hooks/events.py, .usages/registering-hooks.md, hooks/.usages/checkpoints.md |
| tests/* | 38 test files |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| format | 49 python files | Line joins to the 120-column contract, call-argument re-wrapping; AST-identical to HEAD |
| format | 5 `.usages/*.md` | Trailing-comment alignment and re-wraps inside python example blocks; prose untouched |

Delivered as commit `8cd8d4e` (`style: restore the ruff format gate across goga/ and tests/`) on `release/2.0.0`.

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| — | — | No new tests: formatting-only change (AST-identical); the format gate itself is the regression guard |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| all | None | 5 `.usages/*.md` files: whitespace-only alignment of python example blocks (formatter output; examples still parse and remain semantically valid) |

## Validation Results

**VERIFIED.**
- `ruff format --check goga/ tests/` → `841 files already formatted`
- `ruff check goga/ tests/` → `All checks passed!`
- `goga lint` → `cells: 81 errors: 0`
- AST equality vs HEAD: 49/49 changed python files, 0 mismatches
- pytest full suite: no new failures vs pre-change baseline; the only persistent failure (`tests/agents/test_facade.py::test_facade_import_surface`) passes with `goga` installed in the verification venv (3 passed) — venv artifact; baseline's docker/onboarding/cli/network failures re-ran green in isolation (82 passed)

## Compatibility Status

**Compatible** — all compatibility-guard checklist items YES: same arguments → same behavior, output formats/paths/error strings unchanged, manifest guarantees preserved, usage recipes valid. No breaking change.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Drift recurs on next `release/*` merge (CI gate still blind) | High | Declined by user (option A); documented here for a future change to `lint.yml` triggers |
| Future ruff releases redefine the gate again (floating pin) | Medium | Declined by user; would be bounded by `ruff>=0.16.0,<0.17` in pyproject + CI |
| Merge conflicts with in-flight branches | Low | Whitespace-only diff; resolve by taking the formatted side and re-running `ruff format` |

## Updated Files

goga/build/.usages/build-usage.md
goga/build/hooks/events.py
goga/build/review_config.py
goga/commands/topics/render.py
goga/config/.usages/registering-hooks.md
goga/config/hooks/.usages/checkpoints.md
goga/config/hooks/overlay.py
goga/config/project/loader.py
goga/schema/.usages/registering-hooks.md
goga/schema/hooks/.usages/checkpoints.md
goga/schema/hooks/events.py
goga/topics/board.py
goga/topics/deletion.py
goga/topics/git/exchange.py
goga/topics/propagating.py
goga/topics/updating.py
tests/build/hooks/test_contexts.py
tests/build/hooks/test_events.py
tests/build/test_build.py
tests/build/test_build_pass.py
tests/build/test_ralphex_config.py
tests/build/test_review_config.py
tests/build/test_run_settings.py
tests/commands/conftest.py
tests/commands/pipeline/test_integration_launcher_tmpfile.py
tests/commands/pipeline/test_pipeline_config_checkpoint.py
tests/commands/pipeline/test_run_pipeline_container.py
tests/commands/pipeline/test_run_pipeline_container_workflow.py
tests/commands/pipeline/test_run_pipeline_info_container.py
tests/commands/test_build.py
tests/commands/test_config.py
tests/commands/test_integration_split.py
tests/commands/test_lint.py
tests/commands/test_schema.py
tests/commands/topics/test_render.py
tests/commands/topics/test_topics.py
tests/config/test_config.py
tests/config/test_loader.py
tests/config/test_project_cell_contract.py
tests/hooks/catalog/test_catalog.py
tests/integration/test_config_hooks_passthrough.py
tests/integration/test_pipeline_info_integration.py
tests/integration/test_runtime_isolation.py
tests/integration/test_topic_workflows.py
tests/pipeline/test_card_run_skip_equivalence.py
tests/pipeline/test_describe_pipeline.py
tests/pipeline/test_run_pipeline.py
tests/pipeline/test_run_pipeline_workflow.py
tests/topics/test_board.py
tests/topics/test_creation.py
tests/topics/test_deletion.py
tests/topics/test_exchange.py
tests/topics/test_propagating.py
tests/topics/test_updating.py

---

# Change Plan (approved — option A: core only)

## Task Classification

Type: bugfix (format-contract restoration; behavior-neutral by construction)

## Change Strategy

1. `ruff format goga/ tests/` with ruff 0.16.9 — exactly 54 files, 787 untouched.
2. Verify `ruff format --check` → 0; `ruff check` → clean; AST-only diff; pytest failure set equals baseline.
3. Single dedicated `style:` commit.

Declined options (not implemented): `release/**` triggers in `lint.yml`; bounding ruff to `>=0.16.0,<0.17`.

## Compatibility Verification

Backward compatible — see Compatibility Status above.
