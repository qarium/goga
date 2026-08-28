"""Contract and logic tests for the branch routines declared in
``goga/commands/pipeline/CODEMANIFEST`` with ``location: branch.py``:

- ``check_branch_occupancy(branch_name, slug) -> str | None`` — three-oracle
  occupancy check (local ref, remote-tracking ref, history topic via the
  domain oracle ``topic_exists``)
- ``ensure_pipeline_branch(branch_name: str) -> str`` — the branch-procedure
  orchestrator (re-ask cycle, non-terminal abort, no-git-host conversion, the
  single create-and-switch mutation)

The slug transformer and the git current-branch reader are NOT local anymore:
they are Imported from the history domain (``goga.history``) and only their
identity with the domain facade is asserted here — their behavior suites live
in ``tests/history/``.

Git is mocked at the subprocess boundary per the ``git`` practice — one
``run`` dispatcher laid over BOTH invocation points at once
(``goga.history.git.branch`` and this cell's ``branch`` module) via
``contextlib.ExitStack``; mocking only one of them would release real git into
the test.
"""

from __future__ import annotations

import contextlib
import subprocess
import typing
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.commands.pipeline import branch as branch_module
from goga.history import naming as history_naming
from goga.history.git import branch as history_git_branch_module

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


@contextlib.contextmanager
def _git_on_both_points(run_mock: mock.Mock) -> Iterator[mock.Mock]:
    """Lay one ``run`` dispatcher over BOTH git invocation points at once.

    ``ensure_pipeline_branch`` spans two modules after the domain migration:
    ``--show-current`` runs in ``goga.history.git.branch`` while ``show-ref``,
    ``for-each-ref``, and ``switch`` run in this cell's ``branch`` module. A
    mock on only one of the two points would let the other run real git.
    """
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(history_git_branch_module.subprocess, "run", run_mock))
        stack.enter_context(mock.patch.object(branch_module.subprocess, "run", run_mock))
        yield run_mock


class _FixedClock:
    """Stand-in for ``datetime`` answering a fixed naive date."""

    @staticmethod
    def now() -> datetime:
        return datetime(2031, 6, 15)  # noqa: DTZ001 — a fixed naive date is the point of the clock


def _switch_argv_calls(run_mock: mock.Mock) -> list[list[str]]:
    """The recorded ``git switch`` argvs (usually asserted to be empty)."""
    return [call.args[0] for call in run_mock.call_args_list if call.args[0][1] == "switch"]


# --- Contract tests ---


