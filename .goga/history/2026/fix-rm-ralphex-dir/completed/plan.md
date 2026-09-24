# Resolution: `fix-rm-ralphex-dir`

Completed resolution of the bug investigated in `.goga/history/2026/fix-rm-ralphex-dir/todo.md`.
Delivered by commit `ceb05d5` (`fix: stop pytest runs from re-creating .ralphex in the repo
root`, branch `fix-rm-ralphex-dir`); accepted by the goga-accept pipeline on 24/09/26 with the
verdict **ACCEPTED_WITH_NOTES**.

---

## Defect

A full pytest run re-created `.ralphex/config` in the repository root, defeating the pipeline
`after_script 'rm -rf .ralphex'`: the cleanup executed successfully, yet the directory
reappeared ~6 minutes later when the acceptance stage's Test Coverage Assessment step ran the
whole suite. Root cause (verified by reproduction): `test_run_build_pass_no_direct_subprocess`
never chdir'd into `tmp_path`, so the real `write_ralphex_config` invoked by `run_build_pass`
wrote the cwd-relative config into the pytest root — inside the pipeline container, `/workspace`
is a bind mount of the host project, so the write propagated to the host.

## Applied changes (test-only; commit `ceb05d5`, 3 files, +21/-1)

1. `tests/build/test_build_pass.py` — restored `monkeypatch.chdir(tmp_path)` as the first
   statement of `test_run_build_pass_no_direct_subprocess`, matching every sibling test in
   the file.
2. `tests/conftest.py` — added the autouse `_isolate_cwd` fixture: every test's process CWD is
   redirected to `tmp_path`, so no cwd-relative write (`.ralphex`, `.goga`) can reach the
   project root regardless of individual test discipline. Per-test `monkeypatch.chdir` calls
   still win — they run after the autouse fixture setup.
3. `tests/ast/test_rules.py` — adapted `test_existing_path_outside_cwd` to the suite-wide CWD
   isolation: the test now chdirs into `tmp_path/'project'` and places the outside file in
   `tmp_path/'outside_project'`, preserving the outside-CWD relation the rule
   (`ImportHasValidFromPath`) must reject.

Production code, CODEMANIFESTs, and usage files are untouched.

## Verification

| Check | Result |
|---|---|
| Scoped tests (`tests/build/test_build_pass.py`, `tests/ast/test_rules.py`) | 188 passed |
| Full suite (`pytest tests/`) | 6099 passed, 0 failed, 60 warnings, 58s |
| Repo root after the full run | `.ralphex` absent; `git status --porcelain` empty |
| `goga lint` | 81 cells, 0 errors |
| `goga contract goga/ast/rules`, `goga contract goga/build` | exit 0, consistent |
| Manifest / usages / coverage review | CONSISTENT / CONSISTENT / EXCELLENT |

The reproduction path from `todo.md` is closed: running the suite from the repo root leaves no
`.ralphex` behind.

## Acceptance verdict

ACCEPTED_WITH_NOTES — zero critical findings; three INFO notes, all pre-existing and
non-blocking:

- the `goga/build` facade exports only `build` while its manifest declares 12 types
  (deliberate narrow public API, unchanged by this fix);
- `goga/ast/rules` carries the baseline annotation block in condensed form (a style shared
  by 14/81 cells);
- no meta-test asserts repo-root cleanliness — the autouse `_isolate_cwd` fixture guards the
  incident class structurally, and the pipeline after_script remains the outer detection.

## Residual gap (open, out of scope — tracked in `todo.md`)

The in-container development workflow's `build` stage (`python3 -m goga.build`, cwd
`/workspace`) is itself a writer of `.ralphex/` into the project by design of the cwd-relative
path; a durable solution would redirect it to a runtime directory. Not part of this fix.
