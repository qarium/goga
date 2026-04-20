from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import click
from click.testing import CliRunner
from goga.cli import app
from goga.commands import init

_init_module = sys.modules["goga.commands.init"]


class TestFacadeAvailability:
    """Contract tests -- verify init is properly exposed as a click Command."""

    def test_init_importable(self) -> None:
        assert init is not None

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
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["init"])
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
        assert "Installed 4 commands" in result.output
        assert "Installed 4 skills" in result.output

    def test_init_claude_agent_explicit(self, tmp_path: Path) -> None:
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["init", "--agent", "claude"])
        assert result.exit_code == 0
        claude_dir = tmp_path / ".claude"
        assert (claude_dir / "commands" / "goga" / "review.md").is_file()
        assert (claude_dir / "skills" / "review-design" / "SKILL.md").is_file()


class TestLogicNegative:
    """Negative scenario tests for the init command."""

    def test_init_unknown_agent(self, tmp_path: Path) -> None:
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["init", "--agent", "unknown"])
        assert result.exit_code == 1
        assert "unsupported agent" in result.output
        assert not (tmp_path / ".claude").exists()


class TestLogicEdgeCases:
    """Edge case tests for the init command."""

    def test_init_creates_target_dir(self, tmp_path: Path) -> None:
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["init"])
        assert result.exit_code == 0
        claude_dir = tmp_path / ".claude"
        assert claude_dir.is_dir()
        assert (claude_dir / "commands" / "goga").is_dir()
        assert (claude_dir / "skills").is_dir()

    def test_init_source_missing(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(
                _init_module,
                "_get_source_dir",
                return_value=tmp_path / "nonexistent",
            ),
        ):
            result = CliRunner().invoke(app, ["init"])
        assert result.exit_code == 1
        assert "agent resources not found" in result.output
        assert not (tmp_path / ".claude").exists()

    def test_init_oserror_during_install(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(
                _init_module,
                "_install_commands",
                side_effect=OSError("permission denied"),
            ),
        ):
            result = CliRunner().invoke(app, ["init"])
        assert result.exit_code == 1
        assert "Error:" in result.output


class TestIntegration:
    """Integration tests for cross-cutting init command behaviors."""

    SOURCE_DIR = Path(__file__).parent.parent.parent.parent / "goga" / "agent"

    def _invoke_init(self, tmp_path: Path) -> click.testing.Result:
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            return CliRunner().invoke(app, ["init"])

    def test_init_idempotent(self, tmp_path: Path) -> None:
        first = self._invoke_init(tmp_path)
        assert first.exit_code == 0

        second = self._invoke_init(tmp_path)
        assert second.exit_code == 0

        source_clarify = self.SOURCE_DIR / "commands" / "review.md"
        target_clarify = tmp_path / ".claude" / "commands" / "goga" / "review.md"
        assert target_clarify.read_text() == source_clarify.read_text()

    def test_init_preserves_existing_files(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "CLAUDE.md").write_text("keep this content")
        (claude_dir / "settings.json").write_text('{"key": "value"}')
        (claude_dir / "README.md").write_text("readme content")

        result = self._invoke_init(tmp_path)
        assert result.exit_code == 0

        assert (claude_dir / "CLAUDE.md").read_text() == "keep this content"
        assert (claude_dir / "settings.json").read_text() == '{"key": "value"}'
        assert (claude_dir / "README.md").read_text() == "readme content"
        assert (claude_dir / "commands" / "goga" / "review.md").is_file()

    def test_init_preserves_other_skills(self, tmp_path: Path) -> None:
        custom = tmp_path / ".claude" / "skills" / "my-custom-skill"
        custom.mkdir(parents=True)
        (custom / "SKILL.md").write_text("my custom skill content")

        result = self._invoke_init(tmp_path)
        assert result.exit_code == 0

        assert (custom / "SKILL.md").read_text() == "my custom skill content"
        assert (tmp_path / ".claude" / "skills" / "review-design" / "SKILL.md").is_file()

    def test_init_replaces_old_commands(self, tmp_path: Path) -> None:
        goga_cmds = tmp_path / ".claude" / "commands" / "goga"
        goga_cmds.mkdir(parents=True)
        (goga_cmds / "old-deleted-command.md").write_text("should be removed")
        (goga_cmds / "review.md").write_text("old version")

        result = self._invoke_init(tmp_path)
        assert result.exit_code == 0

        assert not (goga_cmds / "old-deleted-command.md").exists()

        source_clarify = self.SOURCE_DIR / "commands" / "review.md"
        assert (goga_cmds / "review.md").read_text() == source_clarify.read_text()

        installed_files = sorted(p.name for p in goga_cmds.iterdir())
        assert installed_files == ["design.md", "plan.md", "review.md", "verify.md"]

    def test_init_preserves_other_commands(self, tmp_path: Path) -> None:
        other_cmd = tmp_path / ".claude" / "commands" / "my-other-command"
        other_cmd.mkdir(parents=True)
        (other_cmd / "file.md").write_text("my other command content")

        result = self._invoke_init(tmp_path)
        assert result.exit_code == 0

        assert (other_cmd / "file.md").read_text() == "my other command content"
        assert (tmp_path / ".claude" / "commands" / "goga" / "review.md").is_file()

    def test_init_skill_files_recursive(self, tmp_path: Path) -> None:
        result = self._invoke_init(tmp_path)
        assert result.exit_code == 0

        skills_dir = tmp_path / ".claude" / "skills"

        clarify_design = skills_dir / "review-design"
        assert len(list(clarify_design.iterdir())) == 1
        assert (clarify_design / "SKILL.md").is_file()

        dbc = skills_dir / "design-by-changes"
        assert len(list(dbc.iterdir())) == 2
        assert (dbc / "SKILL.md").is_file()
        assert (dbc / "design-doc-template.md").is_file()

        pbd = skills_dir / "plan-by-design"
        expected = {"SKILL.md", "README.md", "conventions.md", "example.md", "output-template.md"}
        actual = {p.name for p in pbd.iterdir()}
        assert actual == expected

        vp = skills_dir / "verify-plan"
        assert len(list(vp.iterdir())) == 1
        assert (vp / "SKILL.md").is_file()
