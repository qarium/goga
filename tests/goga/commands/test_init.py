from __future__ import annotations

from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner

from goga.cli import app
from goga.commands import init


class TestFacadeAvailability:
    """Contract tests -- verify init is properly exposed as a click Command."""

    def test_init_importable(self) -> None:
        from goga.commands import init as init_cmd

        assert init_cmd is not None

    def test_init_is_click_command(self) -> None:
        assert isinstance(init, click.Command)

    def test_init_name(self) -> None:
        assert init.name == "init"

    def test_init_has_agent_option(self) -> None:
        params = {p.name for p in init.params}
        assert "agent" in params

    def test_init_agent_default(self) -> None:
        agent_param = next(p for p in init.params if p.name == "agent")
        assert agent_param.default == "claude"


class TestLogicPositive:
    """Positive scenario tests for the init command."""

    def test_init_default_agent(self, tmp_path: Path) -> None:
        with mock.patch("goga.commands.init.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["init"])
        assert result.exit_code == 0
        claude_dir = tmp_path / ".claude"
        assert (claude_dir / "commands" / "goga" / "clarify.md").is_file()
        assert (claude_dir / "commands" / "goga" / "design.md").is_file()
        assert (claude_dir / "commands" / "goga" / "plan.md").is_file()
        assert (claude_dir / "skills" / "clarify-design" / "SKILL.md").is_file()
        assert (claude_dir / "skills" / "design-by-changes" / "SKILL.md").is_file()
        assert (claude_dir / "skills" / "plan-by-design" / "SKILL.md").is_file()
        assert "Installed 3 commands" in result.output
        assert "Installed 3 skills" in result.output

    def test_init_claude_agent_explicit(self, tmp_path: Path) -> None:
        with mock.patch("goga.commands.init.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["init", "--agent", "claude"])
        assert result.exit_code == 0
        claude_dir = tmp_path / ".claude"
        assert (claude_dir / "commands" / "goga" / "clarify.md").is_file()
        assert (claude_dir / "skills" / "clarify-design" / "SKILL.md").is_file()


class TestLogicNegative:
    """Negative scenario tests for the init command."""

    def test_init_unknown_agent(self, tmp_path: Path) -> None:
        with mock.patch("goga.commands.init.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["init", "--agent", "unknown"])
        assert result.exit_code == 1
        assert "unsupported agent" in result.output
        assert not (tmp_path / ".claude").exists()


class TestLogicEdgeCases:
    """Edge case tests for the init command."""

    def test_init_creates_target_dir(self, tmp_path: Path) -> None:
        with mock.patch("goga.commands.init.Path.home", return_value=tmp_path):
            CliRunner().invoke(app, ["init"])
        claude_dir = tmp_path / ".claude"
        assert claude_dir.is_dir()
        assert (claude_dir / "commands" / "goga").is_dir()
        assert (claude_dir / "skills").is_dir()

    def test_init_source_missing(self, tmp_path: Path) -> None:
        with (
            mock.patch("goga.commands.init.Path.home", return_value=tmp_path),
            mock.patch(
                "goga.commands.init._get_source_dir",
                return_value=tmp_path / "nonexistent",
            ),
        ):
            result = CliRunner().invoke(app, ["init"])
        assert result.exit_code == 1
        assert "agent resources not found" in result.output
        assert (tmp_path / ".claude").is_dir()
        assert not (tmp_path / ".claude" / "commands").exists()
        assert not (tmp_path / ".claude" / "skills").exists()
