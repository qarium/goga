from __future__ import annotations

import json
import shutil
import stat
import subprocess
from pathlib import Path
from unittest import mock

import pytest
from goga.build.build import (
    CLAUDE_WRAPPER_SCRIPT,
    _assemble_command,
    _copy_defaults,
    _create_claude_settings,
    _create_claude_wrapper,
    _parse_porcelain_path,
    _run_precondition,
    _unquote_git_path,
    build,
)
from goga.config import BuildConfig, Config, TaskExecutor

TEST_ENV_VARS = {
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.7",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5-turbo",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.1",
    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
}


def _make_config(
    agent: str = "claude",
    env: dict | None = None,
    **build_kwargs,
) -> Config:
    task_executor = TaskExecutor(agent=agent, env=env or {})
    build = BuildConfig(task_executor=task_executor, image="goga:latest", **build_kwargs)
    return Config(lang="python", build=build)


def _run_build_in_tmp(
    tmp_path: Path,
    monkeypatch,
    plan: str = "plan.md",
    cli_options: dict | None = None,
    config: Config | None = None,
) -> int:
    monkeypatch.chdir(tmp_path)
    if config is None:
        config = _make_config()
    result = build(plan, config, cli_options or {})
    return result


# --- Helper tests ---


class TestUnquoteGitPath:
    def test_unquoted(self) -> None:
        assert _unquote_git_path("foo/bar.txt") == "foo/bar.txt"

    def test_quoted(self) -> None:
        assert _unquote_git_path('"hello world.txt"') == "hello world.txt"

    def test_double_backslash_replacement(self) -> None:
        assert _unquote_git_path('"hello\\\\world"') == "hello\\world"

    def test_unclosed_quote(self) -> None:
        assert _unquote_git_path('"no end') is None


class TestParsePorcelainPath:
    def test_simple_path(self) -> None:
        assert _parse_porcelain_path("M  file.txt") == "file.txt"

    def test_quoted_path(self) -> None:
        assert _parse_porcelain_path('M  "hello world.txt"') == "hello world.txt"

    def test_rename_entry(self) -> None:
        assert _parse_porcelain_path("R  old.txt -> new.txt") == "new.txt"

    def test_too_short(self) -> None:
        assert _parse_porcelain_path("X") is None

    def test_empty_after_prefix(self) -> None:
        assert _parse_porcelain_path("M  ") is None


# --- Precondition tests ---


