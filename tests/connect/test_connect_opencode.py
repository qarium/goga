from __future__ import annotations

import importlib
from pathlib import Path
from unittest import mock

import pytest
import yaml
from goga.connect.connect import (
    AGENT_DIRS,
    AGENTS_WITH_COMMANDS,
    connect,
)

_install_mod = importlib.import_module("goga.connect.connect")


def _create_agent_resources(target: Path) -> Path:
    """Create a minimal goga/assets/ source tree (goga-* prefixed skills)."""
    source = target / "goga" / "assets"
    (source / "commands").mkdir(parents=True)
    (source / "commands" / "build.md").write_text("# build command")
    (source / "commands" / "install.md").write_text("# install command")
    (source / "skills" / "goga-cell").mkdir(parents=True)
    (source / "skills" / "goga-cell" / "SKILL.md").write_text("# cell skill")
    (source / "skills" / "goga-review").mkdir(parents=True)
    (source / "skills" / "goga-review" / "SKILL.md").write_text("# review skill")
    return source


def _mock_requests_response(content: bytes = b"# DSL spec") -> mock.MagicMock:
    mock_response = mock.MagicMock()
    mock_response.content = content
    mock_response.status_code = 200
    mock_response.raise_for_status = mock.MagicMock()
    return mock_response


def _connect_ctx(tmp_path: Path, source: Path, home: Path, agents: list[str], **kwargs):
    """Run connect() with HOME isolated to a tmp dir (no real ~/.goga touched)."""
    with (
        mock.patch.object(_install_mod, "_get_source_dir", return_value=source),
        mock.patch.object(_install_mod.Path, "home", return_value=home),
        mock.patch.object(_install_mod.requests, "get", return_value=_mock_requests_response()),
    ):
        return connect(agents=agents, **kwargs)


# --- Contract tests: opencode is a declared supported agent ---


class TestOpencodeContract:
    def test_agent_dirs_contains_opencode(self) -> None:
        assert AGENT_DIRS["opencode"] == ".config/opencode"

    def test_agents_with_commands_contains_opencode(self) -> None:
        assert "opencode" in AGENTS_WITH_COMMANDS


# --- Logic tests: opencode installation, idempotency, rejection ---


class TestConnectOpencodeLogic:
    def test_connect_installs_opencode_symlinks(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()

        result = _connect_ctx(tmp_path, source, home, ["opencode"], force_overwrite=False)

        assert result == 0

        # opencode resolves to ~/.config/opencode/ and receives the skills symlink.
        skill_link = home / ".config" / "opencode" / "skills" / "goga-cell"
        assert skill_link.is_symlink()
        assert skill_link.resolve() == (home / ".goga" / "skills" / "goga-cell")

        # opencode is in AGENTS_WITH_COMMANDS, so it also receives the commands symlink.
        cmd_link = home / ".config" / "opencode" / "commands" / "goga"
        assert cmd_link.is_symlink()
        assert cmd_link.resolve() == (home / ".goga" / "commands")

        registry = yaml.safe_load((home / ".goga" / "connect.yml").read_text())
        assert registry["agents"]["opencode"] == {"force_overwrite": False}

    def test_connect_opencode_idempotent_reconnect(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()

        assert _connect_ctx(tmp_path, source, home, ["opencode"]) == 0
        assert _connect_ctx(tmp_path, source, home, ["opencode"]) == 0

        skill_link = home / ".config" / "opencode" / "skills" / "goga-cell"
        assert skill_link.is_symlink() is True
        assert skill_link.resolve() == (home / ".goga" / "skills" / "goga-cell")

        registry = yaml.safe_load((home / ".goga" / "connect.yml").read_text())
        opencode_keys = [k for k in registry["agents"] if k == "opencode"]
        assert len(opencode_keys) == 1

    def test_connect_rejects_unknown_agent(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()

        result = _connect_ctx(tmp_path, source, home, ["foo"], force_overwrite=False)

        assert result == 1
        captured = capsys.readouterr()
        assert "unsupported agent 'foo'" in captured.err
        # validation fails before any central install, so no ~/.goga/ is created
        assert not (home / ".goga" / "skills").exists()
