from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from unittest import mock

import click
import requests.exceptions
from click.testing import CliRunner
from goga.cli import app
from goga.commands import connect
from goga.connect.connect import _cleanup_goga_skills

_connect_module = sys.modules["goga.connect.connect"]
_cmd_connect_module = importlib.import_module("goga.commands.connect.connect")
_AGENT_SOURCE_DIR = Path(__file__).parent.parent.parent / "goga" / "agent"


def _mock_requests_response(content: bytes = b"dsl content") -> mock.MagicMock:
    mock_response = mock.MagicMock()
    mock_response.content = content
    mock_response.status_code = 200
    mock_response.raise_for_status = mock.MagicMock()
    return mock_response


def _invoke_install(tmp_path: Path, agents: tuple[str, ...] = ("claude",)) -> click.testing.Result:
    with (
        mock.patch("pathlib.Path.home", return_value=tmp_path),
        mock.patch.object(_connect_module.requests, "get", return_value=_mock_requests_response()),
    ):
        return CliRunner().invoke(app, ["connect", *agents])


class TestFacadeAvailability:
    """Contract tests -- verify connect is properly exposed as a click Command."""

    def test_connect_importable(self) -> None:
        assert connect is not None

    def test_connect_is_click_command(self) -> None:
        assert isinstance(connect, click.Command)

    def test_connect_command_name_is_connect(self) -> None:
        assert connect.name == "connect"

    def test_connect_has_agents_argument(self) -> None:
        params = {p.name for p in connect.params}
        assert "agents" in params

    def test_connect_agents_is_argument(self) -> None:
        agents_param = next(p for p in connect.params if p.name == "agents")
        assert isinstance(agents_param, click.Argument)

    def test_connect_agents_is_required(self) -> None:
        agents_param = next(p for p in connect.params if p.name == "agents")
        assert agents_param.required


class TestForceOverwriteContract:
    """Contract tests -- verify --force-overwrite option on CLI connect."""

    def test_force_overwrite_param_exists(self) -> None:
        params = {p.name for p in connect.params}
        assert "force_overwrite" in params

    def test_force_overwrite_is_flag(self) -> None:
        param = next(p for p in connect.params if p.name == "force_overwrite")
        assert isinstance(param, click.Option)
        assert param.is_flag

    def test_force_overwrite_default_is_false(self) -> None:
        param = next(p for p in connect.params if p.name == "force_overwrite")
        assert param.default is False


class TestCleanupGogaSkillsContract:
    """Contract tests for _cleanup_goga_skills function."""

    def test_cleanup_goga_skills_exists(self) -> None:
        assert hasattr(_connect_module, "_cleanup_goga_skills")

    def test_cleanup_goga_skills_is_callable(self) -> None:
        assert callable(_cleanup_goga_skills)

    def test_cleanup_goga_skills_signature(self) -> None:
        sig = inspect.signature(_cleanup_goga_skills)
        params = list(sig.parameters.keys())
        assert len(params) == 1
        # annotations may be stringified due to __future__ annotations
        ret = sig.return_annotation
        assert ret is int or ret == "int"


class TestDownloadDslSpecContract:
    """Contract tests for _download_dsl_spec function."""

    def test_download_dsl_spec_exists(self) -> None:
        assert hasattr(_connect_module, "_download_dsl_spec")

    def test_download_dsl_spec_is_callable(self) -> None:
        assert callable(_connect_module._download_dsl_spec)

    def test_download_dsl_spec_signature(self) -> None:
        sig = inspect.signature(_connect_module._download_dsl_spec)
        params = list(sig.parameters.keys())
        assert len(params) == 1
        param_annotation = sig.parameters[params[0]].annotation
        assert param_annotation is Path or param_annotation == "Path"
        ret = sig.return_annotation
        assert ret is None or ret == "None"

    def test_dsl_spec_url_constant(self) -> None:
        assert hasattr(_connect_module, "DSL_SPEC_URL")
        assert _connect_module.DSL_SPEC_URL == (
            "https://raw.githubusercontent.com/qarium/codemanifest/refs/heads/0.0.x/specs/en.md"
        )

    def test_download_dsl_spec_integrated_in_install(self, tmp_path: Path) -> None:
        mock_response = _mock_requests_response(b"dsl content")
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=mock_response) as mock_get,
        ):
            result = CliRunner().invoke(app, ["connect", "claude"])
        assert result.exit_code == 0
        mock_get.assert_called_once_with(_connect_module.DSL_SPEC_URL, timeout=30)


