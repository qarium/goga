"""Contract and logic tests for the three pure routines declared in
``goga/runtime/CODEMANIFEST`` and colocated in ``goga/runtime/paths.py``:

- ``normalize_project_path(project_path: Path) -> str``
- ``resolve_git_branch() -> str``
- ``resolve_runtime_dir(purpose: str, *suffix_parts: str) -> Path``

These are pure host-side helpers with no docker dependency, so the tests exercise
them directly with monkeypatched cwd/home and a mocked ``subprocess.run``.
"""

from __future__ import annotations

import inspect
import subprocess
import typing
from pathlib import Path
from unittest import mock

import pytest
from goga.runtime import (
    normalize_project_path,
    resolve_git_branch,
    resolve_runtime_dir,
)

# --- Contract tests ---


class TestPathsContract:
    def test_all_three_importable_from_facade(self) -> None:
        """The three routines are importable from the goga.runtime facade."""
        assert callable(normalize_project_path)
        assert callable(resolve_git_branch)
        assert callable(resolve_runtime_dir)

    def test_normalize_project_path_signature(self) -> None:
        """normalize_project_path(project_path: Path) -> str."""
        sig = inspect.signature(normalize_project_path)
        assert list(sig.parameters) == ["project_path"]
        # paths.py uses `from __future__ import annotations`, so resolve the
        # stringified annotations to their actual types via get_type_hints.
        hints = typing.get_type_hints(normalize_project_path)
        assert hints["return"] is str

    def test_resolve_git_branch_signature(self) -> None:
        """resolve_git_branch() -> str."""
        sig = inspect.signature(resolve_git_branch)
        assert list(sig.parameters) == []
        hints = typing.get_type_hints(resolve_git_branch)
        assert hints["return"] is str

    def test_resolve_runtime_dir_signature(self) -> None:
        """resolve_runtime_dir(purpose: str, *suffix_parts: str) -> Path."""
        sig = inspect.signature(resolve_runtime_dir)
        params = list(sig.parameters)
        assert params == ["purpose", "suffix_parts"]
        assert sig.parameters["purpose"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert sig.parameters["suffix_parts"].kind == inspect.Parameter.VAR_POSITIONAL
        hints = typing.get_type_hints(resolve_runtime_dir)
        assert hints["return"] is Path

    def test_normalize_project_path_returns_str(self) -> None:
        """normalize_project_path returns a str."""
        assert isinstance(normalize_project_path(Path("/x/y")), str)

    def test_resolve_git_branch_returns_str(self) -> None:
        """resolve_git_branch returns a str (never raises)."""
        assert isinstance(resolve_git_branch(), str)

    def test_resolve_runtime_dir_returns_path(self) -> None:
        """resolve_runtime_dir returns a pathlib.Path."""
        assert isinstance(resolve_runtime_dir("builds"), Path)


# --- Logic tests (positive) ---


class TestNormalizeProjectPathLogic:
    def test_normalize_project_path_strips_leading_slash_and_replaces_remaining(self) -> None:
        """Leading slash removed; every other slash -> hyphen (1:1, no collapsing)."""
        result = normalize_project_path(Path("/Users/wb/IdeaProjects/my/project"))
        assert result == "Users-wb-IdeaProjects-my-project"
        assert "/" not in result


class TestResolveGitBranchLogic:
    def test_resolve_git_branch_returns_branch_when_git_succeeds(self) -> None:
        """When git succeeds with a non-empty answer, return it stripped."""
        completed = subprocess.CompletedProcess(
            ["git", "branch", "--show-current"],
            0,
            stdout="docker-runtime-finishing\n",
            stderr="",
        )
        with mock.patch.object(subprocess, "run", return_value=completed):
            assert resolve_git_branch() == "docker-runtime-finishing"


class TestResolveRuntimeDirLogic:
    def test_resolve_runtime_dir_composes_builds_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """runtime_dir = ~/.goga/runtime/builds/<normalized>/<branch> (branch slugified)."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: Path("/Users/tester"))
        completed = subprocess.CompletedProcess(
            ["git", "branch", "--show-current"],
            0,
            stdout="feature/x\n",
            stderr="",
        )

        with mock.patch.object(subprocess, "run", return_value=completed):
            result = resolve_runtime_dir("builds")

        cwd_segment = str(Path.cwd()).lstrip("/").replace("/", "-")
        expected = Path("/Users/tester/.goga/runtime/builds") / cwd_segment / "feature-x"
        assert result == expected
        # Pure: does not create the directory.
        assert not result.exists()

    def test_resolve_runtime_dir_composes_pipeline_path_with_suffix(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """runtime_dir = ~/.goga/runtime/pipelines/<normalized>/main/<name>."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: Path("/Users/tester"))
        completed = subprocess.CompletedProcess(
            ["git", "branch", "--show-current"],
            0,
            stdout="main\n",
            stderr="",
        )

        with mock.patch.object(subprocess, "run", return_value=completed):
            result = resolve_runtime_dir("pipelines", "my-pipe")

        cwd_segment = str(Path.cwd()).lstrip("/").replace("/", "-")
        expected = Path("/Users/tester/.goga/runtime/pipelines") / cwd_segment / "main" / "my-pipe"
        assert result == expected

    def test_resolve_runtime_dir_appends_multiple_suffix_parts_in_order(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Multiple suffix parts are joined in order after the branch segment."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: Path("/Users/tester"))
        completed = subprocess.CompletedProcess(
            ["git", "branch", "--show-current"],
            0,
            stdout="main\n",
            stderr="",
        )

        with mock.patch.object(subprocess, "run", return_value=completed):
            result = resolve_runtime_dir("purpose", "a", "b")

        cwd_segment = str(Path.cwd()).lstrip("/").replace("/", "-")
        expected = Path("/Users/tester/.goga/runtime/purpose") / cwd_segment / "main" / "a" / "b"
        assert result == expected
        assert result.parts[-2:] == ("a", "b")


# --- Logic tests (negative) ---


class TestResolveGitBranchNegative:
    def test_resolve_git_branch_returns_default_when_not_a_repo(self) -> None:
        """A non-repo directory (git exits non-zero) maps to the 'default' fallback."""
        completed = subprocess.CompletedProcess(
            ["git", "branch", "--show-current"],
            128,
            stdout="",
            stderr="fatal: not a git repository",
        )
        with mock.patch.object(subprocess, "run", return_value=completed):
            assert resolve_git_branch() == "default"

    def test_resolve_git_branch_returns_default_when_git_missing(self) -> None:
        """FileNotFoundError (git not on PATH) maps to the 'default' fallback."""
        with mock.patch.object(subprocess, "run", side_effect=FileNotFoundError):
            assert resolve_git_branch() == "default"

    def test_resolve_git_branch_propagates_unexpected_errors(self) -> None:
        """Only FileNotFoundError is caught — other errors propagate, not 'default'.

        The contract catches ``FileNotFoundError`` specifically (git binary
        missing) so genuinely unexpected failures surface during development
        instead of being silently swallowed into the ``"default"`` fallback.
        """
        with (
            mock.patch.object(subprocess, "run", side_effect=PermissionError("denied")),
            pytest.raises(PermissionError),
        ):
            resolve_git_branch()


# --- Logic tests (edge) ---


class TestNormalizeProjectPathEdge:
    def test_normalize_project_path_applies_literal_transform_only(self) -> None:
        """The function adds no stripping/collapsing of its own (literal transform).

        ``pathlib.Path`` normalizes a trailing slash away during construction
        (``str(Path("/foo/bar/")) == "/foo/bar"``), so a trailing hyphen can never
        arise from a Path input. This guards the contract that the function does
        exactly ``lstrip("/")`` + ``replace("/", "-")`` and nothing more — it does
        not introduce trailing-hyphen stripping or consecutive-hyphen collapsing.
        """
        assert normalize_project_path(Path("/foo/bar/")) == "foo-bar"
        assert normalize_project_path(Path("/foo//bar")) == "foo-bar"

    def test_normalize_project_path_root_only(self) -> None:
        """A bare root path normalizes to the empty string."""
        assert normalize_project_path(Path("/")) == ""

    def test_normalize_project_path_preserves_backslashes(self) -> None:
        """Backslashes are not touched — only forward slashes become hyphens."""
        result = normalize_project_path(Path("/Users/wb/my\\proj"))
        assert result == "Users-wb-my\\proj"
        assert "\\" in result
        assert "/" not in result


class TestResolveGitBranchEdge:
    def test_resolve_git_branch_returns_default_in_detached_head(self) -> None:
        """Detached HEAD (empty stdout from --show-current) -> 'default'.

        Regression guard for the detached-HEAD defect: the old
        ``git rev-parse --abbrev-ref HEAD`` returned the literal ``"HEAD"`` with
        exit 0 in detached state and never reached the fallback; ``git branch
        --show-current`` prints an empty string (exit 0) so the non-empty-answer
        check correctly falls through to ``"default"``.
        """
        completed = subprocess.CompletedProcess(
            ["git", "branch", "--show-current"],
            0,
            stdout="",
            stderr="",
        )
        with mock.patch.object(subprocess, "run", return_value=completed):
            assert resolve_git_branch() == "default"

    def test_resolve_git_branch_slugifies_forward_slashes(self) -> None:
        """Forward slashes in the branch name are replaced with hyphens."""
        completed = subprocess.CompletedProcess(
            ["git", "branch", "--show-current"],
            0,
            stdout="feature/ralphex-runtime-isolation\n",
            stderr="",
        )
        with mock.patch.object(subprocess, "run", return_value=completed):
            assert resolve_git_branch() == "feature-ralphex-runtime-isolation"

    def test_resolve_git_branch_preserves_branch_without_slashes(self) -> None:
        """A branch name with no slashes is returned unchanged (no-op slugify)."""
        completed = subprocess.CompletedProcess(
            ["git", "branch", "--show-current"],
            0,
            stdout="main\n",
            stderr="",
        )
        with mock.patch.object(subprocess, "run", return_value=completed):
            assert resolve_git_branch() == "main"

    def test_resolve_git_branch_strips_whitespace(self) -> None:
        """The branch answer is stripped before slugification."""
        completed = subprocess.CompletedProcess(
            ["git", "branch", "--show-current"],
            0,
            stdout="  release/2.0  \n",
            stderr="",
        )
        with mock.patch.object(subprocess, "run", return_value=completed):
            assert resolve_git_branch() == "release-2.0"
