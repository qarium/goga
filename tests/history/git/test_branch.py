"""Contract and logic tests for the routine declared in
``goga/history/git/CODEMANIFEST`` with ``location: branch.py``:

- ``resolve_current_branch_name() -> str | None`` — the raw git branch reader
  with the three documented None modes (detached HEAD, missing git binary,
  non-repository)

The cell's second module — the branch inventory of ``refs.py`` — is covered
by ``tests/history/git/test_refs.py``.

Git is mocked at the subprocess boundary per the ``git`` practice —
``mock.patch.object(branch_module.subprocess, "run")`` — never as a git double.
"""

from __future__ import annotations

import inspect
import subprocess
import typing
from unittest import mock

import pytest
from goga.history.git import branch as branch_module
from goga.history.git import resolve_current_branch_name

# --- Git subprocess mocking helpers (the process boundary only) ---


class _GitResult:
    """Minimal stand-in for a ``subprocess.CompletedProcess``."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _git_run_dispatch(
    show_current: object = _GitResult(stdout="main\n"),
    show_ref: object = subprocess.CalledProcessError(1, "git"),
    for_each_ref: object = _GitResult(stdout=""),
    switch: object = _GitResult(returncode=0),
) -> mock.Mock:
    """Build a ``subprocess.run`` mock dispatching per git subcommand.

    ``show_current`` / ``show_ref`` / ``for_each_ref`` / ``switch`` are either a
    ``_GitResult`` (returned) or an exception instance/class (raised). Any of
    them may instead be a LIST of such outcomes consumed in call order
    (exhausted → AssertionError) — for re-ask sequences where the same command
    must answer differently per iteration.
    """
    outcomes = {
        ("branch", "--show-current"): show_current,
        ("show-ref",): show_ref,
        ("for-each-ref",): for_each_ref,
        ("switch",): switch,
    }
    queues = {key: (list(value) if isinstance(value, list) else None) for key, value in outcomes.items()}

    def _run(argv: list[str], **_kwargs: object) -> _GitResult:
        for key, default_outcome in outcomes.items():
            if tuple(argv[1 : 1 + len(key)]) == key:
                outcome = default_outcome
                if queues[key] is not None:
                    if not queues[key]:
                        raise AssertionError(f"unexpected repeat of git argv in test: {argv!r}")
                    outcome = queues[key].pop(0)
                if isinstance(outcome, BaseException) or (
                    isinstance(outcome, type) and issubclass(outcome, BaseException)
                ):
                    raise outcome
                return outcome
        raise AssertionError(f"unexpected git argv in test: {argv!r}")

    return mock.Mock(side_effect=_run)


# --- Contract tests ---


class TestGitBranchContract:
    def test_routine_is_importable_from_facade_and_callable(self) -> None:
        """The routine is importable from ``goga.history.git`` and callable."""
        assert callable(resolve_current_branch_name)
        assert branch_module.resolve_current_branch_name is resolve_current_branch_name

    def test_facade_all_lists_the_routine(self) -> None:
        """The cell facade exports the reader and the inventory, sorted."""
        import goga.history.git

        assert goga.history.git.__all__ == [
            "BranchRef",
            "list_branch_refs",
            "resolve_current_branch_name",
        ]

    def test_resolve_current_branch_name_signature(self) -> None:
        """``resolve_current_branch_name() -> str | None`` — no parameters."""
        signature = inspect.signature(resolve_current_branch_name)
        assert list(signature.parameters) == []
        hints = typing.get_type_hints(resolve_current_branch_name)
        assert hints == {"return": str | None}


# --- Logic tests ---


class TestResolveCurrentBranchName:
    def test_returns_raw_branch_name_stripped(self) -> None:
        """A non-empty git answer is returned stripped and unmodified."""
        run_mock = _git_run_dispatch(show_current=_GitResult(stdout="  release/1.3.0\n"))

        with mock.patch.object(branch_module.subprocess, "run", run_mock):
            assert resolve_current_branch_name() == "release/1.3.0"

    def test_asks_git_show_current_without_terminal_prompts(self) -> None:
        """The invocation follows the ``git`` practice: argv and prompt-free env."""
        run_mock = _git_run_dispatch()

        with mock.patch.object(branch_module.subprocess, "run", run_mock):
            resolve_current_branch_name()

        call = run_mock.call_args
        assert call.args[0] == ["git", "branch", "--show-current"]
        assert call.kwargs["check"] is True
        assert call.kwargs["capture_output"] is True
        assert call.kwargs["text"] is True
        assert call.kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"

    def test_detached_head_returns_none(self) -> None:
        """An empty git answer (detached HEAD) is a documented None mode."""
        run_mock = _git_run_dispatch(show_current=_GitResult(stdout=""))

        with mock.patch.object(branch_module.subprocess, "run", run_mock):
            assert resolve_current_branch_name() is None

    def test_non_repository_returns_none(self) -> None:
        """A non-zero git exit (a non-repository) is a documented None mode."""
        run_mock = _git_run_dispatch(
            show_current=subprocess.CalledProcessError(128, "git", stderr="fatal: not a git repository"),
        )

        with mock.patch.object(branch_module.subprocess, "run", run_mock):
            assert resolve_current_branch_name() is None

    def test_missing_git_binary_returns_none(self) -> None:
        """A missing git binary is a documented None mode."""
        run_mock = mock.Mock(side_effect=FileNotFoundError("git"))

        with mock.patch.object(branch_module.subprocess, "run", run_mock):
            assert resolve_current_branch_name() is None

    def test_unexpected_os_failure_propagates(self) -> None:
        """An unexpected ``PermissionError`` is not swallowed by the None modes."""
        run_mock = mock.Mock(side_effect=PermissionError("git"))

        with mock.patch.object(branch_module.subprocess, "run", run_mock), pytest.raises(PermissionError):
            resolve_current_branch_name()
