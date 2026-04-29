from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import click
from click.testing import CliRunner
from goga.cli import app
from goga.commands import install
from goga.commands.install import load_config

_install_module = sys.modules["goga.commands.install"]


class TestFacadeAvailability:
    """Contract tests -- verify install is properly exposed as a click Command."""

    def test_install_importable(self) -> None:
        assert install is not None

    def test_install_is_click_command(self) -> None:
        assert isinstance(install, click.Command)

    def test_install_command_name_is_install(self) -> None:
        assert install.name == "install"

    def test_install_has_agent_option(self) -> None:
        params = {p.name for p in install.params}
        assert "agent" in params

    def test_install_agent_default_is_none(self) -> None:
        agent_param = next(p for p in install.params if p.name == "agent")
        assert agent_param.default is None

    def test_install_load_config_imported(self) -> None:
        assert load_config is not None


class TestLogicPositive:
    """Positive scenario tests for the install command."""

    def test_install_default_agent(self, tmp_path: Path) -> None:
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        claude_dir = tmp_path / ".claude"
        assert (claude_dir / "commands" / "goga" / "review.md").is_file()
        assert (claude_dir / "commands" / "goga" / "design.md").is_file()
        assert (claude_dir / "commands" / "goga" / "plan.md").is_file()
        assert (claude_dir / "commands" / "goga" / "verify.md").is_file()
        assert (claude_dir / "skills" / "review-design" / "SKILL.md").is_file()
        assert (claude_dir / "skills" / "design-by-changes" / "SKILL.md").is_file()
        assert (claude_dir / "skills" / "plan-by-design" / "SKILL.md").is_file()
        assert (claude_dir / "skills" / "verify-plan" / "SKILL.md").is_file()
        assert (claude_dir / "skills" / "arch-by-brainstorm" / "SKILL.md").is_file()
        assert (claude_dir / "skills" / "cells-by-brainstorm" / "SKILL.md").is_file()
        assert "Installed 6 commands" in result.output
        assert "Installed 9 skills" in result.output

    def test_install_claude_agent_explicit(self, tmp_path: Path) -> None:
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["install", "--agent", "claude"])
        assert result.exit_code == 0
        claude_dir = tmp_path / ".claude"
        assert (claude_dir / "commands" / "goga" / "review.md").is_file()
        assert (claude_dir / "skills" / "review-design" / "SKILL.md").is_file()


class TestLogicConfig:
    """Tests for config-based default resolution in the install command."""

    def test_install_agent_from_config(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / ".goga.yml").write_text(
            "language: python\nbuild:\n  task_executor:\n    agent: claude\n"
        )
        monkeypatch.chdir(tmp_path)
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        claude_dir = tmp_path / ".claude"
        assert (claude_dir / "commands" / "goga" / "review.md").is_file()
        assert (claude_dir / "skills" / "review-design" / "SKILL.md").is_file()

    def test_install_agent_cli_overrides_config(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / ".goga.yml").write_text(
            "language: python\nbuild:\n  task_executor:\n    agent: codex\n"
        )
        monkeypatch.chdir(tmp_path)
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["install", "--agent", "claude"])
        assert result.exit_code == 0
        claude_dir = tmp_path / ".claude"
        assert (claude_dir / "commands" / "goga" / "review.md").is_file()

    def test_install_config_missing(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code != 0
        assert ".goga.yml" in result.output or ".goga.yml" in result.stderr

    def test_install_config_invalid_agent(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / ".goga.yml").write_text(
            "language: python\nbuild:\n  task_executor:\n    agent: ''\n"
        )
        monkeypatch.chdir(tmp_path)
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code != 0
        assert "agent" in result.output


class TestLogicNegative:
    """Negative scenario tests for the install command."""

    def test_install_unknown_agent(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / ".goga.yml").write_text(
            "language: python\nbuild:\n  task_executor:\n    agent: claude\n"
        )
        monkeypatch.chdir(tmp_path)
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["install", "--agent", "unknown"])
        assert result.exit_code == 1
        assert "unsupported agent" in result.output
        assert not (tmp_path / ".claude").exists()


class TestLogicEdgeCases:
    """Edge case tests for the install command."""

    def test_install_creates_target_dir(self, tmp_path: Path) -> None:
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        claude_dir = tmp_path / ".claude"
        assert claude_dir.is_dir()
        assert (claude_dir / "commands" / "goga").is_dir()
        assert (claude_dir / "skills").is_dir()

    def test_install_source_missing(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(
                _install_module,
                "_get_source_dir",
                return_value=tmp_path / "nonexistent",
            ),
        ):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 1
        assert "agent resources not found" in result.output
        assert not (tmp_path / ".claude").exists()

    def test_install_oserror_during_install(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(
                _install_module,
                "_install_commands",
                side_effect=OSError("permission denied"),
            ),
        ):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 1
        assert "Error:" in result.output


