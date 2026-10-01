"""Shared fixtures and helpers of the build cell tests — the platform boundary.

Re-exports the two boundary fixtures of the hooks platform tests
(``pin_package_environment`` / ``install_tool_package``) so the orchestration
suites of ``tests/build`` pin the same two outside-world points — the
``packages_distributions`` read and the ``sys.modules`` entry of a
``goga_tool_*`` package — with the platform code under test running for real.
The git-status fixture pins the manifest pre-check's subprocess boundary the
same way: the porcelain stdout becomes the single test input. The vendored
sources helper is the one tests/build-wide pin of the ralphex defaults
boundary the orchestration suites share.
"""

from __future__ import annotations

import importlib
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest

from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401

# goga.build.build is shadowed in the package __init__ by the build function,
# so a string-based patch path walking through it fails on Python 3.10.
# Resolve the real module through the import system and patch its
# attributes directly.
build_module = importlib.import_module("goga.build.build")

# The five reviewer roles of the vendored ralphex agent definitions.
VENDORED_ROLES = ("quality", "implementation", "testing", "simplification", "documentation")


@pytest.fixture
def fake_git_status(monkeypatch: pytest.MonkeyPatch):
    """Factory: pin the manifest pre-check's git boundary at ``build.py``'s import point.

    ``porcelain`` is the canned ``git status --porcelain -uall`` stdout the
    pre-check parses; a non-zero ``returncode`` is the not-a-repository
    refusal. The git subprocess itself never runs.
    """

    def _fake(porcelain: str, *, returncode: int = 0) -> None:
        def _run(cmd, *args: object, **kwargs: object) -> subprocess.CompletedProcess:
            return subprocess.CompletedProcess(cmd, returncode, stdout=porcelain, stderr="")

        monkeypatch.setattr(build_module.subprocess, "run", _run)

    return _fake


@contextmanager
def mock_vendored_sources(
    tmp_path: Path,
    *,
    review_first: str = "# first review prompt\n",
    review_second: str = "# second review prompt\n",
) -> Iterator[tuple[Path, Path]]:
    """Point the vendored ralphex defaults at synthetic tmp sources (external boundary).

    ``build()`` fully rewrites ``.ralphex/prompts|agents/`` from the vendored
    defaults; the real assets are a maintainers' artifact outside these
    tests. A suite needing specific prompt bodies (the role-filter counter
    fragments) passes them through the keyword arguments.

    Args:
        tmp_path: The per-test directory the synthetic sources live under.
        review_first: The content of the vendored first review prompt.
        review_second: The content of the vendored second review prompt.

    Yields:
        The prompts and the agents source directory.
    """
    from goga.build import ralphex_runtime

    prompts_dir = tmp_path / "vendored-prompts"
    agents_dir = tmp_path / "vendored-agents"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    agents_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "task.txt").write_text("# task prompt\n")
    (prompts_dir / "codex.txt").write_text("# codex review prompt\n")
    (prompts_dir / "review_first.txt").write_text(review_first)
    (prompts_dir / "review_second.txt").write_text(review_second)

    for role in VENDORED_ROLES:
        (agents_dir / f"{role}.txt").write_text(f"# {role} agent definition\n")

    with (
        mock.patch.object(ralphex_runtime, "_VENDORED_PROMPTS", prompts_dir),
        mock.patch.object(ralphex_runtime, "_VENDORED_AGENTS", agents_dir),
    ):
        yield prompts_dir, agents_dir
