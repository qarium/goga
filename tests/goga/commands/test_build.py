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
from goga.build.build import CLAUDE_WRAPPER_SCRIPT
from goga.commands import build as build_cmd

_build_module = sys.modules["goga.build.build"]

TEST_ENV_VARS = {
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.7",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5-turbo",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.1",
    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
}


def _write_goga_yml(tmp_path: Path, extra: dict | None = None) -> None:
    """Write a minimal .goga/config.yml with optional extra build fields."""
    data: dict = {
        "language": "python",
        "build": {"task_executor": {"agent": "claude"}},
    }
    if extra:
        data["build"].update(extra)
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text(yaml.dump(data))


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
        assert build_cmd is not None

    def test_build_is_click_command(self) -> None:
        """The build object is a click.Command instance."""
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
        assert plan_param.required is True

    def test_build_plan_is_required(self, tmp_path) -> None:
        """Calling build without a plan argument fails with exit code 2."""
        _write_goga_yml(tmp_path)
        result = _run_build_in_tmp(tmp_path)
        assert result.exit_code == 2
        assert "Missing argument" in result.output

    def test_build_has_nine_options(self) -> None:
        """The build command has 9 options (plus 1 argument)."""
        options = [p for p in build_cmd.params if isinstance(p, click.Option)]
        assert len(options) == 9

    def test_build_has_dry_run_option(self) -> None:
        """The build command has a --dry-run option."""
        param_names = [p.name for p in build_cmd.params]
        assert "dry_run" in param_names

    def test_build_has_worktree_option(self) -> None:
        """The build command has a --worktree option."""
        param_names = [p.name for p in build_cmd.params]
        assert "worktree" in param_names

    def test_build_has_skip_finalize_option(self) -> None:
        """The build command has a --skip-finalize option."""
        param_names = [p.name for p in build_cmd.params]
        assert "skip_finalize" in param_names

    def test_build_has_skip_manifest_check_option(self) -> None:
        """The build command has a --skip-manifest-check option."""
        param_names = [p.name for p in build_cmd.params]
        assert "skip_manifest_check" in param_names

    def test_build_has_session_timeout_option(self) -> None:
        """The build command has a --session-timeout option."""
        param_names = [p.name for p in build_cmd.params]
        assert "session_timeout" in param_names

    def test_build_has_idle_timeout_option(self) -> None:
        """The build command has a --idle-timeout option."""
        param_names = [p.name for p in build_cmd.params]
        assert "idle_timeout" in param_names

    def test_build_has_wait_option(self) -> None:
        """The build command has a --wait option."""
        param_names = [p.name for p in build_cmd.params]
        assert "wait" in param_names

    def test_build_has_max_iterations_option(self) -> None:
        """The build command has a --max-iterations option."""
        param_names = [p.name for p in build_cmd.params]
        assert "max_iterations" in param_names

    def test_build_has_review_patience_option(self) -> None:
        """The build command has a --review-patience option."""
        param_names = [p.name for p in build_cmd.params]
        assert "review_patience" in param_names


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
        _write_goga_yml(tmp_path)
        result = _run_build_in_tmp(tmp_path, ["--dry-run", "plan.md"])
        assert result.exit_code == 0

    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_dry_run_shows_command(self, mock_which, tmp_path) -> None:
        """Dry-run mode displays the assembled ralphex command."""
        _write_goga_yml(tmp_path)
        result = _run_build_in_tmp(tmp_path, ["--dry-run", "plan.md"])
        assert "Dry run:" in result.output
        assert "ralphex" in result.output
        assert "plan.md" in result.output

    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_dry_run_does_not_call_ralphex(self, mock_which, tmp_path) -> None:
        """Dry-run mode does not invoke subprocess.call."""
        _write_goga_yml(tmp_path)
        with mock.patch.object(subprocess, "call") as mock_call:
            _run_build_in_tmp(tmp_path, ["--dry-run", "plan.md"])
            mock_call.assert_not_called()


