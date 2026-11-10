# Change Plan — fix kw_only contract tests failing on Python 3.10/3.11

## Task Classification

Type: **bugfix** (test infrastructure — version-incompatible assertion)

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| goga/pipeline/compiler | `tests/pipeline/compiler/test_flow_repeat_contract.py` | Replace raw `__dataclass_params__.kw_only` assertion with the portable `is_kw_only_dataclass` helper; rename the test to `test_flow_repeat_is_kw_only_dataclass` |
| goga/pipeline/workflow | `tests/pipeline/workflow/test_workflow_repeat_contract.py` | Drop the raw `__dataclass_params__.kw_only` assertion (the portable helper check on the line above already pins the same fact) |

Source cells, CODEMANIFEST files, and `.usages` files are NOT modified.

## Root Cause Analysis

The two contract tests pinned the `kw_only=True` convention through a CPython
internal attribute:

```python
assert FlowRepeat.__dataclass_params__.kw_only is True      # compiler test, line 68
assert WorkflowRepeat.__dataclass_params__.kw_only is True  # workflow test, line 36
```

`_DataclassParams.kw_only` exists only from Python 3.12. On Python 3.10/3.11
the attribute is absent, so the access raises `AttributeError` — while the
declaration itself holds everywhere (`@dataclass(kw_only=True)` on both
classes; `field.kw_only` is `True` on every version since 3.10).

Evidence chain:

- CI (`.github/workflows/tests.yml` matrix 3.10–3.14): exactly these 2 tests fail on 3.10 and 3.11 with `AttributeError: '_DataclassParams' object has no attribute 'kw_only'`; all other 7890 tests pass
- Local reproduction on Python 3.11.2: `hasattr(D.__dataclass_params__, 'kw_only') == False` while `[f.kw_only for f in dataclasses.fields(D)] == [True]`
- `tests/conftest.py:70` already ships `is_kw_only_dataclass()` whose docstring documents this exact incompatibility ("`cls.__dataclass_params__.kw_only` is unusable on 3.10/3.11")
- Conventions (`.goga/usages/conventions.md`): "Test code must be compatible with Python 3.10 and above" and "All dataclass-based model classes MUST use `kw_only=True`"
- Both CODEMANIFESTs require `Use @dataclass(kw_only=True)`; both implementations satisfy it — the defect is in the tests, not the code
- Repo-wide grep: no other test reads `.kw_only` from `__dataclass_params__` (all other uses are `.frozen`, present on all versions); the helper is the established idiom across ~57 test files

## Trace Summary

test → facade import (`goga.pipeline.compiler` / `goga.pipeline.workflow`) →
class object → `__dataclass_params__` (decorator-set, shape is
version-dependent) → `AttributeError` on Python < 3.12. The portable
equivalent path (`dataclasses.fields()` → `field.kw_only`) is stable on
3.10+ and is what the shared helper uses.

## Change Strategy

1. Compiler test: import the shared helper `from tests.conftest import is_kw_only_dataclass`; replace the raw assertion; rename the test for accuracy (no external references to the old name — verified by grep)
2. Workflow test: remove the redundant raw assertion; the helper assertion stays
3. No runtime, manifest, or usage changes

## Specification Impact

None. CODEMANIFEST files unchanged; the manifests already declare the
`kw_only=True` requirement, and the implementation satisfies it.

## Usage Impact

None. No `.usages` file references the kw_only pin or the affected assertion
pattern; `compile-flow.md` describes the repeat compilation rule, which is
unchanged.

## Compatibility Verification

Fully backward compatible — test-only change; no runtime behavior, file
paths, output formats, return semantics, or manifest guarantees altered.
The same convention guarantee is verified through a version-portable
mechanism. Compatibility-guard checklist: all 12 items YES.

## Test Strategy

The modified assertions are themselves the regression tests for this defect:
each cell keeps a portable pin (`is_kw_only_dataclass`) plus a behavioral pin
(positional construction raises `TypeError`). Verified on Python 3.11.2 (the
failing CI class) and 3.12.16.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Test rename breaks external references | Low | Low | Repo-wide grep: none exist |
| Helper semantics differ from `kw_only=True` | Low | Low | Helper checks `all(field.kw_only)` — the observable contract; the positional-raises-TypeError test pins behavior separately |

---

# Change Execution Report

## Summary

Fixed two contract tests that failed on Python 3.10/3.11 in CI by pinning the
`kw_only=True` dataclass convention through `_DataclassParams.kw_only` — a
CPython internal attribute that exists only from Python 3.12. Both tests now
use the project's shared portable helper `is_kw_only_dataclass`
(`dataclasses.fields()`-based, stable on 3.10+), matching the idiom already
used by ~57 other test files. No production code, CODEMANIFEST, or usage
changes were needed — the implementation was already correct.

## Root Cause

See Root Cause Analysis above: version-incompatible assertion in tests,
violating the project convention "Test code must be compatible with Python
3.10 and above".

## Modified Cells

| Cell | Files Modified |
|---|---|
| goga/pipeline/compiler | `tests/pipeline/compiler/test_flow_repeat_contract.py` (test mirror) |
| goga/pipeline/workflow | `tests/pipeline/workflow/test_workflow_repeat_contract.py` (test mirror) |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| Portable kw_only pin | `tests/pipeline/compiler/test_flow_repeat_contract.py` | Import `is_kw_only_dataclass`; replace `assert FlowRepeat.__dataclass_params__.kw_only is True` with `assert is_kw_only_dataclass(FlowRepeat)`; rename test to `test_flow_repeat_is_kw_only_dataclass` |
| Drop raw assertion | `tests/pipeline/workflow/test_workflow_repeat_contract.py` | Remove `assert WorkflowRepeat.__dataclass_params__.kw_only is True` (the helper assertion above it pins the same fact) |

## Tests Added

No new test files. The two modified tests ARE the fix; each affected cell
retains both a portable pin and a behavioral pin (positional construction
raises `TypeError`).

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| goga/pipeline/compiler | none | none |
| goga/pipeline/workflow | none | none |

`goga lint`: 91 cells, 0 errors.

## Validation Results

**VERIFIED.**

- Both target test files: 16/16 passed on Python 3.11.2 (the failing CI class, reproduced before the fix) and on Python 3.12.16
- `tests/pipeline/` suite: 1713/1713 passed on both 3.11 and 3.12
- Full suite on 3.11 and 3.12: 7816 passed, 68 failed — all 68 are pre-existing sandbox-environment failures (container guards, in-container builds, workflow resolution), proven identical on the pristine tree via `git stash` baseline (68 failed on the unmodified tree for the same file subset); zero regressions from this change
- `ruff check` on both modified files: all checks passed
- `goga lint`: 0 errors
- Scope integrity: git diff contains exactly the 2 planned test files, nothing else

## Compatibility Status

COMPATIBLE — all 12 compatibility-guard checklist items YES; no breaking
change; triple consistency (CODEMANIFEST ↔ implementation ↔ .usages)
preserved for both cells; no specification drift on any axis.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| CI on Python 3.10 cannot be verified locally (3.10 interpreter unavailable in sandbox) | Low | Root cause is version-structural, reproduced and fixed on 3.11 (same `_DataclassParams` shape as 3.10); the helper's docstring and CI matrix confirm 3.10 behaves identically |
| Environment-dependent suite failures may mask regressions | Low | Pristine-baseline comparison isolates them: identical 68 failures with and without the change |

## Updated Files

- tests/pipeline/compiler/test_flow_repeat_contract.py
- tests/pipeline/workflow/test_workflow_repeat_contract.py