class TestBranchContract:
    def test_branch_routines_exist_and_are_callable(self) -> None:
        """The two routines are defined on the branch module and callable."""
        assert callable(branch_module.check_branch_occupancy)
        assert callable(branch_module.ensure_pipeline_branch)

    def test_check_branch_occupancy_signature(self) -> None:
        """``check_branch_occupancy(branch_name: str, slug: str) -> str | None``."""
        import inspect

        signature = inspect.signature(branch_module.check_branch_occupancy)
        assert list(signature.parameters) == ["branch_name", "slug"]
        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        hints = typing.get_type_hints(branch_module.check_branch_occupancy)
        assert hints == {"branch_name": str, "slug": str, "return": str | None}

    def test_ensure_pipeline_branch_signature(self) -> None:
        """``ensure_pipeline_branch(branch_name: str) -> str``."""
        import inspect

        signature = inspect.signature(branch_module.ensure_pipeline_branch)
        assert list(signature.parameters) == ["branch_name"]
        assert signature.parameters["branch_name"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        hints = typing.get_type_hints(branch_module.ensure_pipeline_branch)
        assert hints == {"branch_name": str, "return": str}

    def test_moved_routines_are_bound_to_the_domain_not_local_copies(self) -> None:
        """The moved names resolve to the DOMAIN objects — a local ``def`` copy would differ."""
        import goga.history

        assert branch_module.normalize_topic_slug is goga.history.normalize_topic_slug
        assert branch_module.resolve_current_branch_name is goga.history.resolve_current_branch_name

    def test_pipeline_facade_all_without_moved_names(self) -> None:
        """The package facade exports exactly the seven names — the moved routines are gone."""
        from goga.commands.pipeline import __all__ as facade_all

        assert facade_all == [
            "check_branch_occupancy",
            "clean_pipeline_runtime_dir",
            "ensure_pipeline_branch",
            "pipeline",
            "resolve_pipeline_runtime_dir",
            "run_pipeline_container",
            "run_pipeline_info_container",
        ]


# --- Logic tests: check_branch_occupancy (three oracles) ---


class TestCheckBranchOccupancy:
    def test_check_branch_occupancy_local_ref_reports_reason(self) -> None:
        """Oracle 1: an existing local branch ref reports the reason; later oracles not probed."""
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=_GitResult(returncode=0),
            for_each_ref=_GitResult(stdout="refs/remotes/origin/feat/x\n"),
        )
        with _git_on_both_points(run_mock):
            conflict = branch_module.check_branch_occupancy("feat/x", "feat-x")
        assert conflict == "branch 'feat/x' already exists"
        probed = [call.args[0] for call in run_mock.call_args_list]
        assert all(argv[1] != "for-each-ref" for argv in probed)

    def test_check_branch_occupancy_remote_tracking_ref_reports_reason(self) -> None:
        """Oracle 2: an existing remote-tracking ref reports the reason (exact branch match)."""
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=_GitResult(stdout="refs/remotes/origin/feat/x\nrefs/remotes/origin/main\n"),
        )
        with _git_on_both_points(run_mock):
            conflict = branch_module.check_branch_occupancy("feat/x", "feat-x")
        assert conflict == "remote-tracking branch 'feat/x' already exists"

    def test_check_branch_occupancy_remote_ref_no_prefix_match(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``feat/x`` must not match the remote branch ``feat/xy`` — exact equality only."""
        monkeypatch.chdir(tmp_path)
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=_GitResult(stdout="refs/remotes/origin/feat/xy\nrefs/remotes/origin/main\n"),
        )
        with _git_on_both_points(run_mock):
            conflict = branch_module.check_branch_occupancy("feat/x", "feat-x")
        assert conflict is None

    def test_check_branch_occupancy_two_param_topic_oracle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Oracle 3: the DOMAIN resolves the year — two parameters, no clock here.

        The year 2031 comes from the fixed clock patched at the domain's
        ``naming.datetime`` (the mandated bare-``now()`` point); this cell
        computes no year of its own. The reason names the slug for the current
        year — no hand-built path in the message.
        """
        (tmp_path / ".goga" / "history" / "2031" / "feat-x").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=_GitResult(stdout=""),
        )
        with (
            mock.patch.object(history_naming, "datetime", _FixedClock),
            _git_on_both_points(run_mock),
        ):
            conflict = branch_module.check_branch_occupancy("feat/x", "feat-x")
        assert conflict == "history topic 'feat-x' already exists for the current year"
        assert _switch_argv_calls(run_mock) == []

    def test_check_branch_occupancy_stray_file_is_not_topic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stray FILE named <slug> does not occupy a topic — only a directory does."""
        (tmp_path / ".goga" / "history" / "2031" / "feat-x").parent.mkdir(parents=True)
        (tmp_path / ".goga" / "history" / "2031" / "feat-x").write_text("stray")
        monkeypatch.chdir(tmp_path)
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=_GitResult(stdout=""),
        )
        with (
            mock.patch.object(history_naming, "datetime", _FixedClock),
            _git_on_both_points(run_mock),
        ):
            assert branch_module.check_branch_occupancy("feat/x", "feat-x") is None

    def test_check_branch_occupancy_oracle_listing_failure_propagates(self) -> None:
        """A git infrastructure failure of oracle 2 itself propagates (not an occupancy answer)."""
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=subprocess.CalledProcessError(128, "git", stderr="fatal: not a git repository"),
        )
        with (
            _git_on_both_points(run_mock),
            pytest.raises(subprocess.CalledProcessError),
        ):
            branch_module.check_branch_occupancy("feat/x", "feat-x")


# --- Logic tests: ensure_pipeline_branch (the branch-procedure orchestrator) ---


class TestEnsurePipelineBranch:
    def test_ensure_pipeline_branch_end_to_end_free_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One dispatcher over both points: a free name returns the entered name and switches."""
        monkeypatch.chdir(tmp_path)
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=_GitResult(stdout=""),
            switch=_GitResult(returncode=0),
        )
        with _git_on_both_points(run_mock):
            assert branch_module.ensure_pipeline_branch("feat/x") == "feat/x"
        assert run_mock.call_args.args[0] == ["git", "switch", "-c", "feat/x"]

    def test_ensure_pipeline_branch_creates_and_switches_as_entered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A free name is created with the ENTERED name (topic is the slug — duality)."""
        monkeypatch.chdir(tmp_path)
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=_GitResult(stdout=""),
            switch=_GitResult(returncode=0),
        )
        with _git_on_both_points(run_mock):
            assert branch_module.ensure_pipeline_branch("Feature/X") == "Feature/X"
        assert run_mock.call_args.args[0] == ["git", "switch", "-c", "Feature/X"]

    def test_ensure_pipeline_branch_already_on_branch_returns_current_name(self) -> None:
        """Slug equality with the current branch → the CURRENT name, one probe, no mutation."""
        run_mock = _git_run_dispatch(show_current=_GitResult(stdout="release/1.3.0\n"))
        with _git_on_both_points(run_mock):
            assert branch_module.ensure_pipeline_branch("release-1.3.0") == "release/1.3.0"
        assert run_mock.call_count == 1
        assert run_mock.call_args.args[0] == ["git", "branch", "--show-current"]

    def test_ensure_pipeline_branch_empty_slug_no_tty_fails_with_hint(self) -> None:
        """Empty slug without a terminal → ClickException with the reason and the -b hint."""
        run_mock = _git_run_dispatch()
        with (
            _git_on_both_points(run_mock),
            mock.patch.object(branch_module.sys.stdin, "isatty", return_value=False),
            pytest.raises(click.ClickException) as excinfo,
        ):
            branch_module.ensure_pipeline_branch("Релиз")
        message = str(excinfo.value)
        assert "normalizes to an empty topic slug" in message
        assert "Pass another branch name via -b." in message
        assert _switch_argv_calls(run_mock) == []

    def test_ensure_pipeline_branch_empty_slug_cli_semantics_stderr_exit_1(self) -> None:
        """The ClickException surfaces as stderr + exit 1 through a click command."""

        @click.command()
        def _probe() -> None:
            branch_module.ensure_pipeline_branch("Релиз")

        with _git_on_both_points(_git_run_dispatch()):
            result = CliRunner().invoke(_probe, [])
        assert result.exit_code == 1
        assert "normalizes to an empty topic slug" in result.stderr
        assert "Pass another branch name via -b." in result.stderr

    def test_ensure_pipeline_branch_conflict_no_tty_fails_with_reason(self) -> None:
        """A conflict without a terminal → ClickException with the oracle reason and hint."""
        run_mock = _git_run_dispatch(show_ref=_GitResult(returncode=0))
        with (
            _git_on_both_points(run_mock),
            mock.patch.object(branch_module.sys.stdin, "isatty", return_value=False),
            pytest.raises(click.ClickException) as excinfo,
        ):
            branch_module.ensure_pipeline_branch("feat/x")
        message = str(excinfo.value)
        assert "branch 'feat/x' already exists" in message
        assert "Pass another branch name via -b." in message
        assert _switch_argv_calls(run_mock) == []

    def test_ensure_pipeline_branch_history_topic_conflict_no_tty_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Oracle 3 through the orchestrator: the domain topic oracle wins for the current year.

        The year is pinned at the domain's ``naming.datetime`` — the only
        clock left in the procedure. The reason names the slug and the current
        year, not a hand-composed path.
        """
        (tmp_path / ".goga" / "history" / "2031" / "feat-x").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=_GitResult(stdout=""),
        )
        with (
            mock.patch.object(history_naming, "datetime", _FixedClock),
            _git_on_both_points(run_mock),
            mock.patch.object(branch_module.sys.stdin, "isatty", return_value=False),
            pytest.raises(click.ClickException) as excinfo,
        ):
            branch_module.ensure_pipeline_branch("feat/x")
        message = str(excinfo.value)
        assert "history topic 'feat-x' already exists for the current year" in message
        assert "Pass another branch name via -b." in message
        assert _switch_argv_calls(run_mock) == []

    def test_ensure_pipeline_branch_tty_reask_until_free(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """On a terminal an occupied name re-asks; the NEW name runs the FULL procedure."""
        monkeypatch.chdir(tmp_path)
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=[_GitResult(returncode=0), subprocess.CalledProcessError(1, "git")],
            for_each_ref=_GitResult(stdout=""),
            switch=_GitResult(returncode=0),
        )
        with (
            _git_on_both_points(run_mock),
            mock.patch.object(branch_module.sys.stdin, "isatty", return_value=True),
            mock.patch.object(branch_module.click, "prompt", return_value="feat/two") as prompt_mock,
        ):
            assert branch_module.ensure_pipeline_branch("feat/one") == "feat/two"
        assert prompt_mock.call_count == 1
        assert run_mock.call_args.args[0] == ["git", "switch", "-c", "feat/two"]

    def test_ensure_pipeline_branch_abort_leaves_repository_untouched(self) -> None:
        """Ctrl-C at the re-ask prompt propagates as click.Abort — no switch ever ran."""
        run_mock = _git_run_dispatch(show_ref=_GitResult(returncode=0))
        with (
            _git_on_both_points(run_mock),
            mock.patch.object(branch_module.sys.stdin, "isatty", return_value=True),
            mock.patch.object(branch_module.click, "prompt", side_effect=click.Abort()),
            pytest.raises(click.Abort),
        ):
            branch_module.ensure_pipeline_branch("feat/x")
        assert _switch_argv_calls(run_mock) == []

    def test_ensure_pipeline_branch_git_rejects_invalid_name_surfaces_stderr(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """git owns name validity — its stderr is surfaced in the ClickException."""
        monkeypatch.chdir(tmp_path)
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=_GitResult(stdout=""),
            switch=subprocess.CalledProcessError(128, "git", stderr="fatal: 'a b' is not a valid branch name"),
        )
        with (
            _git_on_both_points(run_mock),
            pytest.raises(click.ClickException) as excinfo,
        ):
            branch_module.ensure_pipeline_branch("a b")
        message = str(excinfo.value)
        assert "git failed to create branch" in message
        assert "fatal: 'a b' is not a valid branch name" in message

    def test_ensure_pipeline_branch_missing_git_binary_fails_cleanly(self) -> None:
        """A no-git host is a clean ClickException — never a traceback (both points)."""
        run_mock = mock.Mock(side_effect=FileNotFoundError("git"))
        with (
            _git_on_both_points(run_mock),
            pytest.raises(click.ClickException) as excinfo,
        ):
            branch_module.ensure_pipeline_branch("feat/x")
        assert str(excinfo.value) == "git is required for -b/--branch: git binary not found"
        assert _switch_argv_calls(run_mock) == []

    def test_ensure_pipeline_branch_ref_listing_failure_fails_cleanly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A git infra failure of the oracles (e.g. outside a repository) is a clean error.

        ``git for-each-ref`` exiting non-zero (128 outside a repository) must
        surface as a ClickException carrying git's stderr — never a raw
        ``CalledProcessError`` traceback out of the CLI.
        """
        monkeypatch.chdir(tmp_path)
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=subprocess.CalledProcessError(128, "git", stderr="fatal: not a git repository"),
        )
        with (
            _git_on_both_points(run_mock),
            pytest.raises(click.ClickException) as excinfo,
        ):
            branch_module.ensure_pipeline_branch("feat/x")
        message = str(excinfo.value)
        assert "git failed to check branch occupancy" in message
        assert "fatal: not a git repository" in message
        assert _switch_argv_calls(run_mock) == []

    def test_ensure_pipeline_branch_reask_validates_new_name_fully(self) -> None:
        """The re-asked name re-runs slug + already-on-branch + occupancy — fully."""
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=[_GitResult(returncode=0)],
        )
        with (
            _git_on_both_points(run_mock),
            mock.patch.object(branch_module.sys.stdin, "isatty", return_value=True),
            mock.patch.object(branch_module.click, "prompt", return_value="main"),
        ):
            assert branch_module.ensure_pipeline_branch("feat/one") == "main"
        assert _switch_argv_calls(run_mock) == []

    def test_ensure_pipeline_branch_empty_slug_tty_reasks_new_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An empty slug on a terminal re-asks; the loop restarts with the new name.

        The empty-slug branch shares the re-ask machinery with the conflict
        branch, but it fires BEFORE the already-on-branch and occupancy steps —
        so the first iteration must not reach a single oracle. The re-asked
        name then runs the full procedure: occupancy is free, the branch is
        created exactly as entered.
        """
        monkeypatch.chdir(tmp_path)
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=_GitResult(stdout=""),
            switch=_GitResult(returncode=0),
        )
        with (
            _git_on_both_points(run_mock),
            mock.patch.object(branch_module.sys.stdin, "isatty", return_value=True),
            mock.patch.object(branch_module.click, "prompt", return_value="feat/two") as prompt_mock,
        ):
            assert branch_module.ensure_pipeline_branch("Релиз/Один") == "feat/two"
        assert prompt_mock.call_count == 1
        reason = capsys.readouterr().err
        assert "normalizes to an empty topic slug" in reason
        assert "Релиз/Один" in reason
        assert run_mock.call_args.args[0] == ["git", "switch", "-c", "feat/two"]
