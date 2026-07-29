from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from goga.connect.connect import (
    AGENT_DIRS,
    AGENTS_WITH_COMMANDS,
)

# --- Contract tests: qwen is a declared supported agent ---


class TestQwenContract:
    def test_agent_dirs_contains_qwen(self) -> None:
        assert AGENT_DIRS["qwen"] == ".qwen"

    def test_agents_with_commands_contains_qwen(self) -> None:
        assert "qwen" in AGENTS_WITH_COMMANDS


# --- Logic tests: qwen installation, idempotency, rejection ---


class TestConnectQwenLogic:
    def test_connect_installs_qwen_symlinks(self, tmp_path: Path, agent_resources: Path, connect_ctx) -> None:
        home = tmp_path / "home"
        home.mkdir()

        result = connect_ctx(agent_resources, home, ["qwen"], force_overwrite=False)

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

    def test_connect_qwen_idempotent_reconnect(self, tmp_path: Path, agent_resources: Path, connect_ctx) -> None:
        home = tmp_path / "home"
        home.mkdir()

        assert connect_ctx(agent_resources, home, ["qwen"]) == 0
        assert connect_ctx(agent_resources, home, ["qwen"]) == 0

        skill_link = home / ".qwen" / "skills" / "goga-cell"
        assert skill_link.is_symlink() is True
        assert skill_link.resolve() == (home / ".goga" / "skills" / "goga-cell")

        registry = yaml.safe_load((home / ".goga" / "connect.yml").read_text())
        qwen_keys = [k for k in registry["agents"] if k == "qwen"]
        assert len(qwen_keys) == 1

    def test_connect_rejects_unknown_agent(
        self,
        tmp_path: Path,
        agent_resources: Path,
        connect_ctx,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()

        result = connect_ctx(agent_resources, home, ["foo"], force_overwrite=False)

        assert result == 1
        captured = capsys.readouterr()
        assert "unsupported agent 'foo'" in captured.err
        # validation fails before any central install, so no ~/.goga/ is created
        assert not (home / ".goga").exists()
        assert not (home / ".goga" / "skills").exists()
