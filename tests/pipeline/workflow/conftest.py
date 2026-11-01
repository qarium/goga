"""Shared fixtures of the ``tests.pipeline.workflow`` package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from jinja2 import Environment


@pytest.fixture
def project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """chdir into a fake project carrying the profile and workflow roots.

    The contributor-profile feature resolves profiles from
    ``<cwd>/.goga/profiles`` and workflows from ``<cwd>/.goga/workflows``;
    both directories exist (empty) inside the isolated project so every
    scenario of the package starts from the same project shape and writes
    nothing outside the tmp tree. Tests seed files into the returned root.

    Args:
        tmp_path: the isolated test directory holding the fake project.
        monkeypatch: the pytest patcher restoring the original CWD.

    Returns:
        The project root the process CWD was moved into.
    """
    root = tmp_path / "project"
    (root / ".goga" / "profiles").mkdir(parents=True)
    (root / ".goga" / "workflows").mkdir(parents=True)
    monkeypatch.chdir(root)

    return root


@pytest.fixture
def home_bundle() -> dict[str, dict[str, Any]]:
    """Sample personal-bundle mapping — the ``load_home_profiles`` shape.

    One profile under one name: the whole mapping under ``mixa`` doubles as
    the Jinja rendering context (a nested ``worker`` mapping), matching the
    fixture data the plan's scenarios build on.
    """
    return {"mixa": {"worker": {"agent": "codex", "model": "sonnet"}}}


@pytest.fixture
def render_env() -> Environment:
    """The fixed jinja2 rendering environment per the ``jinja2`` practice.

    The four flags are an accepted ADR decision — the rendering contract the
    ``render_workflow`` implementation and its tests both build on.
    """
    return Environment(
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )
