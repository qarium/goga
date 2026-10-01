# Change Plan & Execution Report — CI test portability on Python 3.10/3.11

## Summary

CI failed on the Python-version matrix: 37 tests on python3.10 (36 in
`tests/build/test_build.py` with `AttributeError: <function build …> does not
have the attribute 'run_build_pass'` and 1 in `tests/config/test_loader.py`
with `AttributeError: '_DataclassParams' object has no attribute 'kw_only'`)
plus the same loader test on python3.11. Both failures were reproduced locally
on the exact CI interpreter (3.10.21) and root-caused to two non-portable
test-harness mechanisms — not to production code. The fix converts the
non-portable test mechanics to the project's established portable conventions;
production code, CODEMANIFEST files, and `.usages` files are untouched.

## Root Cause

- **A (36 tests, py3.10 only).** The tests patched
  `mock.patch("goga.build.build.run_build_pass", …)` by string target. Python
  3.10 `unittest.mock` resolves dotted targets by walking `getattr` from the
  root package; `goga/build/__init__.py` re-exports `from .build import build`,
  so the package attribute `goga.build.build` is the *function*, not the
  submodule → `AttributeError` at patch setup, before any production code runs.
  Python 3.11+ `mock` uses `pkgutil.resolve_name` (sys.modules-based), so the
  same tests pass on 3.11–3.14. Evidence: minimal shadowing repro; real suite
  36 failed / 26 passed on 3.10.21 vs 62 passed on 3.11.2 and 3.12.14; the
  identical failure class was already fixed for `goga.pipeline.run_pipeline`
  (see `tests/pipeline/test_run_pipeline*.py`, convention
  `[[feedback_mock_patch_module_shadowing]]`), and those tests pass on 3.10 in
  the same failing CI run.
- **B (1 test, py3.10 + py3.11).** `assert model.__dataclass_params__.kw_only`
  — the stdlib `_DataclassParams` object gains the `kw_only` attribute only in
  Python 3.12 (verified absent on 3.10.21/3.11.2, present on 3.12.14). The
  models themselves are kw_only on every version (`Field.kw_only == True`).
  The portable helper `is_kw_only_dataclass` (all fields kw_only via
  `dataclasses.fields`) already exists in `tests/conftest.py` and was already
  used for the same models in `tests/config/test_project_cell_contract.py`.

## Modified Cells

| Cell | Files Modified |
|---|---|
| `goga/build` (test suite only) | `tests/build/test_build.py` |
| `goga/config/project` (test suite only) | `tests/config/test_loader.py` |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| Portable patch targets | `tests/build/test_build.py` | 33 string patches `mock.patch("goga.build.build.run_build_pass", …)` → `mock.patch.object(build_module, "run_build_pass", …)` (`build_module = sys.modules["goga.build.build"]` already existed at the file top and is the established seam) |
| Convention comment | `tests/build/test_build.py` | Added the `[[feedback_mock_patch_module_shadowing]]` comment above the `build_module` binding, matching the `tests/pipeline/test_run_pipeline*.py` precedent |
| Portable kw_only assertion | `tests/config/test_loader.py` | `assert model.__dataclass_params__.kw_only, model` → `assert is_kw_only_dataclass(model), model`; added `from tests.conftest import is_kw_only_dataclass` |

## Tests Added

None — per the approved plan: the failing tests *are* the manifest-behavior
tests; the fix restores their executability on Python 3.10/3.11 without
altering any assertion. No production behavior changed, so there is no new
behavior to cover.

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| `goga/build` | none | none |
| `goga/config/project` | none | none |

`goga lint`: 81 cells, 0 errors.

## Validation Results

**VERIFIED.**

- python3.10.21: `tests/build/test_build.py` 62/62 passed (was 36 failed);
  the loader topics test passed (was failed). Combined selection 63/63.
- python3.11.2: combined selection 63/63 (loader test was the CI 3.11 failure).
- python3.12.14: both full files 447/447 passed — no regression.
- Full suite on python3.10.21: 6420 passed, 8 skipped, 9 failed — all 9
  reproduced identically on the pre-fix code (git-stash baseline) →
  pre-existing, environment-specific (no docker binary in the validation
  container; agents/docker/integration/onboarding/test_cli tests), none in the
  CI failure list.
- `ruff check goga/ tests/` — all checks passed; `ruff format --check goga/
  tests/` — 841 files already formatted.
- Scope integrity: working tree contains exactly the two approved test files.

## Compatibility Status

**Compatible** (all compatibility-guard checkboxes YES): test-only change;
same arguments produce the same production behavior; no file paths, output
formats, return semantics, or manifest guarantees altered; the 26 build tests
green on 3.10 pre-fix remain green post-fix.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Reintroduction of string patches through shadowed facades | low | Convention comment at the seam; convention `[[feedback_mock_patch_module_shadowing]]` |
| Matrix legs 3.13/3.14 not runnable locally | low | Both mechanisms used are stable there (`mock.patch.object` needs no target resolution; `Field.kw_only` exists since 3.10); CI matrix confirms |
| Local env lacks docker (9 pre-existing failures) | none for this change | Documented; proven pre-existing via differential baseline |

## Updated Files

- tests/build/test_build.py
- tests/config/test_loader.py

---

# Change Plan (as approved)

## Task Classification
Type: bugfix — fix CI test failures caused by two non-portable test-harness
mechanisms (no production behavior change).

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| `goga/build` (test suite only) | `tests/build/test_build.py` | Convert 33 string-target patches to object-target; add the convention comment at the `build_module` binding |
| `goga/config/project` (test suite only) | `tests/config/test_loader.py` | Replace the `__dataclass_params__.kw_only` assertion with `is_kw_only_dataclass(model)`; add the helper import |

## Root Cause Analysis
See Root Cause above (investigation confidence HIGH; differential reproduction
on 3.10.21 / 3.11.2 / 3.12.14).

## Trace Summary
Failure A dies in `mock.patch.__enter__ → get_original` before any production
code; the intended seam (`goga/build/build.py:10` import of `run_build_pass`,
called at `build.py:236`) is manifest-conformant and unchanged. Failure B dies
on stdlib introspection of models that are correctly kw_only on every version.

## Change Strategy
1. `tests/build/test_build.py`: convention comment + mechanical replacement of
   the 33 `run_build_pass` patch sites (arguments unchanged).
2. `tests/config/test_loader.py`: helper import + portable assertion (the
   adjacent `frozen` assertion is portable and stays).
3. Verification on 3.10.21 / 3.11.2 / 3.12.14 + ruff gates.

## Specification Impact
None — no manifest governs test patch mechanics; both manifests' contracts
keep being verified by the same tests through the same seams.

## Usage Impact
None — `.usages` files describe production behavior, which is untouched.

## Compatibility Verification
Backward compatible (test-only; see Compatibility Status).

## Test Strategy
Reproduce → fix → green on the exact failing selections per version; full
3.10 suite differential run; ruff check + format gates. No new tests needed.

## Risk Assessment
As in the Risks table above.
