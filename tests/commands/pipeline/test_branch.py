"""Contract and logic tests for the three branch primitives declared in
``goga/commands/pipeline/CODEMANIFEST`` with ``location: branch.py``:

- ``normalize_topic_slug(name: str) -> str`` — pure slug transformer
- ``resolve_current_branch_name() -> str | None`` — git reader with the three
  documented None modes (detached HEAD, missing git binary, non-repository)
- ``check_branch_occupancy(branch_name, slug, history_year) -> str | None`` —
  three-oracle occupancy check (local ref, remote-tracking ref, history topic)

The fourth declared routine, ``ensure_pipeline_branch``, is covered by its own
task and is intentionally absent here. Git is mocked at the subprocess boundary
per the ``git`` practice — ``mock.patch.object(branch_module.subprocess, "run")``
— never as a git double.
"""

from __future__ import annotations

import subprocess
import typing
from pathlib import Path
from unittest import mock

import pytest
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
) -> mock.Mock:
    """Build a ``subprocess.run`` mock dispatching per git subcommand.

    ``show_current`` / ``show_ref`` / ``for_each_ref`` are either a
    ``_GitResult`` (returned) or an exception instance/class (raised).
    """
    outcomes = {
        ("branch", "--show-current"): show_current,
        ("show-ref",): show_ref,
        ("for-each-ref",): for_each_ref,
    }

    def _run(argv: list[str], **_kwargs: object) -> _GitResult:
        for key, outcome in outcomes.items():
            if tuple(argv[1 : 1 + len(key)]) == key or tuple(argv[1:]) == key:
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
