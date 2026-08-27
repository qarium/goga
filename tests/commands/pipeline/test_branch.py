"""Contract and logic tests for the branch routines declared in
``goga/commands/pipeline/CODEMANIFEST`` with ``location: branch.py``:

- ``normalize_topic_slug(name: str) -> str`` — pure slug transformer
- ``resolve_current_branch_name() -> str | None`` — git reader with the three
  documented None modes (detached HEAD, missing git binary, non-repository)
- ``check_branch_occupancy(branch_name, slug, history_year) -> str | None`` —
  three-oracle occupancy check (local ref, remote-tracking ref, history topic)
- ``ensure_pipeline_branch(branch_name: str) -> str`` — the branch-procedure
  orchestrator (re-ask cycle, non-terminal abort, no-git-host conversion, the
  single create-and-switch mutation)

Git is mocked at the subprocess boundary per the ``git`` practice —
``mock.patch.object(branch_module.subprocess, "run")`` — never as a git double.
"""

from __future__ import annotations

import subprocess
import typing
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.commands.pipeline import branch as branch_module

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
            if tuple(argv[1 : 1 + len(key)]) == key or tuple(argv[1:]) == key:
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


class TestBranchContract:
    def test_three_primitives_exist_and_are_callable(self) -> None:
        """The three routines are defined on the branch module and callable."""
        assert callable(branch_module.normalize_topic_slug)
        assert callable(branch_module.resolve_current_branch_name)
        assert callable(branch_module.check_branch_occupancy)

    def test_normalize_topic_slug_signature(self) -> None:
        """``normalize_topic_slug(name: str) -> str``."""
        hints = typing.get_type_hints(branch_module.normalize_topic_slug)
        assert hints == {"name": str, "return": str}

    def test_resolve_current_branch_name_signature(self) -> None:
        """``resolve_current_branch_name() -> str | None``."""
        hints = typing.get_type_hints(branch_module.resolve_current_branch_name)
        assert hints["return"] == str | None

    def test_check_branch_occupancy_signature(self) -> None:
        """``check_branch_occupancy(branch_name: str, slug: str, history_year: str) -> str | None``."""
        import inspect

        signature = inspect.signature(branch_module.check_branch_occupancy)
        assert list(signature.parameters) == ["branch_name", "slug", "history_year"]
        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        hints = typing.get_type_hints(branch_module.check_branch_occupancy)
        assert hints == {
            "branch_name": str,
            "slug": str,
            "history_year": str,
            "return": str | None,
        }

    def test_resolve_current_branch_name_signature_parameters(self) -> None:
        """``resolve_current_branch_name`` takes no parameters."""
        import inspect

        signature = inspect.signature(branch_module.resolve_current_branch_name)
        assert list(signature.parameters) == []
        hints = typing.get_type_hints(branch_module.resolve_current_branch_name)
        assert hints == {"return": str | None}

    def test_normalize_topic_slug_parameters(self) -> None:
        """``normalize_topic_slug`` takes one positional-or-keyword ``name``."""
        import inspect

        signature = inspect.signature(branch_module.normalize_topic_slug)
        assert list(signature.parameters) == ["name"]
        assert signature.parameters["name"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD

    def test_ensure_pipeline_branch_exists_and_is_callable(self) -> None:
        """The orchestrator is defined on the branch module and callable."""
        assert callable(branch_module.ensure_pipeline_branch)

    def test_ensure_pipeline_branch_signature(self) -> None:
        """``ensure_pipeline_branch(branch_name: str) -> str``."""
        import inspect

        signature = inspect.signature(branch_module.ensure_pipeline_branch)
        assert list(signature.parameters) == ["branch_name"]
        assert signature.parameters["branch_name"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        hints = typing.get_type_hints(branch_module.ensure_pipeline_branch)
        assert hints == {"branch_name": str, "return": str}

    def test_ensure_pipeline_branch_free_name_returns_entered_name(self) -> None:
        """A free name creates-and-switches and returns the entered name (str → str)."""
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=_GitResult(stdout=""),
            switch=_GitResult(returncode=0),
        )
        with mock.patch.object(branch_module.subprocess, "run", run_mock):
            assert branch_module.ensure_pipeline_branch("feat/x") == "feat/x"


# --- Logic tests: normalize_topic_slug (pure transformer) ---


class TestNormalizeTopicSlug:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Feature/Foo_Bar", "feature-foo-bar"),
            ("release/1.3.0", "release-1-3-0"),
            ("Релиз/Один", ""),
            ("aБb", "ab"),
            ("-a--b-", "a-b"),
            ("My Tool", "my-tool"),
            ("feat///x", "feat-x"),
            ("UPPER", "upper"),
            ("123", "123"),
        ],
    )
    def test_normalize_topic_slug_parametrized(self, name: str, expected: str) -> None:
        """The grammar rows from the contract — deterministic pure transform."""
        assert branch_module.normalize_topic_slug(name) == expected

    def test_normalize_topic_slug_empty_result_is_valid_output(self) -> None:
        """A fully non-ASCII name yields "" — no fallback, no raise."""
        assert branch_module.normalize_topic_slug("Релиз/Один") == ""


