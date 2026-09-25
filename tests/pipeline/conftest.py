"""Shared fixtures of the ``tests/pipeline`` package."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """chdir into tmp_path — the workflows root resolves to ``<tmp>/.goga/workflows``."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