class TestRunPrecondition:
    def test_claude_agent_succeeds(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(agent="claude")
        assert _run_precondition(config) == 0

    def test_codex_agent_succeeds(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(agent="codex")
        assert _run_precondition(config) == 0

    def test_codex_agent_no_claude_settings(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(agent="codex")
        assert _run_precondition(config) == 0
        assert not (tmp_path / ".claude").exists()

    def test_cleanup_ralphex_dir_for_claude(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "old_config").write_text("stale")
        config = _make_config(agent="claude")
        assert _run_precondition(config) == 0
        assert not (ralphex_dir / "old_config").exists()

    def test_cleanup_ralphex_dir_for_codex(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "old_config").write_text("stale")
        config = _make_config(agent="codex")
        assert _run_precondition(config) == 0
        assert not ralphex_dir.exists()

    def test_cleanup_ralphex_dir_no_dir(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(agent="codex")
        assert _run_precondition(config) == 0

    def test_unsupported_agent_returns_1(self, tmp_path, monkeypatch) -> None:
        config = _make_config(agent="gemini")
        assert _run_precondition(config) == 1


class TestCreateClaudeSettings:
    def test_creates_settings_json(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(env=TEST_ENV_VARS)
        _create_claude_settings(config)

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        for key, value in TEST_ENV_VARS.items():
            assert settings["env"][key] == value
        assert settings["attribution"] == {"commit": "", "pr": ""}

    def test_empty_env_creates_empty_section(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config()
        _create_claude_settings(config)

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert settings["env"] == {}
        assert settings["attribution"] == {"commit": "", "pr": ""}

    def test_merge_preserves_existing_fields(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        existing = {"custom_field": "preserved", "env": {"EXISTING_VAR": "val"}}
        (claude_dir / "settings.json").write_text(json.dumps(existing))

        config = _make_config(env={"NEW_VAR": "new_val"})
        _create_claude_settings(config)

        settings = json.loads((claude_dir / "settings.json").read_text())
        assert settings["custom_field"] == "preserved"
        assert settings["env"]["EXISTING_VAR"] == "val"
        assert settings["env"]["NEW_VAR"] == "new_val"

    def test_invalid_json_raises_runtime_error(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text("{broken json")

        config = _make_config()
        with pytest.raises(RuntimeError, match="Invalid JSON"):
            _create_claude_settings(config)


class TestCreateClaudeWrapper:
    def test_wrapper_created(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config()
        _create_claude_wrapper(config)

        wrapper_path = tmp_path / ".ralphex" / "claude-wrapper.sh"
        assert wrapper_path.is_file()
        assert wrapper_path.read_text() == CLAUDE_WRAPPER_SCRIPT

    def test_wrapper_is_executable(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config()
        _create_claude_wrapper(config)

        wrapper_path = tmp_path / ".ralphex" / "claude-wrapper.sh"
        mode = wrapper_path.stat().st_mode
        assert mode & stat.S_IXUSR
        assert mode & stat.S_IXGRP
        assert mode & stat.S_IXOTH

    def test_config_defaults_added(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config()
        _create_claude_wrapper(config)

        config_content = (tmp_path / ".ralphex" / "config").read_text()
        assert "claude_command = .ralphex/claude-wrapper.sh" in config_content
        assert "codex_enabled = false" in config_content

    def test_codex_enabled_true(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(codex_review=True)
        _create_claude_wrapper(config)

        config_content = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = true" in config_content

    def test_codex_overwrites_existing(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "config").write_text("codex_enabled = true\n")

        config = _make_config(codex_review=False)
        _create_claude_wrapper(config)

        config_content = (ralphex_dir / "config").read_text()
        assert "codex_enabled = false" in config_content
        assert config_content.count("codex_enabled") == 1

    def test_preserves_comments_and_custom_keys(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "config").write_text(
            "# ralphex settings\ncodex_enabled = true\n# other\ncustom_key = val\n"
            "claude_command = .ralphex/claude-wrapper.sh\n"
            "claude_args = --dangerously-skip-permissions --output-format stream-json --verbose\n"
        )

        config = _make_config(codex_review=False)
        _create_claude_wrapper(config)

        config_content = (ralphex_dir / "config").read_text()
        lines = config_content.strip().splitlines()
        assert "# ralphex settings" in lines
        assert "codex_enabled = false" in lines
        assert "# other" in lines
        assert "custom_key = val" in lines


class TestCopyDefaults:
    def test_prompts_copied(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config()
        assert _copy_defaults(config) == 0

        prompts_dir = tmp_path / ".ralphex" / "prompts"
        assert prompts_dir.is_dir()
        expected = {"task.txt", "codex.txt", "review_first.txt", "review_second.txt"}
        actual = {f.name for f in prompts_dir.iterdir() if f.is_file()}
        assert expected.issubset(actual)

    def test_agents_copied(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config()
        assert _copy_defaults(config) == 0

        agents_dir = tmp_path / ".ralphex" / "agents"
        assert agents_dir.is_dir()
        expected = {
            "quality.txt",
            "implementation.txt",
            "testing.txt",
            "simplification.txt",
            "documentation.txt",
        }
        actual = {f.name for f in agents_dir.iterdir() if f.is_file()}
        assert expected.issubset(actual)

    def test_overwrites_existing(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        prompts_dir = tmp_path / ".ralphex" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "task.txt").write_text("ORIGINAL")

        config = _make_config()
        _copy_defaults(config)

        assert (prompts_dir / "task.txt").read_text() != "ORIGINAL"

    def test_defaults_dir_not_found_returns_1(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config()
        with mock.patch("goga.build.build.DEFAULTS_PACKAGE_DIR", Path("/nonexistent")):
            assert _copy_defaults(config) == 1

    def test_empty_defaults_subdirs_no_error(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        fake_defaults = tmp_path / "fake_defaults"
        (fake_defaults / "prompts").mkdir(parents=True)
        (fake_defaults / "agents").mkdir(parents=True)

        config = _make_config()
        with mock.patch("goga.build.build.DEFAULTS_PACKAGE_DIR", fake_defaults):
            assert _copy_defaults(config) == 0

    def test_custom_prompts_dir(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        custom_prompts = tmp_path / "custom" / "prompts"
        custom_prompts.mkdir(parents=True)
        (custom_prompts / "custom_task.txt").write_text("custom content")

        config = _make_config(prompts_dir=str(custom_prompts))
        assert _copy_defaults(config) == 0

        assert (tmp_path / ".ralphex" / "prompts" / "custom_task.txt").is_file()
        assert (tmp_path / ".ralphex" / "prompts" / "custom_task.txt").read_text() == "custom content"


class TestAssembleCommand:
    def test_basic_command(self) -> None:
        config = _make_config()
        cmd = _assemble_command("plan.md", config, {})
        assert cmd == ["ralphex", "plan.md", "--config-dir", ".ralphex/"]

    def test_worktree_flag_from_cli(self) -> None:
        config = _make_config()
        cmd = _assemble_command("plan.md", config, {"worktree": True})
        assert "--worktree" in cmd

    def test_worktree_flag_from_config(self) -> None:
        config = _make_config(worktree=True)
        cmd = _assemble_command("plan.md", config, {})
        assert "--worktree" in cmd

    def test_session_timeout_from_cli(self) -> None:
        config = _make_config()
        cmd = _assemble_command("plan.md", config, {"session_timeout": "30m"})
        assert "--session-timeout" in cmd
        assert "30m" in cmd

    def test_cli_overrides_config(self) -> None:
        config = _make_config(worktree=False)
        cmd = _assemble_command("plan.md", config, {"worktree": True})
        assert "--worktree" in cmd

    def test_max_iterations_forwarded(self) -> None:
        config = _make_config()
        cmd = _assemble_command("plan.md", config, {"max_iterations": 10})
        assert "--max-iterations" in cmd
        assert "10" in cmd

    def test_skip_finalize_flag(self) -> None:
        config = _make_config()
        cmd = _assemble_command("plan.md", config, {"skip_finalize": True})
        assert "--skip-finalize" in cmd

    def test_codex_flag_when_codex_agent(self) -> None:
        config = _make_config(agent="codex")
        cmd = _assemble_command("plan.md", config, {})
        assert "--codex" in cmd

    def test_no_codex_flag_when_claude_agent(self) -> None:
        config = _make_config(agent="claude")
        cmd = _assemble_command("plan.md", config, {})
        assert "--codex" not in cmd


# --- Full build function tests ---


class TestBuildDryRun:
    def test_dry_run_returns_0(self, tmp_path, monkeypatch) -> None:
        result = _run_build_in_tmp(
            tmp_path,
            monkeypatch,
            cli_options={"dry_run": True, "skip_manifest_check": True},
        )
        assert result == 0

    def test_dry_run_does_not_call_subprocess(self, tmp_path, monkeypatch) -> None:
        with mock.patch.object(subprocess, "call") as mock_call:
            _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                cli_options={"dry_run": True, "skip_manifest_check": True},
            )
            mock_call.assert_not_called()


class TestBuildFullExecution:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_full_execution_returns_0(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": True})
        assert result == 0

    @mock.patch.object(subprocess, "call", return_value=42)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_propagates_exit_code(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": True})
        assert result == 42


class TestBuildEnvVarsInSettings:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_env_vars_in_settings_json(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        config = _make_config(env=TEST_ENV_VARS)
        result = _run_build_in_tmp(
            tmp_path,
            monkeypatch,
            config=config,
            cli_options={"skip_manifest_check": True},
        )
        assert result == 0

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        for key, value in TEST_ENV_VARS.items():
            assert settings["env"][key] == value
        assert settings["attribution"] == {"commit": "", "pr": ""}


class TestBuildUnsupportedAgent:
    def test_unsupported_agent_returns_1(self, tmp_path, monkeypatch) -> None:
        config = _make_config(agent="gemini")
        result = _run_build_in_tmp(
            tmp_path,
            monkeypatch,
            config=config,
            cli_options={"skip_manifest_check": True},
        )
        assert result == 1


class TestBuildCodexAgent:
    def test_codex_dry_run_returns_0(self, tmp_path, monkeypatch) -> None:
        result = _run_build_in_tmp(
            tmp_path,
            monkeypatch,
            config=_make_config(agent="codex"),
            cli_options={"dry_run": True, "skip_manifest_check": True},
        )
        assert result == 0

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_flag_in_full_build(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        config = _make_config(agent="codex")
        _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options={"skip_manifest_check": True})

        cmd = mock_call.call_args[0][0]
        assert "--codex" in cmd

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_codex_no_claude_settings(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        config = _make_config(agent="codex")
        _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options={"skip_manifest_check": True})

        assert not (tmp_path / ".claude").exists()


class TestBuildMissingRalphex:
    def test_ralphex_not_found_returns_1(self, tmp_path, monkeypatch) -> None:
        with mock.patch.object(shutil, "which", return_value=None):
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                cli_options={"skip_manifest_check": True},
            )
            assert result == 1


class TestBuildDefaultsDirNotFound:
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    @mock.patch.object(subprocess, "call", return_value=0)
    def test_defaults_missing_returns_1(self, mock_call, mock_which, tmp_path, monkeypatch) -> None:
        with mock.patch("goga.build.build.DEFAULTS_PACKAGE_DIR", Path("/nonexistent")):
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                cli_options={"skip_manifest_check": True},
            )
            assert result == 1


class TestBuildRepeatedBuild:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_repeated_build_overwrites(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        cli_options = {"skip_manifest_check": True}
        _run_build_in_tmp(tmp_path, monkeypatch, cli_options=cli_options)

        prompts_dir = tmp_path / ".ralphex" / "prompts"
        modified_file = prompts_dir / "task.txt"
        modified_file.write_text("USER MODIFICATION")

        _run_build_in_tmp(tmp_path, monkeypatch, cli_options=cli_options)
        assert modified_file.read_text() != "USER MODIFICATION"


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)


class TestManifestCheck:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_all_committed_proceeds(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("content")
        subprocess.run(["git", "add", "CODEMANIFEST"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)

        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={})
        assert result == 0

    def test_uncommitted_manifest_returns_1(self, tmp_path, monkeypatch) -> None:
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("content")

        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={})
        assert result == 1

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_skip_manifest_check(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("content")

        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": True})
        assert result == 0

    def test_not_git_repo_returns_1(self, tmp_path, monkeypatch) -> None:
        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={})
        assert result == 1

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_no_codemanifest_files_proceeds(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / ".gitkeep").write_text("")
        subprocess.run(["git", "add", ".gitkeep"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)

        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={})
        assert result == 0

    def test_multiple_uncommitted_lists_all(self, tmp_path, monkeypatch) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / ".gitkeep").write_text("")
        subprocess.run(["git", "add", ".gitkeep"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)
        for d in ("a", "b", "c"):
            subdir = tmp_path / d
            subdir.mkdir()
            (subdir / "CODEMANIFEST").write_text(f"content {d}")

        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={})
        assert result == 1


class TestBuildNegativeCases:
    def test_invalid_settings_json_returns_nonzero(self, tmp_path, monkeypatch) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text("{broken json")

        result = _run_build_in_tmp(
            tmp_path,
            monkeypatch,
            cli_options={"skip_manifest_check": True},
        )
        assert result != 0


class TestBuildConfigFlags:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_worktree_from_config(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        config = _make_config(worktree=True)
        _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options={"skip_manifest_check": True})

        cmd = mock_call.call_args[0][0]
        assert "--worktree" in cmd

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_cli_worktree_overrides_config(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        config = _make_config(worktree=False)
        _run_build_in_tmp(
            tmp_path,
            monkeypatch,
            config=config,
            cli_options={"worktree": True, "skip_manifest_check": True},
        )

        cmd = mock_call.call_args[0][0]
        assert "--worktree" in cmd

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_custom_prompts_dir(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        custom_prompts = tmp_path / "custom" / "prompts"
        custom_prompts.mkdir(parents=True)
        (custom_prompts / "custom_task.txt").write_text("custom content")

        config = _make_config(prompts_dir=str(custom_prompts))
        _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options={"skip_manifest_check": True})

        assert (tmp_path / ".ralphex" / "prompts" / "custom_task.txt").is_file()
        assert (tmp_path / ".ralphex" / "prompts" / "custom_task.txt").read_text() == "custom content"
