"""Shared fixtures of the config zone tests — the on-disk project boundary.

The suites under ``tests/config/`` drive the real loader against a real
``.goga/config.yml`` laid out under ``tmp_path``: the ``goga_project`` fixture
points a run at one such project root (the CWD of the test), and the
``_write_goga_yml`` helper writes its configuration file.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def goga_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run inside a fresh empty project root — ``tmp_path`` chdir'ed into."""
    monkeypatch.chdir(tmp_path)

    return tmp_path


def _write_goga_yml(path: Path, content: str) -> None:
    goga_dir = path / ".goga"
    goga_dir.mkdir(exist_ok=True)
    (goga_dir / "config.yml").write_text(content)