class TestBuildUsesLoadConfigFromGogaConfig:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_build_env_vars_in_settings_json(self, mock_which, mock_call, tmp_path) -> None:
        """.goga/config.yml env vars are written to .claude/settings.json."""
        _write_goga_yml(
            tmp_path,
            extra={
                "task_executor": {
                    "agent": "claude",
                    "env": TEST_ENV_VARS,
                }
            },
        )

        _run_build_in_tmp(tmp_path, ["plan.md"])

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        for key, value in TEST_ENV_VARS.items():
            assert settings["env"][key] == value
        assert settings["attribution"] == {"commit": "", "pr": ""}

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_build_empty_env_dict_creates_empty_env_section(self, mock_which, mock_call, tmp_path) -> None:
        """.goga/config.yml without env section creates empty env dict in settings.json."""
        _write_goga_yml(tmp_path)
        _run_build_in_tmp(tmp_path, ["plan.md"])

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert settings["env"] == {}
        assert settings["attribution"] == {"commit": "", "pr": ""}


class TestBuildUnsupportedAgentRaisesError:
    def test_build_unsupported_agent_raises_error(self, tmp_path) -> None:
        """Unsupported agent in .goga/config.yml causes exit code 1 with error message."""
        data = {
            "language": "python",
            "build": {"task_executor": {"agent": "gemini"}},
        }
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(yaml.dump(data))

        result = _run_build_in_tmp(tmp_path, ["plan.md"])
        assert result.exit_code == 1
        assert "Unsupported agent" in result.output


class TestBuildMissingGogaYmlRaisesConfigError:
    def test_build_missing_goga_config_yml_raises_config_error(self, tmp_path) -> None:
        """Missing .goga/config.yml causes exit code 1 with config error message."""
        result = _run_build_in_tmp(tmp_path, ["plan.md"])
        assert result.exit_code == 1
        assert ".goga/config.yml" in result.output


