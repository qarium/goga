# Bug: `rm -rf .ralphex` in the pipeline `after_script` succeeds, but `.ralphex/` reappears in the project root

## Summary

During a development pipeline run, the workflow `build` stage's `after_script` (`rm -rf .ralphex`) deletes the directory for real, yet `.ralphex/config` is present in the project root after the run. The directory is re-created ~6 minutes after the deletion by the acceptance stage: its Test Coverage Assessment step runs the full pytest suite, and one build test writes the cwd-relative `.ralphex/config` because it lacks the `monkeypatch.chdir(tmp_path)` isolation every sibling test has.

## Incident

Run: `GogaDevelopment-20260923-201902-4b9d` (flow `GogaDevelopment`, branch `add-hooks-to-schema`, project runtime dir `~/.goga/runtime/pipelines/Users-wb-IdeaProjects-python-qarium-goga/add-hooks-to-schema/development`). All times below are UTC; host-local time is UTC+3 (afm log lines are UTC, host mtimes are local).

| Time (UTC) | Event | Source |
|---|---|---|
| ~21:49 | `build` stage starts; `python3 -m goga.build` writes `.ralphex/{config,prompts,agents}` under `/workspace` (the project bind) | build stage script |
| 22:49:04.350 | `build` stage completes | `state.json` |
| 22:49:04 | `script_after` runs `rm -rf .ralphex` — the directory is deleted (exit 0, `Deleted successfully`, duration 0s) | `build/after.log` |
| 22:49:04 | `accept-result` ("Contracts & coverage audit") starts | `state.json` |
| 22:55:26–22:56:20 | Acceptance step 4 runs the full suite: `/opt/goga/bin/pytest tests/ -q` | accept transcript |
| 22:55:50 | `.ralphex/config` (223 bytes, only `config`) re-created in the project root | host mtime 01:55:50 +0300 |
| 22:58:59 | `accept-result` completes; run ends | `state.json` |

Observed final state: `.ralphex/` contains a single file `config` with `claude_command = /home/goga/bin/claude-as-claude.sh` — no `prompts/`, no `agents/`, which matches a bare `write_ralphex_config` call (no `sync_ralphex_defaults` involved).

## Root cause

`tests/build/test_build_pass.py:211` — `TestRunBuildPassContract::test_run_build_pass_no_direct_subprocess`:

```python
def test_run_build_pass_no_direct_subprocess(self, tmp_path, monkeypatch) -> None:
    with (
        mock.patch("goga.build.build_pass.run_ralphex", return_value=0),
        mock.patch("subprocess.call") as mock_call,
    ):
        run_build_pass("plan.md", _make_settings(), {}, WRAPPER, False)

    mock_call.assert_not_called()
```

The test accepts `tmp_path` and `monkeypatch` but never calls `monkeypatch.chdir(tmp_path)` — every other test in the file does. `run_build_pass` calls the real `write_ralphex_config`, which writes the cwd-relative `Path(".ralphex")` (`goga/build/ralphex_config.py:68-72`). With pytest running from the repo root, the file lands in `<project>/.ralphex/config`. Inside the pipeline container `/workspace` is a bind mount of the host project, so the write propagates to the host.

Reproduction (verified): run the single test from the repo root — it creates `.ralphex/config` byte-identical to the file found after the pipeline run (confirmed by `diff` against a preserved copy).

## Contributing factors

- The pipeline container has no mount shadowing `/workspace/.ralphex` (mounts: project, `/home/goga/pipeline`, afm config — `goga/commands/pipeline/run_pipeline_container.py`). The host-side `goga build` command keeps ralphex bytes out of the project via the nested mount `-v {runtime_dir}:/workspace/.ralphex` plus `_cleanup_ralphex_in_project` (`goga/commands/build/build.py`); in-container paths bypass both protections.
- The development workflow's `build` stage (`python3 -m goga.build`, cwd `/workspace`) is itself a writer of `.ralphex/` into the project — that is what the `after_script` was trying to clean up. The cleanup cannot stick while any later full-suite pytest run re-creates the directory.
- `tests/conftest.py` isolates `$HOME` (`_isolate_home`) but not the process CWD, so cwd-relative writes leak into the project root on every full-suite run — on the host this is silent, in the pipeline container it mutates the host project through the bind.

## Suggested fix

1. Add `monkeypatch.chdir(tmp_path)` to `test_run_build_pass_no_direct_subprocess` (one line, matches the sibling tests).
2. Optional hardening: an autouse CWD-isolation fixture in `tests/conftest.py` (chdir into a tmp dir per test), so no cwd-relative write can reach the project root regardless of individual test discipline.
3. Separate open gap (not this bug): the in-container `python3 -m goga.build` workflow stage writes `.ralphex/` into the project by design of the cwd-relative path; a durable solution is redirecting it to a runtime directory.