class TestLogicPositive:
    """Positive scenario tests for the connect command."""

    def test_install_single_agent(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=_mock_requests_response()),
        ):
            result = CliRunner().invoke(app, ["connect", "claude"])
        assert result.exit_code == 0
        claude_dir = tmp_path / ".claude"
        assert (claude_dir / "commands" / "goga" / "review.md").is_file()
        assert (claude_dir / "commands" / "goga" / "design.md").is_file()
        assert (claude_dir / "commands" / "goga" / "plan.md").is_file()
        assert (claude_dir / "skills" / "goga-review-design" / "SKILL.md").is_file()
        assert (claude_dir / "skills" / "goga-design-by-changes" / "SKILL.md").is_file()
        assert (claude_dir / "skills" / "goga-plan-by-design" / "SKILL.md").is_file()
        assert (claude_dir / "skills" / "goga-review-plan" / "SKILL.md").is_file()
        assert (claude_dir / "skills" / "goga-arch-by-brainstorm" / "SKILL.md").is_file()
        assert (claude_dir / "skills" / "goga-cells-by-brainstorm" / "SKILL.md").is_file()
        assert (claude_dir / "skills" / "goga-cell" / "dsl.md").is_file()
        assert "Installed 9 commands" in result.output
        installed_skills = int(result.output.split("Installed ")[-1].split(" skills")[0])
        assert installed_skills >= 46

    def test_install_codex_agent(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=_mock_requests_response()),
        ):
            result = CliRunner().invoke(app, ["connect", "codex"])
        assert result.exit_code == 0
        codex_dir = tmp_path / ".codex"
        assert (codex_dir / "skills" / "goga-cell" / "dsl.md").is_file()
        assert (codex_dir / "skills" / "goga-review-design" / "SKILL.md").is_file()
        assert not (codex_dir / "commands").exists()
        assert "Installed goga commands" not in result.output
        assert "Installed" in result.output
        assert "skills" in result.output

    def test_install_cursor_agent(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=_mock_requests_response()),
        ):
            result = CliRunner().invoke(app, ["connect", "cursor"])
        assert result.exit_code == 0
        cursor_dir = tmp_path / ".cursor"
        assert (cursor_dir / "skills" / "goga-cell" / "dsl.md").is_file()
        assert (cursor_dir / "skills" / "goga-review-design" / "SKILL.md").is_file()
        assert not (cursor_dir / "commands").exists()
        assert "Installed goga commands" not in result.output
        assert "Installed" in result.output
        assert "skills" in result.output

    def test_install_multiple_agents(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=_mock_requests_response()),
        ):
            result = CliRunner().invoke(app, ["connect", "claude", "codex"])
        assert result.exit_code == 0
        assert (tmp_path / ".claude" / "commands" / "goga" / "review.md").is_file()
        assert (tmp_path / ".claude" / "skills" / "goga-cell" / "dsl.md").is_file()
        assert (tmp_path / ".codex" / "skills" / "goga-cell" / "dsl.md").is_file()
        assert not (tmp_path / ".codex" / "commands").exists()
        assert "Installed" in result.output
        assert "skills" in result.output

    """Negative scenario tests for the connect command."""

    def test_install_unknown_agent(self, tmp_path: Path) -> None:
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["connect", "unknown"])
        assert result.exit_code == 1
        assert "unsupported agent" in result.output
        assert not (tmp_path / ".claude").exists()

    def test_install_no_agents(self, tmp_path: Path) -> None:
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            result = CliRunner().invoke(app, ["connect"])
        assert result.exit_code != 0


class TestLogicEdgeCases:
    """Edge case tests for the connect command."""

    def test_install_creates_target_dir(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=_mock_requests_response()),
        ):
            result = CliRunner().invoke(app, ["connect", "claude"])
        assert result.exit_code == 0
        claude_dir = tmp_path / ".claude"
        assert claude_dir.is_dir()
        assert (claude_dir / "commands" / "goga").is_dir()
        assert (claude_dir / "skills").is_dir()

    def test_install_source_missing(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(
                _connect_module,
                "_get_source_dir",
                return_value=tmp_path / "nonexistent",
            ),
        ):
            result = CliRunner().invoke(app, ["connect", "claude"])
        assert result.exit_code == 1
        assert "agent resources not found" in result.output
        assert not (tmp_path / ".claude").exists()

    def test_install_oserror_during_install(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(
                _connect_module,
                "_install_commands",
                side_effect=OSError("permission denied"),
            ),
        ):
            result = CliRunner().invoke(app, ["connect", "claude"])
        assert result.exit_code == 1
        assert "Error:" in result.output