class TestBuildCodexReviewMapsToCodexEnabled:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_build_codex_review_true(self, mock_which, mock_call, tmp_path) -> None:
        """.goga/config.yml with codex_review: true writes codex_enabled = true."""
        _write_goga_yml(tmp_path, extra={"codex_review": True})

        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = true" in config_content

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_build_codex_review_none_writes_false(self, mock_which, mock_call, tmp_path) -> None:
        """.goga/config.yml without codex_review writes codex_enabled = false."""
        _write_goga_yml(tmp_path)

        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in config_content


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

        _write_goga_yml(
            tmp_path,
            extra={
                "task_executor": {
                    "agent": "claude",
                    "env": {"ANTHROPIC_DEFAULT_HAIKU_MODEL": "custom-haiku"},
                }
            },
        )
        _run_build_in_tmp(tmp_path, ["plan.md"])

        settings = json.loads((claude_dir / "settings.json").read_text())
        assert settings["custom_field"] == "preserved_value"
        assert settings["nested"]["key"] == "value"
        assert settings["env"]["EXISTING_VAR"] == "existing_val"
        assert settings["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "custom-haiku"

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_attribution_set(self, mock_which, mock_call, tmp_path) -> None:
        """The attribution section is set in settings.json."""
        _write_goga_yml(tmp_path)
        _run_build_in_tmp(tmp_path, ["plan.md"])

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert "attribution" in settings
        assert settings["attribution"] == {"commit": "", "pr": ""}


class TestClaudeWrapper:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_wrapper_created(self, mock_which, mock_call, tmp_path) -> None:
        """The claude-wrapper.sh file is created in .ralphex/."""
        _write_goga_yml(tmp_path)
        _run_build_in_tmp(tmp_path, ["plan.md"])

        wrapper_path = tmp_path / ".ralphex" / "claude-wrapper.sh"
        assert wrapper_path.is_file()

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_wrapper_content(self, mock_which, mock_call, tmp_path) -> None:
        """The claude-wrapper.sh has the correct shebang and content."""
        _write_goga_yml(tmp_path)
        _run_build_in_tmp(tmp_path, ["plan.md"])

        wrapper_path = tmp_path / ".ralphex" / "claude-wrapper.sh"
        content = wrapper_path.read_text()
        assert content == CLAUDE_WRAPPER_SCRIPT

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_wrapper_is_executable(self, mock_which, mock_call, tmp_path) -> None:
        """The claude-wrapper.sh file has execute permission."""
        _write_goga_yml(tmp_path)
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
        _write_goga_yml(tmp_path)
        _run_build_in_tmp(tmp_path, ["plan.md"])

        prompts_dir = tmp_path / ".ralphex" / "prompts"
        assert prompts_dir.is_dir()
        expected_files = {"task.txt", "codex.txt", "review_first.txt", "review_second.txt"}
        actual_files = {f.name for f in prompts_dir.iterdir() if f.is_file()}
        assert expected_files.issubset(actual_files)

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_agents_copied(self, mock_which, mock_call, tmp_path) -> None:
        """Default agent files are copied to .ralphex/agents/."""
        _write_goga_yml(tmp_path)
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
        _write_goga_yml(tmp_path)
        ralphex_prompts = tmp_path / ".ralphex" / "prompts"
        ralphex_prompts.mkdir(parents=True)
        existing_file = ralphex_prompts / "task.txt"
        existing_file.write_text("ORIGINAL CONTENT DO NOT OVERWRITE")

        _run_build_in_tmp(tmp_path, ["plan.md"])

        assert existing_file.read_text() != "ORIGINAL CONTENT DO NOT OVERWRITE"
        expected_files = {"task.txt", "codex.txt", "review_first.txt", "review_second.txt"}
        actual_files = {f.name for f in ralphex_prompts.iterdir() if f.is_file()}
        assert expected_files.issubset(actual_files)

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_defaults_subdir_empty_no_error(self, mock_which, mock_call, tmp_path) -> None:
        """Empty prompts/ and agents/ subdirectories under defaults_dir cause no error."""
        _write_goga_yml(tmp_path)
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
        _write_goga_yml(tmp_path)
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
        _write_goga_yml(tmp_path)
        _run_build_in_tmp(tmp_path, ["plan.md"])

        prompts_dir = tmp_path / ".ralphex" / "prompts"
        modified_file = prompts_dir / "task.txt"
        modified_file.write_text("USER MODIFICATION BETWEEN RUNS")

        _run_build_in_tmp(tmp_path, ["plan.md"])

        assert modified_file.read_text() != "USER MODIFICATION BETWEEN RUNS"


class TestDefaultsDirNotFound:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_defaults_dir_not_found_exits_with_error(self, mock_which, mock_call, tmp_path) -> None:
        """When defaults directory is missing, build exits with code 1 and error."""
        _write_goga_yml(tmp_path)
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
        _write_goga_yml(tmp_path)
        with mock.patch.object(shutil, "which", return_value=None):
            result = _run_build_in_tmp(tmp_path, ["plan.md"])

        assert "ralphex not found in PATH" in result.output

    def test_exit_code_one(self, tmp_path) -> None:
        """When ralphex is not found, exit code is 1."""
        _write_goga_yml(tmp_path)
        with mock.patch.object(shutil, "which", return_value=None):
            result = _run_build_in_tmp(tmp_path, ["plan.md"])

        assert result.exit_code == 1


class TestRalphexExecution:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_subprocess_called(self, mock_which, mock_call, tmp_path) -> None:
        """subprocess.call is invoked with the assembled ralphex command."""
        _write_goga_yml(tmp_path)
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
        _write_goga_yml(tmp_path)
        result = _run_build_in_tmp(tmp_path, ["plan.md"])
        assert result.exit_code == 0

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_custom_plan_passed(self, mock_which, mock_call, tmp_path) -> None:
        """A custom plan argument is forwarded to the ralphex command."""
        _write_goga_yml(tmp_path)
        _run_build_in_tmp(tmp_path, ["my-plan.md"])

        cmd = mock_call.call_args[0][0]
        assert "my-plan.md" in cmd

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_worktree_flag_forwarded(self, mock_which, mock_call, tmp_path) -> None:
        """The --worktree CLI flag is forwarded to ralphex."""
        _write_goga_yml(tmp_path)
        _run_build_in_tmp(tmp_path, ["plan.md", "--worktree"])

        cmd = mock_call.call_args[0][0]
        assert "--worktree" in cmd

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_skip_finalize_flag_forwarded(self, mock_which, mock_call, tmp_path) -> None:
        """The --skip-finalize CLI flag is forwarded to ralphex."""
        _write_goga_yml(tmp_path)
        _run_build_in_tmp(tmp_path, ["plan.md", "--skip-finalize"])

        cmd = mock_call.call_args[0][0]
        assert "--skip-finalize" in cmd

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_session_timeout_forwarded(self, mock_which, mock_call, tmp_path) -> None:
        """The --session-timeout CLI option is forwarded to ralphex."""
        _write_goga_yml(tmp_path)
        _run_build_in_tmp(tmp_path, ["plan.md", "--session-timeout", "30m"])

        cmd = mock_call.call_args[0][0]
        assert "--session-timeout" in cmd
        assert "30m" in cmd

    @mock.patch.object(subprocess, "call", return_value=42)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_nonzero_exit_propagated(self, mock_which, mock_call, tmp_path) -> None:
        """Non-zero ralphex return code is propagated as exit code."""
        _write_goga_yml(tmp_path)
        result = _run_build_in_tmp(tmp_path, ["plan.md"])
        assert result.exit_code == 42


class TestWrapperScriptEnvVariable:
    def test_wrapper_script_uses_anthropic_api_token(self) -> None:
        """Wrapper script constant contains ANTHROPIC_API_TOKEN, not ZAI_TOKEN."""
        assert "ANTHROPIC_API_TOKEN" in CLAUDE_WRAPPER_SCRIPT
        assert "ZAI_TOKEN" not in CLAUDE_WRAPPER_SCRIPT


class TestCodexEnabled:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_default_false_in_config(self, mock_which, mock_call, tmp_path) -> None:
        """Without codex_review in .goga/config.yml, codex_enabled defaults to false."""
        _write_goga_yml(tmp_path)
        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in config_content

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_true_from_goga_config(self, mock_which, mock_call, tmp_path) -> None:
        """.goga/config.yml with codex_review: true writes codex_enabled = true to config."""
        _write_goga_yml(tmp_path, extra={"codex_review": True})
        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = true" in config_content

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_overwritten_on_rerun(self, mock_which, mock_call, tmp_path) -> None:
        """Existing codex_enabled value is overwritten by new .goga/config.yml value."""
        _write_goga_yml(tmp_path, extra={"codex_review": False})
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "config").write_text("codex_enabled = true\n")

        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (ralphex_dir / "config").read_text()
        assert "codex_enabled = false" in config_content
        assert "codex_enabled = true" not in config_content
        assert "claude_command = .ralphex/claude-wrapper.sh" in config_content

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_false_explicit(self, mock_which, mock_call, tmp_path) -> None:
        """Explicit codex_review: false writes false to config."""
        _write_goga_yml(tmp_path, extra={"codex_review": False})
        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in config_content

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_overwrite_preserves_other_keys(self, mock_which, mock_call, tmp_path) -> None:
        """Overwriting codex_enabled preserves other custom keys."""
        _write_goga_yml(tmp_path, extra={"codex_review": True})
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "config").write_text("custom_key = custom_value\ncodex_enabled = false\n")

        _run_build_in_tmp(tmp_path, ["plan.md"])

        config_content = (ralphex_dir / "config").read_text()
        assert "codex_enabled = true" in config_content
        assert "custom_key = custom_value" in config_content

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_enabled_overwrite_preserves_comments(self, mock_which, mock_call, tmp_path) -> None:
        """Overwriting codex_enabled preserves comment lines."""
        _write_goga_yml(tmp_path, extra={"codex_review": False})
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "config").write_text(
            "# ralphex settings\ncodex_enabled = true\n# other\ncustom_key = val\n"
            "claude_command = .ralphex/claude-wrapper.sh\n"
            "claude_args = --dangerously-skip-permissions --output-format stream-json --verbose\n"
        )

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


