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


# --- Contract tests: qwen is a declared supported agent ---


class TestQwenContract:
    def test_agent_dirs_contains_qwen(self) -> None:
        assert AGENT_DIRS["qwen"] == ".qwen"

    def test_agents_with_commands_contains_qwen(self) -> None:
        assert "qwen" in AGENTS_WITH_COMMANDS


# --- Logic tests: qwen installation, idempotency, rejection ---


class TestConnectQwenLogic:
    def test_connect_installs_qwen_symlinks(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()

        result = _connect_ctx(tmp_path, source, home, ["qwen"], force_overwrite=False)

        assert result == 0

        # qwen resolves to ~/.qwen/ and receives the skills symlink.
        skill_link = home / ".qwen" / "skills" / "goga-cell"
        assert skill_link.is_symlink()
        assert skill_link.resolve() == (home / ".goga" / "skills" / "goga-cell")

        # Every goga-* skill is symlinked (the multi-entry loop, not just the first).
        review_link = home / ".qwen" / "skills" / "goga-review"
        assert review_link.is_symlink()
        assert review_link.resolve() == (home / ".goga" / "skills" / "goga-review")

        # qwen is in AGENTS_WITH_COMMANDS, so it also receives the commands symlink
        # (commands/goga nested folder, like claude).
        cmd_link = home / ".qwen" / "commands" / "goga"
        assert cmd_link.is_symlink()
        assert cmd_link.resolve() == (home / ".goga" / "commands")

        registry = yaml.safe_load((home / ".goga" / "connect.yml").read_text())
        assert registry["agents"]["qwen"] == {"force_overwrite": False}

    def test_connect_qwen_idempotent_reconnect(self, tmp_path: Path) -> None:
        _create_agent_resources(tmp_path)
        source = tmp_path / "goga" / "assets"
        home = tmp_path / "home"
        home.mkdir()

        assert _connect_ctx(tmp_path, source, home, ["qwen"]) == 0
        assert _connect_ctx(tmp_path, source, home, ["qwen"]) == 0

        skill_link = home / ".qwen" / "skills" / "goga-cell"
        assert skill_link.is_symlink() is True
        assert skill_link.resolve() == (home / ".goga" / "skills" / "goga-cell")

        registry = yaml.safe_load((home / ".goga" / "connect.yml").read_text())
        qwen_keys = [k for k in registry["agents"] if k == "qwen"]
        assert len(qwen_keys) == 1

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
        assert not (home / ".goga").exists()
        assert not (home / ".goga" / "skills").exists()