class TestIntegration:
    """Integration tests for cross-cutting connect command behaviors."""

    def test_install_idempotent(self, tmp_path: Path) -> None:
        first = _invoke_install(tmp_path)
        assert first.exit_code == 0

        second = _invoke_install(tmp_path)
        assert second.exit_code == 0

        source_clarify = _AGENT_SOURCE_DIR / "commands" / "review.md"
        target_clarify = tmp_path / ".claude" / "commands" / "goga" / "review.md"
        assert target_clarify.read_text() == source_clarify.read_text()

    def test_install_preserves_existing_files(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "CLAUDE.md").write_text("keep this content")
        (claude_dir / "settings.json").write_text('{"key": "value"}')

        result = _invoke_install(tmp_path)
        assert result.exit_code == 0

        assert (claude_dir / "CLAUDE.md").read_text() == "keep this content"
        assert (claude_dir / "settings.json").read_text() == '{"key": "value"}'
        assert (claude_dir / "commands" / "goga" / "review.md").is_file()

    def test_install_preserves_other_skills(self, tmp_path: Path) -> None:
        custom = tmp_path / ".claude" / "skills" / "my-custom-skill"
        custom.mkdir(parents=True)
        (custom / "SKILL.md").write_text("my custom skill content")

        result = _invoke_install(tmp_path)
        assert result.exit_code == 0

        assert (custom / "SKILL.md").read_text() == "my custom skill content"
        assert (tmp_path / ".claude" / "skills" / "goga-review-design" / "SKILL.md").is_file()

    def test_install_replaces_old_commands(self, tmp_path: Path) -> None:
        goga_cmds = tmp_path / ".claude" / "commands" / "goga"
        goga_cmds.mkdir(parents=True)
        (goga_cmds / "old-deleted-command.md").write_text("should be removed")
        (goga_cmds / "review.md").write_text("old version")

        result = _invoke_install(tmp_path)
        assert result.exit_code == 0

        assert not (goga_cmds / "old-deleted-command.md").exists()

        source_clarify = _AGENT_SOURCE_DIR / "commands" / "review.md"
        assert (goga_cmds / "review.md").read_text() == source_clarify.read_text()

        installed_files = sorted(p.name for p in goga_cmds.iterdir())
        assert installed_files == [
            "acceptance.md",
            "apply.md",
            "brainstorm.md",
            "change.md",
            "design.md",
            "plan.md",
            "propose.md",
            "review.md",
            "tool.md",
        ]

    def test_install_preserves_other_commands(self, tmp_path: Path) -> None:
        other_cmd = tmp_path / ".claude" / "commands" / "my-other-command"
        other_cmd.mkdir(parents=True)
        (other_cmd / "file.md").write_text("my other command content")

        result = _invoke_install(tmp_path)
        assert result.exit_code == 0

        assert (other_cmd / "file.md").read_text() == "my other command content"
        assert (tmp_path / ".claude" / "commands" / "goga" / "review.md").is_file()

    def test_install_skill_files_recursive(self, tmp_path: Path) -> None:
        result = _invoke_install(tmp_path)
        assert result.exit_code == 0

        skills_dir = tmp_path / ".claude" / "skills"

        clarify_design = skills_dir / "goga-review-design"
        assert (clarify_design / "SKILL.md").is_file()

        dbc = skills_dir / "goga-design-by-changes"
        assert (dbc / "SKILL.md").is_file()
        assert (dbc / "design-doc-template.md").is_file()

        pbd = skills_dir / "goga-plan-by-design"
        assert (pbd / "SKILL.md").is_file()
        assert (pbd / "conventions.md").is_file()
        assert (pbd / "output-template.md").is_file()

        vp = skills_dir / "goga-review-plan"
        assert (vp / "SKILL.md").is_file()


