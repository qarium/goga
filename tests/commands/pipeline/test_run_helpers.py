"""Contract and logic tests for the four intra-cell routines declared in
``goga/commands/pipeline/CODEMANIFEST`` and colocated with
``run_pipeline_container`` in ``run_pipeline_container.py``:

- ``normalize_project_path(project_path) -> str``
- ``resolve_git_branch() -> str``
- ``resolve_afm_runtime_dir(pipeline_name) -> Path``
- ``clean_afm_runtime_dir(afm_runtime_dir) -> None``

These are pure host-side helpers used by run mode to compute and manage the
persistent afm state directory. They have no docker dependency, so the tests
exercise them directly with monkeypatched git/cwd/home.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from goga.commands.pipeline.run_pipeline_container import (
    clean_afm_runtime_dir,
    normalize_project_path,
    resolve_afm_runtime_dir,
    resolve_git_branch,
)

# Resolve the real submodule via sys.modules (the package __init__ binds the
# function name `run_pipeline_container`, which would shadow string-based
# mock.patch paths walking through the package on Python 3.10).
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]


# --- Contract tests ---


class TestRunHelpersContract:
    def test_all_four_importable_from_run_pipeline_container(self) -> None:
        """The four routines are importable from the declared location."""
        assert callable(normalize_project_path)
        assert callable(resolve_git_branch)
        assert callable(resolve_afm_runtime_dir)
        assert callable(clean_afm_runtime_dir)

    def test_normalize_project_path_returns_str_no_slashes(self) -> None:
        """normalize_project_path returns a str with no forward slashes."""
        result = normalize_project_path(Path("/Users/wb/myproj"))
        assert isinstance(result, str)
        assert "/" not in result

    def test_resolve_git_branch_returns_str(self) -> None:
        """resolve_git_branch returns a str (never raises)."""
        assert isinstance(resolve_git_branch(), str)

    def test_resolve_afm_runtime_dir_returns_absolute_path(self) -> None:
        """resolve_afm_runtime_dir returns an absolute Path."""
        result = resolve_afm_runtime_dir("deploy")
        assert isinstance(result, Path)
        assert result.is_absolute()

    def test_clean_afm_runtime_dir_returns_none(self, tmp_path: Path) -> None:
        """clean_afm_runtime_dir returns None (and creates the directory)."""
        assert clean_afm_runtime_dir(tmp_path / "rt") is None
        assert (tmp_path / "rt").exists()


# --- Logic tests (positive) ---


class TestNormalizeProjectPathLogic:
    def test_normalize_project_path_typical(self) -> None:
        """Leading slash removed; every other slash → hyphen (1:1, no collapsing)."""
        result = normalize_project_path(Path("/Users/wb/IdeaProjects/my/project"))
        assert result == "Users-wb-IdeaProjects-my-project"
        assert "/" not in result


class TestResolveGitBranchLogic:
    def test_resolve_git_branch_ok(self) -> None:
        """When git succeeds with a non-empty answer, return it stripped."""
        completed = subprocess.CompletedProcess(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            0,
            stdout="docker-runtime-finishing\n",
            stderr="",
        )
        with mock.patch.object(subprocess, "run", return_value=completed):
            assert resolve_git_branch() == "docker-runtime-finishing"


class TestResolveAfmRuntimeDirLogic:
    def test_resolve_afm_runtime_dir_composition(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """runtime_dir = ~/.goga/runtime/pipelines/<normalized>/<branch>/<name>."""
        monkeypatch.setattr(Path, "cwd", lambda: Path("/Users/wb/myproj"))
        monkeypatch.setattr(Path, "home", lambda: Path("/Users/wb"))
        monkeypatch.setattr(_rpc_mod, "resolve_git_branch", lambda: "feature-x")

        result = resolve_afm_runtime_dir("deploy")

        assert result == Path(
            "/Users/wb/.goga/runtime/pipelines/Users-wb-myproj/feature-x/deploy"
        )
        # Pure: does not create the directory.
        assert not result.exists()


class TestCleanAfmRuntimeDirLogic:
    def test_clean_afm_runtime_dir_idempotent(self, tmp_path: Path) -> None:
        """Wiping a populated dir twice leaves it empty without raising."""
        runtime_dir = tmp_path / "rt"
        nested = runtime_dir / "deep" / "nested"
        nested.mkdir(parents=True)
        (nested / "state.txt").write_text("stale")

        clean_afm_runtime_dir(runtime_dir)
        clean_afm_runtime_dir(runtime_dir)  # second call must not raise

        assert runtime_dir.exists()
        assert not any(runtime_dir.iterdir())


# --- Logic tests (negative) ---


class TestResolveGitBranchNegative:
    def test_resolve_git_branch_git_missing(self) -> None:
        """FileNotFoundError (git not on PATH) maps to the 'default' fallback."""
        with mock.patch.object(subprocess, "run", side_effect=FileNotFoundError):
            assert resolve_git_branch() == "default"

    def test_resolve_git_branch_permission_error_falls_back(self) -> None:
        """PermissionError maps to the 'default' fallback."""
        with mock.patch.object(subprocess, "run", side_effect=PermissionError):
            assert resolve_git_branch() == "default"


# --- Logic tests (edge) ---


class TestNormalizeProjectPathEdge:
    def test_normalize_project_path_root_only(self) -> None:
        """A bare root path normalizes to the empty string."""
        assert normalize_project_path(Path("/")) == ""

    def test_normalize_project_path_posix_only_no_backslash_handling(self) -> None:
        """Backslashes are not touched — only forward slashes become hyphens."""
        # Posix-only: a backslash is a literal path character and is left as-is.
        result = normalize_project_path(Path("/Users/wb/my\\proj"))
        assert result == "Users-wb-my\\proj"
        assert "\\" in result
        assert "/" not in result


class TestResolveGitBranchEdge:
    def test_resolve_git_branch_detached_head(self) -> None:
        """A detached HEAD (git prints 'HEAD') is returned as-is, non-empty."""
        completed = subprocess.CompletedProcess(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            0,
            stdout="HEAD\n",
            stderr="",
        )
        with mock.patch.object(subprocess, "run", return_value=completed):
            assert resolve_git_branch() == "HEAD"
