from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from unittest import mock

import click
import yaml
from click.testing import CliRunner
from goga.commands import build
from goga.commands.build import (
    CLAUDE_WRAPPER_SCRIPT,
    DEFAULT_BUILD_CONFIG,
)
from goga.commands.build import (
    build as build_cmd,
)


def _run_build_in_tmp(tmp_path, args=None):
    """Run the build command in tmp_path directory, restoring CWD afterwards."""
    original_cwd = str(Path.cwd())
    try:
        os.chdir(tmp_path)
        runner = CliRunner()
        return runner.invoke(build_cmd, args or [])
    finally:
        os.chdir(original_cwd)


class TestFacadeAvailability:
    def test_import_build_from_commands(self) -> None:
        """The build symbol is available from goga.commands."""
        assert build is not None

    def test_build_is_click_command(self) -> None:
        """The build object is a click Command instance."""
        assert isinstance(build_cmd, click.Command)


class TestApiShape:
    def test_build_has_callback(self) -> None:
        """The build command has a callback (the actual function)."""
        assert build_cmd.callback is not None

    def test_build_name(self) -> None:
        """The command name is 'build'."""
        assert build_cmd.name == "build"

    def test_build_has_plan_argument(self) -> None:
        """The build command accepts a 'plan' argument."""
        param_names = [p.name for p in build_cmd.params]
        assert "plan" in param_names

    def test_build_plan_no_default_value(self) -> None:
        """The plan argument has no default and is required."""
        plan_param = next(p for p in build_cmd.params if p.name == "plan")
        assert plan_param.default != "docs/plans/plan.md"  # default was removed
        assert plan_param.required is True

    def test_build_plan_is_required(self, tmp_path) -> None:
        """Calling build without a plan argument fails with exit code 2."""
        result = _run_build_in_tmp(tmp_path)
        assert result.exit_code == 2
        assert "Missing argument" in result.output

    def test_build_has_eight_options(self) -> None:
        """The build command has 8 options (plus 1 argument)."""
        options = [p for p in build_cmd.params if isinstance(p, click.Option)]
        assert len(options) == 8


class TestHelpOutput:
    def test_help_exit_code_zero(self) -> None:
        """The --help flag produces exit code 0."""
        runner = CliRunner()
        result = runner.invoke(build_cmd, ["--help"])
        assert result.exit_code == 0

    def test_help_contains_all_options(self) -> None:
        """The --help output lists all 8 CLI options."""
        runner = CliRunner()
        result = runner.invoke(build_cmd, ["--help"])
        output = result.output
        for opt in (
            "--dry-run",
            "--worktree",
            "--skip-finalize",
            "--session-timeout",
            "--idle-timeout",
            "--wait",
            "--max-iterations",
            "--review-patience",
        ):
            assert opt in output, f"Option {opt} not found in help output"


class TestDryRun:
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_dry_run_exit_code_zero(self, mock_which, tmp_path) -> None:
        """Dry-run mode exits with code 0."""
        result = _run_build_in_tmp(tmp_path, ["--dry-run", "plan.md"])
        assert result.exit_code == 0

    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_dry_run_shows_command(self, mock_which, tmp_path) -> None:
        """Dry-run mode displays the assembled ralphex command."""
        result = _run_build_in_tmp(tmp_path, ["--dry-run", "plan.md"])
        assert "Dry run:" in result.output
        assert "ralphex" in result.output
        assert "plan.md" in result.output

    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_dry_run_does_not_call_ralphex(self, mock_which, tmp_path) -> None:
        """Dry-run mode does not invoke subprocess.call."""
        with mock.patch.object(subprocess, "call") as mock_call:
            _run_build_in_tmp(tmp_path, ["--dry-run", "plan.md"])
            mock_call.assert_not_called()


