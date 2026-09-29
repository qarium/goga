# Fix Non-Hermetic Build Tests (CI failures)

Author: Goga
CreatedAt: 29/09/26
Type: bugfix (test-surface defect)

## Summary

The CI run (Python 3.13 job) reported 10 failing tests: 9 with
`ERROR goga.build.build:build.py:89 invalid review configuration` and 1 with
`SystemExit: 1` from `ensure_in_docker()`. Investigation proved the failures are
environmental, not version-specific: the 10 tests implicitly depend on the goga
Docker image environment. The fix pins the two external in-container boundaries
in the tests, using the project's already-established pattern. No production
code, CODEMANIFEST, or usage file changed.

## Root Cause

- 9 tests invoke `build()` without pinning
  `goga.build.review_config.resolve_wrapper_path`. The review-config validation
  requires `Path(resolve_wrapper_path(agent)).is_file()` where the resolver is
  contractually a pure builder of the in-container path
  `/home/goga/bin/<agent>-as-claude.sh`. Inside the goga Docker image the file
  exists; on a bare CI runner it does not → `ValueError` → exit 1.
- `test_main_argparse_surface_matches_contract` runs a second `main()`
  invocation whose `with` block mocks only `build` / `load_project_config`,
  not `ensure_in_docker` — the real guard reads `GOGA_DOCKER` (unset on a bare
  runner) and exits 1.

Evidence: the same 10 tests pass on Python 3.12/3.13/3.14 inside the container;
a simulated bare runner (tmpfs over `/home/goga/bin`, `GOGA_DOCKER` unset)
reproduced exactly the CI's 10 failures before the fix and passes after it.

## Change Plan (as executed)

Apply the canonical boundary-pinning pattern
(`monkeypatch.setattr("goga.build.review_config.resolve_wrapper_path", ...)`,
already used by 20+ passing tests):

1. `tests/build/test_build.py::test_build_statuses_absent_topic_record_yields_empty`
   — add the missing `monkeypatch.setattr` line (the tmp wrapper file was
   already created; the sibling test had the line, this one lost it).
2. `tests/build/test_build.py::test_build_reuses_existing_ralphex_dir` — create
   the tmp wrapper + add the patch.
3. `tests/build/test_build.py::test_build_writes_ralphex_config_when_dir_exists`
   — same as (2).
4. `tests/integration/test_resolved_wrapper_flow.py::TestBuildResolvedPathFlow`
   — tmp wrapper + patch inside the `with` block; the
   `claude_command == resolve_wrapper_path(agent)` comparison keeps using the
   real pure resolver.
5. `tests/integration/test_resolved_wrapper_flow.py::TestResolvedPathConsistency`
   — same as (4), build side only.
6. `tests/build/test_main.py::test_main_argparse_surface_matches_contract` —
   mock `ensure_in_docker` in the second `with` block; `call_order` assertion
   becomes `["ensure_in_docker", "build", "ensure_in_docker", "build"]` so the
   guard-first property is proven for both invocations.

## Implemented Changes

| Change | File | Description |
|---|---|---|
| 1 | tests/build/test_build.py | Missing wrapper-boundary `monkeypatch.setattr` added |
| 2 | tests/build/test_build.py | tmp wrapper + boundary patch in `test_build_reuses_existing_ralphex_dir` |
| 3 | tests/build/test_build.py | tmp wrapper + boundary patch in `test_build_writes_ralphex_config_when_dir_exists` |
| 4 | tests/integration/test_resolved_wrapper_flow.py | tmp wrapper + boundary patch in `TestBuildResolvedPathFlow` (3 params) |
| 5 | tests/integration/test_resolved_wrapper_flow.py | tmp wrapper + boundary patch in `TestResolvedPathConsistency` (3 params) |
| 6 | tests/build/test_main.py | `ensure_in_docker` mocked in second `main()` block; `call_order` strengthened |

## Tests Added

None — the change repairs existing tests; no production behavior changed.

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| goga/build | none | none |
| goga/agents (+ wrapper) | none | none |
| goga/docker | none | none |

## Validation Results

- Full suite, in-container Python 3.12: 6429 passed, 8 skipped (baseline kept).
- Full suite, in-container Python 3.13: 6429 passed, 8 skipped.
- Full suite, simulated bare CI runner (Python 3.13, no `GOGA_DOCKER`, empty
  `/home/goga/bin`): 6427 passed, 10 skipped — the 10 previously failing tests
  pass; 2 extra skips are root-user artifacts of the simulation namespace.
- `ruff check goga/ tests/`: all checks passed.
- `ruff format --check`: edited files conform (one pre-existing complaint in
  `test_build.py:561` exists at HEAD — repo-wide drift with ruff 0.16.9, not
  affected by this change).
- `goga lint`: 81 cells, 0 errors.

## Compatibility Status

Fully backward compatible — test-only diff (+18/−1); no production signature,
path, output, or manifest guarantee changed; all 6419 other tests unmodified.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Other tests share the hidden env-dependence | low | full-suite run on the simulated bare runner is green |
| `call_order` assertion change alters test meaning | low | new assertion is strictly stronger (guard-first for both calls) |

## Updated Files

- tests/build/test_build.py
- tests/build/test_main.py
- tests/integration/test_resolved_wrapper_flow.py