# --- Logic tests: resolve_current_branch_name (git reader) ---


class TestResolveCurrentBranchName:
    def test_resolve_current_branch_name_returns_stripped_raw_name(self) -> None:
        """The raw branch name is returned stripped and unmodified (no slugification)."""
        result = _GitResult(returncode=0, stdout="  release/1.3.0\n")
        with mock.patch.object(branch_module.subprocess, "run", return_value=result) as run_mock:
            branch = branch_module.resolve_current_branch_name()
        assert branch == "release/1.3.0"
        assert run_mock.call_args.args[0] == ["git", "branch", "--show-current"]
        assert run_mock.call_args.kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"

    def test_resolve_current_branch_name_detached_head_returns_none(self) -> None:
        """Detached HEAD — an empty git answer — yields None."""
        result = _GitResult(returncode=0, stdout="")
        with mock.patch.object(branch_module.subprocess, "run", return_value=result):
            assert branch_module.resolve_current_branch_name() is None

    def test_resolve_current_branch_name_not_a_repository_returns_none(self) -> None:
        """A non-repository (non-zero git exit) yields None."""
        error = subprocess.CalledProcessError(128, "git")
        with mock.patch.object(branch_module.subprocess, "run", side_effect=error):
            assert branch_module.resolve_current_branch_name() is None

    def test_resolve_current_branch_name_missing_git_binary_returns_none(self) -> None:
        """A missing git binary yields None."""
        with mock.patch.object(branch_module.subprocess, "run", side_effect=FileNotFoundError("git")):
            assert branch_module.resolve_current_branch_name() is None

    def test_resolve_current_branch_name_unexpected_os_error_propagates(self) -> None:
        """Unexpected OS-level failures are NOT swallowed — PermissionError propagates."""
        with (
            mock.patch.object(branch_module.subprocess, "run", side_effect=PermissionError("denied")),
            pytest.raises(PermissionError),
        ):
            branch_module.resolve_current_branch_name()


# --- Logic tests: check_branch_occupancy (three oracles) ---


class TestCheckBranchOccupancy:
    def test_check_branch_occupancy_local_ref_reports_reason(self) -> None:
        """Oracle 1: an existing local branch ref reports the reason; later oracles not probed."""
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=_GitResult(returncode=0),
            for_each_ref=_GitResult(stdout="refs/remotes/origin/feat/x\n"),
        )
        with mock.patch.object(branch_module.subprocess, "run", run_mock):
            conflict = branch_module.check_branch_occupancy("feat/x", "feat-x", "2026")
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
        with mock.patch.object(branch_module.subprocess, "run", run_mock):
            conflict = branch_module.check_branch_occupancy("feat/x", "feat-x", "2026")
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
        with mock.patch.object(branch_module.subprocess, "run", run_mock):
            conflict = branch_module.check_branch_occupancy("feat/x", "feat-x", "2026")
        assert conflict is None

    def test_check_branch_occupancy_history_topic_folder_reports_reason(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Oracle 3: an existing history topic DIRECTORY (checked by slug) reports the reason."""
        (tmp_path / ".goga" / "history" / "2026" / "feat-x").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=_GitResult(stdout=""),
        )
        with mock.patch.object(branch_module.subprocess, "run", run_mock):
            conflict = branch_module.check_branch_occupancy("feat/x", "feat-x", "2026")
        assert conflict == "history topic '.goga/history/2026/feat-x' already exists"

    def test_check_branch_occupancy_stray_file_is_not_a_topic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stray FILE named <slug> does not occupy a topic — only a directory does."""
        (tmp_path / ".goga" / "history" / "2026" / "feat-x").parent.mkdir(parents=True)
        (tmp_path / ".goga" / "history" / "2026" / "feat-x").write_text("stray")
        monkeypatch.chdir(tmp_path)
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=_GitResult(stdout=""),
        )
        with mock.patch.object(branch_module.subprocess, "run", run_mock):
            assert branch_module.check_branch_occupancy("feat/x", "feat-x", "2026") is None


# --- Logic tests: ensure_pipeline_branch (the branch-procedure orchestrator) ---


def _switch_argv_calls(run_mock: mock.Mock) -> list[list[str]]:
    """The recorded ``git switch`` argvs (usually asserted to be empty)."""
    return [call.args[0] for call in run_mock.call_args_list if call.args[0][1] == "switch"]


