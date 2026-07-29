from __future__ import annotations

import importlib
from pathlib import Path
from unittest import mock

import pytest
from goga.connect.connect import connect

_install_mod = importlib.import_module("goga.connect.connect")


@pytest.fixture
def agent_resources(tmp_path: Path) -> Path:
    """Create a minimal goga/assets/ source tree (goga-* prefixed skills)."""
    source = tmp_path / "goga" / "assets"
    (source / "commands").mkdir(parents=True)
    (source / "commands" / "build.md").write_text("# build command")
    (source / "commands" / "install.md").write_text("# install command")
    (source / "skills" / "goga-cell").mkdir(parents=True)
    (source / "skills" / "goga-cell" / "SKILL.md").write_text("# cell skill")
    (source / "skills" / "goga-review").mkdir(parents=True)
    (source / "skills" / "goga-review" / "SKILL.md").write_text("# review skill")
    return source


@pytest.fixture
def mock_requests_response():
    """Build a mock requests.Response (status 200, raise_for_status no-op).

    Returns a factory: ``mock_requests_response(content=b"# DSL spec")``.
    """

    def _make(content: bytes = b"# DSL spec") -> mock.MagicMock:
        mock_response = mock.MagicMock()
        mock_response.content = content
        mock_response.status_code = 200
        mock_response.raise_for_status = mock.MagicMock()
        return mock_response

    return _make


@pytest.fixture
def connect_ctx(mock_requests_response):
    """Run connect() with HOME isolated to a tmp dir (no real ~/.goga touched).

    Returns a callable: ``connect_ctx(source, home, agents, **kwargs) -> int``.
    """

    def _connect(source: Path, home: Path, agents: list[str], **kwargs) -> int:
        with (
            mock.patch.object(_install_mod, "_get_source_dir", return_value=source),
            mock.patch.object(_install_mod.Path, "home", return_value=home),
            mock.patch.object(_install_mod.requests, "get", return_value=mock_requests_response()),
        ):
            return connect(agents=agents, **kwargs)

    return _connect
