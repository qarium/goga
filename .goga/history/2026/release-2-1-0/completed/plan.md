# Change Plan + Execution Report — fix 19 CI integration-test failures (PermissionError /home/goga)

## Task Classification

Type: bugfix (test infrastructure; no production code change).

## Task Summary

The CI run of `release/2.1.0` failed 19 integration tests (8254 passed) with
`PermissionError: [Errno 13] Permission denied: '/home/goga'`. Direct
`run_pipeline` calls raised out of `materialize_afm_skin`
(`goga/pipeline/run_pipeline.py:507` → `goga/pipeline/afm_skin.py:74`); CLI-path
tests surfaced the same `OSError` as `Error: pipeline 'deploy' could not be read
or written` (`goga/pipeline/cli.py:243` → exit 1 instead of the expected code).
The same tests pass on a developer machine whose user home is `/home/goga`.

## Root Cause

`tests/integration/conftest.py::in_container_pipeline_run_context` — the fixture
all 19 failing suites opt into — relocated only the `_AFM_CONFIG_PATH` fixed
constant into the tmp tree. The `_SKINS_TARGET_BASE` constant (the documented
test seam of `materialize_afm_skin`, fixed at `/home/goga/.afm/skins`) was never
relocated when the skin feature landed (commit 51376ae). Consequences:

- On CI (user `runner`, home `/home/runner`) the skins-base `mkdir` fails with
  `PermissionError` → 19 failures.
- On a developer machine (user `goga`) the tests pass by accident while silently
  materializing the skin into the real home — violating the fixture's own
  documented intent ("no test writes the real home"). The leak
  (`/home/goga/.afm/skins/goga`) was observed and removed.

The unit zone pins the constant correctly (`tests/pipeline/conftest.py:99`);
the integration zone was missed. The production contract is unaffected: the
CODEMANIFEST of `goga/pipeline` fixes the skin path on purpose ("Do not derive
the skin directory value … it is fixed"), so the fix belongs in the test seam.

## Affected Cells

| Cell | Files to Modify | What Changes |
|------|-----------------|--------------|
| — (test infrastructure, outside cells) | `tests/integration/conftest.py` | Relocate `_SKINS_TARGET_BASE` in the shared run-context fixture |
| — (test infrastructure, outside cells) | `tests/integration/test_run_context_isolation.py` | New guard test for the isolation property |

Production cells (`goga/pipeline` included): untouched.

## Change Strategy

1. In `in_container_pipeline_run_context`, resolve `goga.pipeline.afm_skin` via
   `sys.modules` (same pattern as the adjacent `afm_config` resolution) and
   `monkeypatch.setattr` its `_SKINS_TARGET_BASE` to
   `tmp_path / ".afm-home" / "skins"` — mirroring the unit-zone pin.
2. Align the fixture docstring with the actual relocations.
3. Add a guard test pinning the isolation property so a dropped relocation
   fails on ANY host, not only on CI.

## Implemented Changes

| Change | File | Description |
|--------|------|-------------|
| Skins-base relocation | `tests/integration/conftest.py` | Fixture pins `_SKINS_TARGET_BASE` into the tmp tree; docstring updated |
| Isolation guard test | `tests/integration/test_run_context_isolation.py` | New test `test_skin_materialization_stays_in_tmp_tree` (class `TestInContainerPipelineRunContext`) |

## Tests Added

| Test | File | What It Validates |
|------|------|-------------------|
| `test_skin_materialization_stays_in_tmp_tree` | `tests/integration/test_run_context_isolation.py` | The fixture relocates the skins base into the tmp tree and `materialize_afm_skin` writes there (base equality, materialized dir, `index.css` present). Verified to FAIL without the conftest fix and PASS with it. |

## Test Results

| Run | Result |
|-----|--------|
| The 9 previously failing files (50 tests) | 50 passed |
| Full `tests/integration/` zone | 330 passed, 8 skipped |
| `tests/pipeline/` unit zone | 1976 passed |
| Full suite `pytest tests/` | 8266 passed, 8 skipped (fresh venv, Python 3.12) |
| Isolation leak check | `/home/goga/.afm/skins` NOT recreated after the full run |
| `ruff check` / `ruff format --check` (changed files + integration zone) | clean |
| `goga lint` | 92 cells, 0 errors |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|------|----------------------|---------------|
| goga/pipeline | none — contract unchanged and preserved | none — `run-pipeline.md` skin section verified accurate |

## Compatibility Status

COMPATIBLE (all checklist items YES). No production signature, behavior, path,
output, or error semantics changed; the test-time relocation is the documented
purpose of the `_SKINS_TARGET_BASE` module constant ("A module constant so the
tests (and only they) can relocate it"). Breaking change: none.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| A test depends on writing the real home | low | grep clean; full-suite run green |
| Other CI-only latent dependencies | low | full integration zone green; fixed-constant seams now pinned in both zones |

## Out of Scope (observation)

The integration fixture also leaves `_CLOSURE_BASE` (`/tmp/goga-assistant-env`)
and `_GATE_WRAPPER_BASE` (`/tmp/goga-gate-env`) unrelocated (real `/tmp`
writes). Writable everywhere, unrelated to the failure — candidate for a
separate housekeeping task.

## Updated Files

- tests/integration/conftest.py
- tests/integration/test_run_context_isolation.py