class TestEnsurePipelineBranch:
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
        with mock.patch.object(branch_module.subprocess, "run", run_mock):
            assert branch_module.ensure_pipeline_branch("Feature/X") == "Feature/X"
        assert run_mock.call_args.args[0] == ["git", "switch", "-c", "Feature/X"]

    def test_ensure_pipeline_branch_already_on_branch_returns_current_name(self) -> None:
        """Slug equality with the current branch → the CURRENT name, one probe, no mutation."""
        run_mock = _git_run_dispatch(show_current=_GitResult(stdout="release/1.3.0\n"))
        with mock.patch.object(branch_module.subprocess, "run", run_mock):
            assert branch_module.ensure_pipeline_branch("release-1.3.0") == "release/1.3.0"
        assert run_mock.call_count == 1
        assert run_mock.call_args.args[0] == ["git", "branch", "--show-current"]

    def test_ensure_pipeline_branch_empty_slug_no_tty_fails_with_hint(self) -> None:
        """Empty slug without a terminal → ClickException with the reason and the -b hint."""
        run_mock = _git_run_dispatch()
        with (
            mock.patch.object(branch_module.subprocess, "run", run_mock),
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

        with mock.patch.object(branch_module.subprocess, "run", _git_run_dispatch()):
            result = CliRunner().invoke(_probe, [])
        assert result.exit_code == 1
        assert "normalizes to an empty topic slug" in result.stderr
        assert "Pass another branch name via -b." in result.stderr

    def test_ensure_pipeline_branch_conflict_no_tty_fails_with_reason(self) -> None:
        """A conflict without a terminal → ClickException with the oracle reason and hint."""
        run_mock = _git_run_dispatch(show_ref=_GitResult(returncode=0))
        with (
            mock.patch.object(branch_module.subprocess, "run", run_mock),
            mock.patch.object(branch_module.sys.stdin, "isatty", return_value=False),
            pytest.raises(click.ClickException) as excinfo,
        ):
            branch_module.ensure_pipeline_branch("feat/x")
        message = str(excinfo.value)
        assert "branch 'feat/x' already exists" in message
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
            mock.patch.object(branch_module.subprocess, "run", run_mock),
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
            mock.patch.object(branch_module.subprocess, "run", run_mock),
            mock.patch.object(branch_module.sys.stdin, "isatty", return_value=True),
            mock.patch.object(branch_module.click, "prompt", side_effect=click.Abort()),
            pytest.raises(click.Abort),
        ):
            branch_module.ensure_pipeline_branch("feat/x")
        assert _switch_argv_calls(run_mock) == []

    def test_ensure_pipeline_branch_git_rejects_invalid_name_surfaces_stderr(self) -> None:
        """git owns name validity — its stderr is surfaced in the ClickException."""
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=subprocess.CalledProcessError(1, "git"),
            for_each_ref=_GitResult(stdout=""),
            switch=subprocess.CalledProcessError(128, "git", stderr="fatal: 'a b' is not a valid branch name"),
        )
        with (
            mock.patch.object(branch_module.subprocess, "run", run_mock),
            pytest.raises(click.ClickException) as excinfo,
        ):
            branch_module.ensure_pipeline_branch("a b")
        message = str(excinfo.value)
        assert "git failed to create branch" in message
        assert "fatal: 'a b' is not a valid branch name" in message

    def test_ensure_pipeline_branch_missing_git_binary_fails_cleanly(self) -> None:
        """A no-git host is a clean ClickException — never a traceback."""
        run_mock = mock.Mock(side_effect=FileNotFoundError("git"))
        with (
            mock.patch.object(branch_module.subprocess, "run", run_mock),
            pytest.raises(click.ClickException) as excinfo,
        ):
            branch_module.ensure_pipeline_branch("feat/x")
        assert str(excinfo.value) == "git is required for -b/--branch: git binary not found"
        assert _switch_argv_calls(run_mock) == []

    def test_ensure_pipeline_branch_reask_validates_new_name_fully(self) -> None:
        """The re-asked name re-runs slug + already-on-branch + occupancy — fully."""
        run_mock = _git_run_dispatch(
            show_current=_GitResult(stdout="main\n"),
            show_ref=[_GitResult(returncode=0)],
        )
        with (
            mock.patch.object(branch_module.subprocess, "run", run_mock),
            mock.patch.object(branch_module.sys.stdin, "isatty", return_value=True),
            mock.patch.object(branch_module.click, "prompt", return_value="main"),
        ):
            assert branch_module.ensure_pipeline_branch("feat/one") == "main"
        assert _switch_argv_calls(run_mock) == []