def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with user config in the given path."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)


class TestManifestCheck:
    def test_manifest_check_all_committed_proceeds(self, tmp_path) -> None:
        """When all CODEMANIFEST files are committed, build proceeds normally."""
        _write_goga_yml(tmp_path)
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
        _write_goga_yml(tmp_path)
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
        _write_goga_yml(tmp_path)
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
        _write_goga_yml(tmp_path)
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("content")

        result = _run_build_in_tmp(tmp_path, ["plan.md"], skip_manifest_check=False)

        assert result.exit_code == 1
        assert "Error: Uncommitted CODEMANIFEST files found:" in result.output

    def test_manifest_check_staged_not_committed_exit_1(self, tmp_path) -> None:
        """Staged but not committed CODEMANIFEST causes exit 1."""
        _write_goga_yml(tmp_path)
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("content")
        subprocess.run(["git", "add", "CODEMANIFEST"], cwd=tmp_path, capture_output=True, check=True)

        result = _run_build_in_tmp(tmp_path, ["plan.md"], skip_manifest_check=False)

        assert result.exit_code == 1
        assert "Error: Uncommitted CODEMANIFEST files found:" in result.output

    def test_manifest_check_not_git_repo_exit_1(self, tmp_path) -> None:
        """When not in a git repo, build exits with code 1."""
        _write_goga_yml(tmp_path)
        result = _run_build_in_tmp(tmp_path, ["plan.md"], skip_manifest_check=False)

        assert result.exit_code == 1
        assert "git status failed" in result.output

    def test_manifest_check_no_codemanifest_files_proceeds(self, tmp_path) -> None:
        """Empty repo with no CODEMANIFEST files proceeds normally."""
        _write_goga_yml(tmp_path)
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
        _write_goga_yml(tmp_path)
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


