"""Contract and logic tests for the four pure target/branch routines declared
in ``goga/commands/runtime/CODEMANIFEST`` and colocated in
``goga/commands/runtime/targets.py``:

- ``resolve_effective_branch(branch: str | None = None) -> str``
- ``resolve_build_target_dir(branch_segment: str) -> Path``
- ``sanitize_pipeline_name(name: str) -> str``
- ``resolve_pipeline_target_dir(pipeline_name: str, branch_segment: str) -> Path``

All four are thin, pure delegations over the shared runtime formula
(``goga.runtime``) — no second path scheme — so the tests monkeypatch
cwd/home and mock the git subprocess only where the derived branch form
consults it; the pure logic stays mock-free.
"""

from __future__ import annotations

import inspect
import subprocess
import typing
from pathlib import Path
from unittest import mock

import pytest
from goga.commands import runtime as runtime_facade
from goga.commands.runtime import (
    resolve_build_target_dir,
    resolve_effective_branch,
    resolve_pipeline_target_dir,
    sanitize_pipeline_name,
)
from goga.runtime import resolve_runtime_dir


def _git_completed(stdout: str) -> subprocess.CompletedProcess:
    """Build the ``subprocess.run`` return the git boundary mock delivers."""
    return subprocess.CompletedProcess(
        ["git", "branch", "--show-current"],
        0,
        stdout=stdout,
        stderr="",
    )


# --- Contract tests ---


class TestTargetsContract:
    def test_all_four_importable_from_facade(self) -> None:
        """The four routines are importable from the goga.commands.runtime facade."""
        assert callable(resolve_effective_branch)
        assert callable(resolve_build_target_dir)
        assert callable(sanitize_pipeline_name)
        assert callable(resolve_pipeline_target_dir)

    def test_facade_all_lists_exactly_the_landed_names(self) -> None:
        """__all__ exposes exactly the landed names — the facade grows as entities land."""
        assert runtime_facade.__all__ == [
            "package_runtime_archive",
            "resolve_archive_destination",
            "resolve_build_target_dir",
            "resolve_effective_branch",
            "resolve_pipeline_target_dir",
            "runtime",
            "sanitize_pipeline_name",
        ]

    def test_resolve_effective_branch_signature(self) -> None:
        """resolve_effective_branch(branch: str | None = None) -> str."""
        sig = inspect.signature(resolve_effective_branch)
        assert list(sig.parameters) == ["branch"]
        assert sig.parameters["branch"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert sig.parameters["branch"].default is None
        hints = typing.get_type_hints(resolve_effective_branch)
        assert hints["return"] is str
        assert hints["branch"] == typing.Optional[str]

    def test_resolve_build_target_dir_signature(self) -> None:
        """resolve_build_target_dir(branch_segment: str) -> Path."""
        sig = inspect.signature(resolve_build_target_dir)
        assert list(sig.parameters) == ["branch_segment"]
        assert sig.parameters["branch_segment"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        hints = typing.get_type_hints(resolve_build_target_dir)
        assert hints["return"] is Path
        assert hints["branch_segment"] is str

    def test_sanitize_pipeline_name_signature(self) -> None:
        """sanitize_pipeline_name(name: str) -> str."""
        sig = inspect.signature(sanitize_pipeline_name)
        assert list(sig.parameters) == ["name"]
        assert sig.parameters["name"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        hints = typing.get_type_hints(sanitize_pipeline_name)
        assert hints["return"] is str
        assert hints["name"] is str

    def test_resolve_pipeline_target_dir_signature(self) -> None:
        """resolve_pipeline_target_dir(pipeline_name: str, branch_segment: str) -> Path."""
        sig = inspect.signature(resolve_pipeline_target_dir)
        assert list(sig.parameters) == ["pipeline_name", "branch_segment"]
        for name in sig.parameters:
            assert sig.parameters[name].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        hints = typing.get_type_hints(resolve_pipeline_target_dir)
        assert hints["return"] is Path
        assert hints["pipeline_name"] is str
        assert hints["branch_segment"] is str


# --- Logic tests ---


class TestResolveEffectiveBranchLogic:
    @pytest.mark.parametrize(
        ("branch", "expected_segment"),
        [
            (None, "derived-branch"),
            ("", "derived-branch"),
            ("a/b", "a-b"),
            ("a-b", "a-b"),
        ],
    )
    def test_resolve_effective_branch_contract_matrix(self, branch: str | None, expected_segment: str) -> None:
        """None/'' derive the segment from git; a non-empty value is slugified.

        The explicit rows never consult git — the mock is armed for every row
        anyway, so a stray git call in the explicit forms would surface as a
        wrong segment instead of a live subprocess.
        """
        with mock.patch.object(subprocess, "run", return_value=_git_completed("derived-branch\n")):
            assert resolve_effective_branch(branch) == expected_segment


class TestSanitizePipelineNameLogic:
    def test_sanitize_pipeline_name_literal_replacement(self) -> None:
        """Literal one-to-one colon replacement — no collapsing, no trimming."""
        assert sanitize_pipeline_name("py:bug:gy:") == "py-bug-gy-"
        assert sanitize_pipeline_name("plain") == "plain"
        assert sanitize_pipeline_name("") == ""


class TestRunTimeParity:
    def test_resolve_build_target_dir_matches_the_build_call_site(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """resolve_build_target_dir(segment) == resolve_runtime_dir('builds') for that branch.

        The build command composes its bind-mount directory via
        ``resolve_runtime_dir("builds")`` (``build.py``) — the same purpose
        and formula, so the resolved path is the directory the run uses.
        """
        monkeypatch.chdir(tmp_path)

        assert resolve_build_target_dir("feature-x") == resolve_runtime_dir("builds", branch="feature-x")

    def test_resolve_pipeline_target_dir_matches_the_run_composition(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """resolve_pipeline_target_dir(name, segment) == the run's exact composition.

        The pipeline run composes
        ``resolve_runtime_dir("pipelines", pipeline_name.replace(":", "-"))``
        (``run_pipeline_container.py``) — same purpose, same sanitization,
        same formula for that name/branch.
        """
        monkeypatch.chdir(tmp_path)

        result = resolve_pipeline_target_dir("pybuggy:api", "main")

        assert result == resolve_runtime_dir("pipelines", "pybuggy-api", branch="main")


class TestTargetPurity:
    def test_target_resolvers_never_create_the_directory(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Neither resolver creates anything on disk — the routines never mkdir."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        build_dir = resolve_build_target_dir("feature-x")
        pipeline_dir = resolve_pipeline_target_dir("py:bug", "feature-x")

        assert not build_dir.exists()
        assert not pipeline_dir.exists()