class TestCleanupGogaSkillsLogic:
    """Logical tests for _cleanup_goga_skills behavior during install."""

    def test_install_cleanup_removes_old_goga_skills(self, tmp_path: Path) -> None:
        """Stale goga-* skills are removed before fresh install."""
        claude_dir = tmp_path / ".claude"
        skills_dir = claude_dir / "skills"

        # Create stale goga skills
        (skills_dir / "goga-old-skill").mkdir(parents=True)
        (skills_dir / "goga-old-skill" / "skill.md").write_text("old")
        (skills_dir / "goga-another-old").mkdir(parents=True)
        (skills_dir / "goga-another-old" / "data.md").write_text("old data")

        result = _invoke_install(tmp_path)
        assert result.exit_code == 0

        assert not (skills_dir / "goga-old-skill").exists()
        assert not (skills_dir / "goga-another-old").exists()
        # New goga skills are installed
        assert (skills_dir / "goga-review-design" / "SKILL.md").is_file()

    def test_install_cleanup_keeps_non_goga_skills(self, tmp_path: Path) -> None:
        """Non-goga skills are preserved during cleanup."""
        skills_dir = tmp_path / ".claude" / "skills"

        (skills_dir / "other-skill").mkdir(parents=True)
        (skills_dir / "other-skill" / "data.md").write_text("custom content")
        (skills_dir / "my-custom-plugin").mkdir(parents=True)
        (skills_dir / "my-custom-plugin" / "plugin.py").write_text("plugin")

        result = _invoke_install(tmp_path)
        assert result.exit_code == 0

        assert (skills_dir / "other-skill" / "data.md").read_text() == "custom content"
        assert (skills_dir / "my-custom-plugin" / "plugin.py").read_text() == "plugin"

    def test_install_fresh_no_existing_skills(self, tmp_path: Path) -> None:
        """First install with no skills/ dir works correctly."""
        # Only .claude exists, no skills subdir
        (tmp_path / ".claude").mkdir()

        result = _invoke_install(tmp_path)
        assert result.exit_code == 0

        skills_dir = tmp_path / ".claude" / "skills"
        assert (skills_dir / "goga-review-design" / "SKILL.md").is_file()

    def test_install_cleanup_permission_error(self, tmp_path: Path) -> None:
        """OSError during cleanup is handled gracefully."""
        skills_dir = tmp_path / ".claude" / "skills"
        (skills_dir / "goga-locked").mkdir(parents=True)

        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(
                _connect_module,
                "_cleanup_goga_skills",
                side_effect=OSError("denied"),
            ),
        ):
            result = CliRunner().invoke(app, ["connect", "claude"])

        assert result.exit_code == 1
        assert "Error:" in result.output

    def test_install_cleanup_empty_skills_dir(self, tmp_path: Path) -> None:
        """Empty skills/ dir doesn't cause errors."""
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        result = _invoke_install(tmp_path)
        assert result.exit_code == 0

        assert (skills_dir / "goga-review-design" / "SKILL.md").is_file()

    def test_install_cleanup_mixed_content_in_skills(self, tmp_path: Path) -> None:
        """Mixed content: goga dirs removed, non-goga dirs/files preserved."""
        skills_dir = tmp_path / ".claude" / "skills"

        (skills_dir / "goga-old").mkdir(parents=True)
        (skills_dir / "goga-old" / "old.md").write_text("old")
        (skills_dir / "goga-another").mkdir(parents=True)
        (skills_dir / "goga-another" / "data.md").write_text("data")
        (skills_dir / "my-skill").mkdir(parents=True)
        (skills_dir / "my-skill" / "custom.md").write_text("custom")
        (skills_dir / "some-file.txt").write_text("just a file")

        result = _invoke_install(tmp_path)
        assert result.exit_code == 0

        assert not (skills_dir / "goga-old").exists()
        assert not (skills_dir / "goga-another").exists()
        assert (skills_dir / "my-skill" / "custom.md").read_text() == "custom"
        assert (skills_dir / "some-file.txt").read_text() == "just a file"

    def test_install_cleanup_preserves_goga_without_hyphen(self, tmp_path: Path) -> None:
        """Directory named 'goga' (no hyphen) is not removed by cleanup."""
        skills_dir = tmp_path / ".claude" / "skills"

        (skills_dir / "goga").mkdir(parents=True)
        (skills_dir / "goga" / "custom.md").write_text("must keep")

        result = _invoke_install(tmp_path)
        assert result.exit_code == 0

        assert (skills_dir / "goga" / "custom.md").read_text() == "must keep"


