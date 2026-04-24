from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
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

# goga.commands.__init__ re-exports the Click command as "build", shadowing the
# module.  Retrieve the actual module from sys.modules so that mock.patch can
# reach module-level attributes like DEFAULTS_PACKAGE_DIR.
_build_module = sys.modules["goga.commands.build"]


def _run_build_in_tmp(tmp_path, args=None, *, skip_manifest_check=True):
    """Run the build command in tmp_path directory, restoring CWD afterwards."""
    original_cwd = str(Path.cwd())
    try:
        os.chdir(tmp_path)
        runner = CliRunner()
        full_args = list(args or [])
        if skip_manifest_check:
            full_args = ["--skip-manifest-check", *full_args]
        return runner.invoke(build_cmd, full_args)
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

    def test_build_has_nine_options(self) -> None:
        """The build command has 9 options (plus 1 argument)."""
        options = [p for p in build_cmd.params if isinstance(p, click.Option)]
        assert len(options) == 9


class TestHelpOutput:
    def test_help_exit_code_zero(self) -> None:
        """The --help flag produces exit code 0."""
        runner = CliRunner()
        result = runner.invoke(build_cmd, ["--help"])
        assert result.exit_code == 0

    def test_help_contains_all_options(self) -> None:
        """The --help output lists all 9 CLI options."""
        runner = CliRunner()
        result = runner.invoke(build_cmd, ["--help"])
        output = result.output
        for opt in (
            "--dry-run",
            "--worktree",
            "--skip-finalize",
            "--skip-manifest-check",
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
    def test_overwrite_existing_files(self, mock_which, mock_call, tmp_path) -> None:
        """Existing files in .ralphex/ are overwritten with defaults."""
        ralphex_prompts = tmp_path / ".ralphex" / "prompts"
        ralphex_prompts.mkdir(parents=True)
        existing_file = ralphex_prompts / "task.txt"
        existing_file.write_text("ORIGINAL CONTENT DO NOT OVERWRITE")

        _run_build_in_tmp(tmp_path, ["plan.md"])

        # File was overwritten — content no longer matches original
        assert existing_file.read_text() != "ORIGINAL CONTENT DO NOT OVERWRITE"
        # All default files present
        expected_files = {"task.txt", "codex.txt", "review_first.txt", "review_second.txt"}
        actual_files = {f.name for f in ralphex_prompts.iterdir() if f.is_file()}
        assert expected_files.issubset(actual_files)

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_defaults_subdir_empty_no_error(self, mock_which, mock_call, tmp_path) -> None:
        """Empty prompts/ and agents/ subdirectories under defaults_dir cause no error."""
        fake_defaults = tmp_path / "fake_defaults"
        (fake_defaults / "prompts").mkdir(parents=True)
        (fake_defaults / "agents").mkdir(parents=True)

        with mock.patch.object(_build_module, "DEFAULTS_PACKAGE_DIR", fake_defaults):
            result = _run_build_in_tmp(tmp_path, ["plan.md"])

        assert result.exit_code == 0
        prompts_dir = tmp_path / ".ralphex" / "prompts"
        assert prompts_dir.is_dir()
        assert list(prompts_dir.iterdir()) == []
        agents_dir = tmp_path / ".ralphex" / "agents"
        assert agents_dir.is_dir()
        assert list(agents_dir.iterdir()) == []

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_overwrite_agents_existing_files(self, mock_which, mock_call, tmp_path) -> None:
        """Existing agent files in .ralphex/agents/ are overwritten with defaults."""
        ralphex_agents = tmp_path / ".ralphex" / "agents"
        ralphex_agents.mkdir(parents=True)
        existing_file = ralphex_agents / "quality.txt"
        existing_file.write_text("ORIGINAL AGENT CONTENT")

        _run_build_in_tmp(tmp_path, ["plan.md"])

        assert existing_file.read_text() != "ORIGINAL AGENT CONTENT"
        expected_files = {
            "quality.txt",
            "implementation.txt",
            "testing.txt",
            "simplification.txt",
            "documentation.txt",
        }
        actual_files = {f.name for f in ralphex_agents.iterdir() if f.is_file()}
        assert expected_files.issubset(actual_files)

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_repeated_build_overwrites_every_time(self, mock_which, mock_call, tmp_path) -> None:
        """Running build twice restores defaults even if files were modified between runs."""
        _run_build_in_tmp(tmp_path, ["plan.md"])

        # Modify file between runs
        prompts_dir = tmp_path / ".ralphex" / "prompts"
        modified_file = prompts_dir / "task.txt"
        modified_file.write_text("USER MODIFICATION BETWEEN RUNS")

        # Second run should overwrite back to defaults
        _run_build_in_tmp(tmp_path, ["plan.md"])

        assert modified_file.read_text() != "USER MODIFICATION BETWEEN RUNS"


class TestDefaultsDirNotFound:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_defaults_dir_not_found_exits_with_error(self, mock_which, mock_call, tmp_path) -> None:
        """When defaults directory is missing, build exits with code 1 and error in stderr."""
        with mock.patch.object(
            _build_module, "DEFAULTS_PACKAGE_DIR", Path("/nonexistent/defaults")
        ):
            result = _run_build_in_tmp(tmp_path, ["plan.md"])
        assert result.exit_code == 1
        assert "Error" in result.stderr
        assert "defaults" in result.stderr
        assert "nonexistent" in result.stderr


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


class TestWrapperScriptEnvVariable:
    def test_wrapper_script_uses_anthropic_api_token(self) -> None:
        """Wrapper script constant contains ANTHROPIC_API_TOKEN, not ZAI_TOKEN."""
        assert "ANTHROPIC_API_TOKEN" in CLAUDE_WRAPPER_SCRIPT
        assert "ZAI_TOKEN" not in CLAUDE_WRAPPER_SCRIPT


class TestCodexEnabledDefault:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_default_false_in_config(self, mock_which, mock_call, tmp_path) -> None:
        """Without goga.yml, codex_enabled defaults to false in .ralphex/config."""
        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in config_content


class TestCodexEnabledFromGogaYml:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_true_from_goga_yml(self, mock_which, mock_call, tmp_path) -> None:
        """goga.yml with codex_enabled: true writes codex_enabled = true to config."""
        goga_yml = tmp_path / "goga.yml"
        goga_yml.write_text(yaml.dump({"build": {"codex_enabled": True}}))

        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = true" in config_content

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_overwritten_on_rerun(self, mock_which, mock_call, tmp_path) -> None:
        """Existing codex_enabled value is overwritten by new goga.yml value."""
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "config").write_text("codex_enabled = true\n")

        goga_yml = tmp_path / "goga.yml"
        goga_yml.write_text(yaml.dump({"build": {"codex_enabled": False}}))

        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (ralphex_dir / "config").read_text()
        assert "codex_enabled = false" in config_content
        assert "codex_enabled = true" not in config_content
        assert "claude_command = .ralphex/claude-wrapper.sh" in config_content

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_false_explicit_in_goga_yml(self, mock_which, mock_call, tmp_path) -> None:
        """Explicit codex_enabled: false in goga.yml writes false to config."""
        goga_yml = tmp_path / "goga.yml"
        goga_yml.write_text(yaml.dump({"build": {"codex_enabled": False}}))

        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in config_content

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_invalid_type_in_goga_yml(self, mock_which, mock_call, tmp_path) -> None:
        """Non-boolean codex_enabled value (string) is written as-is lowercased."""
        goga_yml = tmp_path / "goga.yml"
        goga_yml.write_text(yaml.dump({"build": {"codex_enabled": "yes"}}))

        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = yes" in config_content

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_overwrite_preserves_other_keys(self, mock_which, mock_call, tmp_path) -> None:
        """Overwriting codex_enabled preserves other custom keys."""
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "config").write_text("custom_key = custom_value\ncodex_enabled = false\n")

        goga_yml = tmp_path / "goga.yml"
        goga_yml.write_text(yaml.dump({"build": {"codex_enabled": True}}))

        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (ralphex_dir / "config").read_text()
        assert "codex_enabled = true" in config_content
        assert "custom_key = custom_value" in config_content

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_overwrite_preserves_comments(self, mock_which, mock_call, tmp_path) -> None:
        """Overwriting codex_enabled preserves comment lines."""
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "config").write_text(
            "# ralphex settings\ncodex_enabled = true\n# other\ncustom_key = val\n"
            "claude_command = .ralphex/claude-wrapper.sh\n"
            "claude_args = --dangerously-skip-permissions --output-format stream-json --verbose\n"
        )

        goga_yml = tmp_path / "goga.yml"
        goga_yml.write_text(yaml.dump({"build": {"codex_enabled": False}}))

        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (ralphex_dir / "config").read_text()
        lines = config_content.strip().splitlines()
        expected = [
            "# ralphex settings",
            "codex_enabled = false",
            "# other",
            "custom_key = val",
            "claude_command = .ralphex/claude-wrapper.sh",
            "claude_args = --dangerously-skip-permissions --output-format stream-json --verbose",
        ]
        assert lines == expected

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_missing_in_goga_yml_build_section(self, mock_which, mock_call, tmp_path) -> None:
        """Missing codex_enabled in goga.yml build section uses default false."""
        goga_yml = tmp_path / "goga.yml"
        goga_yml.write_text(yaml.dump({"build": {"worktree": True}}))

        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in config_content


