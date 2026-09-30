"""Shared fixtures of the build cell tests — the platform boundary.

Re-exports the two boundary fixtures of the hooks platform tests
(``pin_package_environment`` / ``install_tool_package``) so the orchestration
suites of ``tests/build`` pin the same two outside-world points — the
``packages_distributions`` read and the ``sys.modules`` entry of a
``goga_tool_*`` package — with the platform code under test running for real.
The git-status fixture pins the manifest pre-check's subprocess boundary the
same way: the porcelain stdout becomes the single test input.
"""

from __future__ import annotations

import subprocess

import pytest

from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401


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

        monkeypatch.setattr(subprocess, "run", _run)

    return _fake