class TestGogaYmlReading:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_custom_models_in_settings(self, mock_which, mock_call, tmp_path) -> None:
        """Custom models from goga.yml are written to .claude/settings.json."""
        goga_yml = tmp_path / "goga.yml"
        goga_yml.write_text(
            yaml.dump(
                {
                    "build": {
                        "models": {
                            "haiku": "custom-haiku",
                            "sonnet": "custom-sonnet",
                            "opus": "custom-opus",
                            "base_url": "https://custom.api/url",
                        }
                    }
                }
            )
        )

        _run_build_in_tmp(tmp_path, ["plan.md"])

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert settings["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "custom-haiku"
        assert settings["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "custom-sonnet"
        assert settings["env"]["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "custom-opus"
        assert settings["env"]["ANTHROPIC_BASE_URL"] == "https://custom.api/url"

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_reading_goga_yml_output(self, mock_which, mock_call, tmp_path) -> None:
        """When goga.yml exists, the command outputs 'Reading goga.yml...'."""
        goga_yml = tmp_path / "goga.yml"
        goga_yml.write_text(yaml.dump({"build": {"models": {}}}))

        result = _run_build_in_tmp(tmp_path, ["plan.md"])

        assert "Reading goga.yml" in result.output


class TestMissingGogaYml:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_default_models_in_settings(self, mock_which, mock_call, tmp_path) -> None:
        """Without goga.yml, settings.json uses default model values."""
        _run_build_in_tmp(tmp_path, ["plan.md"])

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert settings["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == DEFAULT_BUILD_CONFIG["models"]["haiku"]
        assert settings["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] == DEFAULT_BUILD_CONFIG["models"]["sonnet"]
        assert settings["env"]["ANTHROPIC_DEFAULT_OPUS_MODEL"] == DEFAULT_BUILD_CONFIG["models"]["opus"]
        assert settings["env"]["ANTHROPIC_BASE_URL"] == DEFAULT_BUILD_CONFIG["models"]["base_url"]

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_missing_goga_yml_output(self, mock_which, mock_call, tmp_path) -> None:
        """Without goga.yml, the command outputs 'goga.yml not found, using defaults'."""
        result = _run_build_in_tmp(tmp_path, ["plan.md"])
        assert "goga.yml not found, using defaults" in result.output


class TestSettingsMerge:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_existing_fields_preserved(self, mock_which, mock_call, tmp_path) -> None:
        """Existing fields in settings.json are preserved during merge."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        existing_settings = {
            "custom_field": "preserved_value",
            "nested": {"key": "value"},
            "env": {"EXISTING_VAR": "existing_val"},
        }
        (claude_dir / "settings.json").write_text(json.dumps(existing_settings))

        _run_build_in_tmp(tmp_path, ["plan.md"])

        settings = json.loads((claude_dir / "settings.json").read_text())
        assert settings["custom_field"] == "preserved_value"
        assert settings["nested"]["key"] == "value"
        assert settings["env"]["EXISTING_VAR"] == "existing_val"

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_env_vars_added(self, mock_which, mock_call, tmp_path) -> None:
        """Model env vars are added to existing settings.json env section."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        existing_settings = {"env": {"EXISTING_VAR": "existing_val"}}
        (claude_dir / "settings.json").write_text(json.dumps(existing_settings))

        _run_build_in_tmp(tmp_path, ["plan.md"])

        settings = json.loads((claude_dir / "settings.json").read_text())
        assert "ANTHROPIC_DEFAULT_HAIKU_MODEL" in settings["env"]
        assert "ANTHROPIC_DEFAULT_SONNET_MODEL" in settings["env"]
        assert "ANTHROPIC_DEFAULT_OPUS_MODEL" in settings["env"]
        assert "ANTHROPIC_BASE_URL" in settings["env"]

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_attribution_set(self, mock_which, mock_call, tmp_path) -> None:
        """The attribution section is set in settings.json."""
        _run_build_in_tmp(tmp_path, ["plan.md"])

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert "attribution" in settings
        assert settings["attribution"] == {"commit": "", "pr": ""}


class TestClaudeWrapper:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_wrapper_created(self, mock_which, mock_call, tmp_path) -> None:
        """The claude-wrapper.sh file is created in .ralphex/."""
        _run_build_in_tmp(tmp_path, ["plan.md"])

        wrapper_path = tmp_path / ".ralphex" / "claude-wrapper.sh"
        assert wrapper_path.is_file()

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_wrapper_content(self, mock_which, mock_call, tmp_path) -> None:
        """The claude-wrapper.sh has the correct shebang and content."""
        _run_build_in_tmp(tmp_path, ["plan.md"])

        wrapper_path = tmp_path / ".ralphex" / "claude-wrapper.sh"
        content = wrapper_path.read_text()
        assert content == CLAUDE_WRAPPER_SCRIPT

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_wrapper_is_executable(self, mock_which, mock_call, tmp_path) -> None:
        """The claude-wrapper.sh file has execute permission."""
        _run_build_in_tmp(tmp_path, ["plan.md"])

        wrapper_path = tmp_path / ".ralphex" / "claude-wrapper.sh"
        mode = wrapper_path.stat().st_mode
        assert mode & stat.S_IXUSR
        assert mode & stat.S_IXGRP
        assert mode & stat.S_IXOTH


class TestDefaultsCopying:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_prompts_copied(self, mock_which, mock_call, tmp_path) -> None:
        """Default prompt files are copied to .ralphex/prompts/."""
        _run_build_in_tmp(tmp_path, ["plan.md"])

        prompts_dir = tmp_path / ".ralphex" / "prompts"
        assert prompts_dir.is_dir()
        # Check that at least some of the known prompt files exist
        expected_files = {"task.txt", "codex.txt", "review_first.txt", "review_second.txt"}
        actual_files = {f.name for f in prompts_dir.iterdir() if f.is_file()}
        assert expected_files.issubset(actual_files)

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_agents_copied(self, mock_which, mock_call, tmp_path) -> None:
        """Default agent files are copied to .ralphex/agents/."""
        _run_build_in_tmp(tmp_path, ["plan.md"])

        agents_dir = tmp_path / ".ralphex" / "agents"
        assert agents_dir.is_dir()
        expected_files = {
            "quality.txt",
            "implementation.txt",
            "testing.txt",
            "simplification.txt",
            "documentation.txt",
        }
        actual_files = {f.name for f in agents_dir.iterdir() if f.is_file()}
        assert expected_files.issubset(actual_files)

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_no_overwrite_existing(self, mock_which, mock_call, tmp_path) -> None:
        """Existing files in .ralphex/ are NOT overwritten."""
        ralphex_prompts = tmp_path / ".ralphex" / "prompts"
        ralphex_prompts.mkdir(parents=True)
        existing_file = ralphex_prompts / "task.txt"
        original_content = "ORIGINAL CONTENT DO NOT OVERWRITE"
        existing_file.write_text(original_content)

        _run_build_in_tmp(tmp_path, ["plan.md"])

        assert existing_file.read_text() == original_content


class TestRalphexNotFound:
    def test_error_message_in_output(self, tmp_path) -> None:
        """When ralphex is not found, error message appears in output."""
        with mock.patch.object(shutil, "which", return_value=None):
            result = _run_build_in_tmp(tmp_path, ["plan.md"])

        assert "ralphex not found in PATH" in result.output

    def test_exit_code_one(self, tmp_path) -> None:
        """When ralphex is not found, exit code is 1."""
        with mock.patch.object(shutil, "which", return_value=None):
            result = _run_build_in_tmp(tmp_path, ["plan.md"])

        assert result.exit_code == 1


class TestRalphexExecution:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_subprocess_called(self, mock_which, mock_call, tmp_path) -> None:
        """subprocess.call is invoked with the assembled ralphex command."""
        _run_build_in_tmp(tmp_path, ["plan.md"])

        mock_call.assert_called_once()
        cmd = mock_call.call_args[0][0]
        assert cmd[0] == "ralphex"
        assert "plan.md" in cmd
        assert "--config-dir" in cmd
        assert ".ralphex/" in cmd

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_exit_code_zero_on_success(self, mock_which, mock_call, tmp_path) -> None:
        """Successful ralphex execution yields exit code 0."""
        result = _run_build_in_tmp(tmp_path, ["plan.md"])
        assert result.exit_code == 0

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_custom_plan_passed(self, mock_which, mock_call, tmp_path) -> None:
        """A custom plan argument is forwarded to the ralphex command."""
        _run_build_in_tmp(tmp_path, ["my-plan.md"])

        cmd = mock_call.call_args[0][0]
        assert "my-plan.md" in cmd

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_worktree_flag_forwarded(self, mock_which, mock_call, tmp_path) -> None:
        """The --worktree CLI flag is forwarded to ralphex."""
        _run_build_in_tmp(tmp_path, ["plan.md", "--worktree"])

        cmd = mock_call.call_args[0][0]
        assert "--worktree" in cmd

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_skip_finalize_flag_forwarded(self, mock_which, mock_call, tmp_path) -> None:
        """The --skip-finalize CLI flag is forwarded to ralphex."""
        _run_build_in_tmp(tmp_path, ["plan.md", "--skip-finalize"])

        cmd = mock_call.call_args[0][0]
        assert "--skip-finalize" in cmd

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_session_timeout_forwarded(self, mock_which, mock_call, tmp_path) -> None:
        """The --session-timeout CLI option is forwarded to ralphex."""
        _run_build_in_tmp(tmp_path, ["plan.md", "--session-timeout", "30m"])

        cmd = mock_call.call_args[0][0]
        assert "--session-timeout" in cmd
        assert "30m" in cmd

    @mock.patch.object(subprocess, "call", return_value=42)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_nonzero_exit_propagated(self, mock_which, mock_call, tmp_path) -> None:
        """Non-zero ralphex return code is propagated as exit code."""
        result = _run_build_in_tmp(tmp_path, ["plan.md"])
        assert result.exit_code == 42