def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with user config in the given path."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)


class TestManifestCheck:
    def test_manifest_check_all_committed_proceeds(self, tmp_path) -> None:
        """When all CODEMANIFEST files are committed, build proceeds normally."""
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("content")
        subprocess.run(["git", "add", "CODEMANIFEST"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)

        with (
            mock.patch.object(subprocess, "call", return_value=0),
            mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex"),
        ):
            result = _run_build_in_tmp(tmp_path, ["plan.md"], skip_manifest_check=False)

        assert result.exit_code == 0
        assert "Error" not in result.output

    def test_manifest_check_skip_flag_skips_check(self, tmp_path) -> None:
        """When --skip-manifest-check is set, uncommitted CODEMANIFEST is ignored."""
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("content")

        with (
            mock.patch.object(subprocess, "call", return_value=0),
            mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex"),
        ):
            result = _run_build_in_tmp(
                tmp_path, ["--skip-manifest-check", "plan.md"], skip_manifest_check=False
            )

        assert result.exit_code == 0
        assert "Uncommitted" not in result.output

    def test_manifest_check_uncommitted_unstaged_exit_1(self, tmp_path) -> None:
        """Uncommitted (unstaged) CODEMANIFEST causes exit 1 with error."""
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("initial")
        subprocess.run(["git", "add", "CODEMANIFEST"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)
        manifest.write_text("modified")

        result = _run_build_in_tmp(tmp_path, ["plan.md"], skip_manifest_check=False)

        assert result.exit_code == 1
        assert "Error: Uncommitted CODEMANIFEST files found:" in result.output
        assert "CODEMANIFEST" in result.output

    def test_manifest_check_untracked_exit_1(self, tmp_path) -> None:
        """Untracked CODEMANIFEST causes exit 1 with error."""
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("content")

        result = _run_build_in_tmp(tmp_path, ["plan.md"], skip_manifest_check=False)

        assert result.exit_code == 1
        assert "Error: Uncommitted CODEMANIFEST files found:" in result.output

    def test_manifest_check_staged_not_committed_exit_1(self, tmp_path) -> None:
        """Staged but not committed CODEMANIFEST causes exit 1."""
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("content")
        subprocess.run(["git", "add", "CODEMANIFEST"], cwd=tmp_path, capture_output=True, check=True)

        result = _run_build_in_tmp(tmp_path, ["plan.md"], skip_manifest_check=False)

        assert result.exit_code == 1
        assert "Error: Uncommitted CODEMANIFEST files found:" in result.output

    def test_manifest_check_not_git_repo_exit_1(self, tmp_path) -> None:
        """When not in a git repo, build exits with code 1."""
        result = _run_build_in_tmp(tmp_path, ["plan.md"], skip_manifest_check=False)

        assert result.exit_code == 1
        assert "git status failed" in result.output

    def test_manifest_check_no_codemanifest_files_proceeds(self, tmp_path) -> None:
        """Empty repo with no CODEMANIFEST files proceeds normally."""
        _init_git_repo(tmp_path)

        with (
            mock.patch.object(subprocess, "call", return_value=0),
            mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex"),
        ):
            result = _run_build_in_tmp(tmp_path, ["plan.md"], skip_manifest_check=False)

        assert result.exit_code == 0
        assert "Error" not in result.output

    def test_manifest_check_multiple_uncommitted_lists_all(self, tmp_path) -> None:
        """Multiple uncommitted CODEMANIFEST files are all listed in the error."""
        _init_git_repo(tmp_path)
        (tmp_path / ".gitkeep").write_text("")
        subprocess.run(["git", "add", ".gitkeep"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)
        for d in ("a", "b", "c"):
            subdir = tmp_path / d
            subdir.mkdir()
            (subdir / "CODEMANIFEST").write_text(f"content {d}")

        result = _run_build_in_tmp(tmp_path, ["plan.md"], skip_manifest_check=False)

        assert result.exit_code == 1
        assert "Error: Uncommitted CODEMANIFEST files found:" in result.output
        assert "a/CODEMANIFEST" in result.output
        assert "b/CODEMANIFEST" in result.output
        assert "c/CODEMANIFEST" in result.output

    def test_manifest_check_new_option_in_help(self) -> None:
        """The --skip-manifest-check option appears in --help output."""
        runner = CliRunner()
        result = runner.invoke(build_cmd, ["--help"])
        assert result.exit_code == 0
        assert "--skip-manifest-check" in result.output