class TestDownloadDslSpecLogic:
    """Logical tests for _download_dsl_spec behavior during install."""

    def test_download_dsl_spec_success(self, tmp_path: Path) -> None:
        mock_response = _mock_requests_response(b"dsl content")
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=mock_response) as mock_get,
        ):
            result = CliRunner().invoke(app, ["connect", "claude"])
        assert result.exit_code == 0
        dsl_file = tmp_path / ".claude" / "skills" / "goga-cell" / "dsl.md"
        assert dsl_file.is_file()
        assert dsl_file.read_bytes() == b"dsl content"
        mock_get.assert_called_once_with(_connect_module.DSL_SPEC_URL, timeout=30)

    def test_download_dsl_spec_idempotent(self, tmp_path: Path) -> None:
        mock_response_old = _mock_requests_response(b"old dsl")
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=mock_response_old),
        ):
            first = CliRunner().invoke(app, ["connect", "claude"])
        assert first.exit_code == 0
        dsl_file = tmp_path / ".claude" / "skills" / "goga-cell" / "dsl.md"
        assert dsl_file.read_bytes() == b"old dsl"

        mock_response_new = _mock_requests_response(b"new dsl content")
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=mock_response_new),
        ):
            second = CliRunner().invoke(app, ["connect", "claude"])
        assert second.exit_code == 0
        assert dsl_file.read_bytes() == b"new dsl content"

    def test_download_dsl_spec_network_error(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(
                _connect_module.requests,
                "get",
                side_effect=requests.exceptions.ConnectionError("connection refused"),
            ),
        ):
            result = CliRunner().invoke(app, ["connect", "claude"])
        assert result.exit_code == 1
        assert "Failed to download DSL spec" in result.output
        assert "connection refused" in result.output

    def test_download_dsl_spec_http_error(self, tmp_path: Path) -> None:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 404
        mock_resp.reason = "Not Found"
        http_error = requests.exceptions.HTTPError(response=mock_resp)
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(
                _connect_module.requests,
                "get",
                side_effect=http_error,
            ),
        ):
            result = CliRunner().invoke(app, ["connect", "claude"])
        assert result.exit_code == 1
        assert "Failed to download DSL spec" in result.output
        assert "HTTP 404" in result.output
        assert "Not Found" in result.output

    def test_download_dsl_spec_timeout(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(
                _connect_module.requests,
                "get",
                side_effect=requests.exceptions.Timeout("timed out"),
            ),
        ):
            result = CliRunner().invoke(app, ["connect", "claude"])
        assert result.exit_code == 1
        assert "Failed to download DSL spec" in result.output
        assert "timed out" in result.output

    def test_download_dsl_spec_empty_response(self, tmp_path: Path) -> None:
        mock_response = _mock_requests_response(b"")
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=mock_response),
        ):
            result = CliRunner().invoke(app, ["connect", "claude"])
        assert result.exit_code == 0
        dsl_file = tmp_path / ".claude" / "skills" / "goga-cell" / "dsl.md"
        assert dsl_file.is_file()
        assert dsl_file.read_bytes() == b""

    def test_download_dsl_spec_file_write_error(self, tmp_path: Path) -> None:
        mock_response = _mock_requests_response(b"dsl content")

        def _write_bytes_only_dsl(self, data):
            if "dsl.md" in str(self):
                raise OSError("permission denied")
            return Path.write_bytes(self, data)

        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=mock_response),
            mock.patch.object(Path, "write_bytes", _write_bytes_only_dsl),
        ):
            result = CliRunner().invoke(app, ["connect", "claude"])
        assert result.exit_code == 1
        assert "Error:" in result.output


class TestForceOverwriteLogic:
    """Logical tests -- verify --force-overwrite CLI behavior."""

    def test_install_cli_force_overwrite_flag(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=_mock_requests_response()),
        ):
            result = CliRunner().invoke(app, ["connect", "claude", "--force-overwrite"])
        assert result.exit_code == 0

    def test_install_cli_default_no_force(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=_mock_requests_response()),
            mock.patch.object(_cmd_connect_module, "connect_logic") as mock_logic,
        ):
            mock_logic.return_value = 0
            CliRunner().invoke(app, ["connect", "claude"])
        mock_logic.assert_called_once()
        assert mock_logic.call_args.kwargs.get("force_overwrite") is False

    def test_install_cli_passes_force_overwrite_true(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_connect_module.requests, "get", return_value=_mock_requests_response()),
            mock.patch.object(_cmd_connect_module, "connect_logic") as mock_logic,
        ):
            mock_logic.return_value = 0
            CliRunner().invoke(app, ["connect", "claude", "--force-overwrite"])
        mock_logic.assert_called_once()
        assert mock_logic.call_args.kwargs.get("force_overwrite") is True