class TestBuildNegativeCases:
    def test_build_invalid_goga_config_raises_config_error(self, tmp_path) -> None:
        """Invalid .goga/config.yml (missing required field) causes exit code 1."""
        data = {
            "build": {"task_executor": {"agent": "claude"}},
        }
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(yaml.dump(data))

        result = _run_build_in_tmp(tmp_path, ["plan.md"])
        assert result.exit_code == 1
        assert "is required in .goga/config.yml" in result.output or "must be" in result.output

    def test_build_invalid_existing_settings_json_raises_error(self, tmp_path) -> None:
        """Invalid JSON in existing .claude/settings.json causes non-zero exit with error."""
        _write_goga_yml(tmp_path)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text("{broken json")

        result = _run_build_in_tmp(tmp_path, ["plan.md"])
        assert result.exit_code != 0
        assert "Invalid JSON" in result.output or "settings.json" in result.output


class TestBuildConfigFlags:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_build_worktree_from_config_when_no_cli_flag(self, mock_which, mock_call, tmp_path) -> None:
        """worktree: true in .goga/config.yml adds --worktree to command without CLI flag."""
        _write_goga_yml(tmp_path, extra={"worktree": True})
        _run_build_in_tmp(tmp_path, ["plan.md"])

        cmd = mock_call.call_args[0][0]
        assert "--worktree" in cmd

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_build_cli_worktree_overrides_config(self, mock_which, mock_call, tmp_path) -> None:
        """--worktree CLI flag overrides worktree: false in config."""
        _write_goga_yml(tmp_path, extra={"worktree": False})
        _run_build_in_tmp(tmp_path, ["plan.md", "--worktree"])

        cmd = mock_call.call_args[0][0]
        assert "--worktree" in cmd

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_build_custom_prompts_dir_from_config(self, mock_which, mock_call, tmp_path) -> None:
        """Custom prompts_dir and agents_dir from config copy files to .ralphex/."""
        custom_prompts = tmp_path / "custom" / "prompts"
        custom_agents = tmp_path / "custom" / "agents"
        custom_prompts.mkdir(parents=True)
        custom_agents.mkdir(parents=True)
        (custom_prompts / "custom_task.txt").write_text("custom task content")
        (custom_agents / "custom_agent.txt").write_text("custom agent content")

        _write_goga_yml(
            tmp_path,
            extra={"prompts_dir": str(custom_prompts), "agents_dir": str(custom_agents)},
        )
        _run_build_in_tmp(tmp_path, ["plan.md"])

        assert (tmp_path / ".ralphex" / "prompts" / "custom_task.txt").is_file()
        assert (tmp_path / ".ralphex" / "agents" / "custom_agent.txt").is_file()
        assert (
            (tmp_path / ".ralphex" / "prompts" / "custom_task.txt").read_text()
            == "custom task content"
        )