class TestIntegration:
    """Integration tests for cross-cutting install command behaviors."""

    SOURCE_DIR = Path(__file__).parent.parent.parent.parent / "goga" / "agent"

    def _invoke_install(self, tmp_path: Path) -> click.testing.Result:
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            return CliRunner().invoke(app, ["install"])

    def test_install_idempotent(self, tmp_path: Path) -> None:
        first = self._invoke_install(tmp_path)
        assert first.exit_code == 0

        second = self._invoke_install(tmp_path)
        assert second.exit_code == 0

        source_clarify = self.SOURCE_DIR / "commands" / "review.md"
        target_clarify = tmp_path / ".claude" / "commands" / "goga" / "review.md"
        assert target_clarify.read_text() == source_clarify.read_text()

    def test_install_preserves_existing_files(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "CLAUDE.md").write_text("keep this content")
        (claude_dir / "settings.json").write_text('{"key": "value"}')

        result = self._invoke_install(tmp_path)
        assert result.exit_code == 0

        assert (claude_dir / "CLAUDE.md").read_text() == "keep this content"
        assert (claude_dir / "settings.json").read_text() == '{"key": "value"}'
        assert (claude_dir / "commands" / "goga" / "review.md").is_file()

    def test_install_preserves_other_skills(self, tmp_path: Path) -> None:
        custom = tmp_path / ".claude" / "skills" / "my-custom-skill"
        custom.mkdir(parents=True)
        (custom / "SKILL.md").write_text("my custom skill content")

        result = self._invoke_install(tmp_path)
        assert result.exit_code == 0

        assert (custom / "SKILL.md").read_text() == "my custom skill content"
        assert (tmp_path / ".claude" / "skills" / "review-design" / "SKILL.md").is_file()

    def test_install_replaces_old_commands(self, tmp_path: Path) -> None:
        goga_cmds = tmp_path / ".claude" / "commands" / "goga"
        goga_cmds.mkdir(parents=True)
        (goga_cmds / "old-deleted-command.md").write_text("should be removed")
        (goga_cmds / "review.md").write_text("old version")

        result = self._invoke_install(tmp_path)
        assert result.exit_code == 0

        assert not (goga_cmds / "old-deleted-command.md").exists()

        source_clarify = self.SOURCE_DIR / "commands" / "review.md"
        assert (goga_cmds / "review.md").read_text() == source_clarify.read_text()

        installed_files = sorted(p.name for p in goga_cmds.iterdir())
        assert installed_files == ["brainstorm.md", "cell.md", "design.md", "plan.md", "review.md", "verify.md"]

    def test_install_preserves_other_commands(self, tmp_path: Path) -> None:
        other_cmd = tmp_path / ".claude" / "commands" / "my-other-command"
        other_cmd.mkdir(parents=True)
        (other_cmd / "file.md").write_text("my other command content")

        result = self._invoke_install(tmp_path)
        assert result.exit_code == 0

        assert (other_cmd / "file.md").read_text() == "my other command content"
        assert (tmp_path / ".claude" / "commands" / "goga" / "review.md").is_file()

    def test_install_skill_files_recursive(self, tmp_path: Path) -> None:
        result = self._invoke_install(tmp_path)
        assert result.exit_code == 0

        skills_dir = tmp_path / ".claude" / "skills"

        clarify_design = skills_dir / "review-design"
        assert len(list(clarify_design.iterdir())) == 2
        assert (clarify_design / "SKILL.md").is_file()
        assert (clarify_design / "dsl.md").is_file()

        dbc = skills_dir / "design-by-changes"
        assert len(list(dbc.iterdir())) == 3
        assert (dbc / "SKILL.md").is_file()
        assert (dbc / "design-doc-template.md").is_file()
        assert (dbc / "dsl.md").is_file()

        pbd = skills_dir / "plan-by-design"
        expected = {"SKILL.md", "conventions.md", "output-template.md", "dsl.md"}
        actual = {p.name for p in pbd.iterdir()}
        assert actual == expected

        vp = skills_dir / "verify-plan"
        assert len(list(vp.iterdir())) == 2
        assert (vp / "SKILL.md").is_file()
        assert (vp / "dsl.md").is_file()
