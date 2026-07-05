from __future__ import annotations

import inspect
import shutil
import subprocess
from pathlib import Path
from unittest import mock

from goga.build.build import (
    _assemble_command,
    _copy_defaults,
    _parse_porcelain_path,
    _unquote_git_path,
    _write_ralphex_config,
    build,
)
from goga.config import BuildConfig, Config, PipelineConfig, TaskExecutorConfig

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
    task_executor = TaskExecutorConfig(agent=agent, env=env or {})
    build = BuildConfig(task_executor=task_executor, **build_kwargs)
    return Config(
        lang="python",
        image="goga:latest",
        build=build,
        pipeline=PipelineConfig(agent="claude"),
    )


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


class TestBuildContract:
    def test_build_signature_is_plan_config_cli_options(self) -> None:
        sig = inspect.signature(build)
        assert list(sig.parameters) == ["plan", "config", "cli_options"]

    def test_build_returns_int_annotation(self) -> None:
        sig = inspect.signature(build)
        # `from __future__ import annotations` defers annotations to strings,
        # so the return annotation is the string "int".
        assert sig.return_annotation in ("int", int)

    def test_make_config_uses_task_executor_config_not_task_executor(self) -> None:
        config = _make_config()
        # TaskExecutorConfig is the renamed class; the old TaskExecutor must
        # no longer be the type carried on BuildConfig.task_executor.
        assert isinstance(config.build.task_executor, TaskExecutorConfig)
        assert not hasattr(config.build, "image")
        assert config.image == "goga:latest"


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


# --- Ralphex config writer tests ---


class TestWriteRalphexConfig:
    def test_writes_resolved_wrapper_to_claude_command(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(agent="codex")

        _write_ralphex_config(config, "/home/goga/bin/codex-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "claude_command = /home/goga/bin/codex-as-claude.sh" in config_text

    def test_writes_claude_args_default(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config()

        _write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "claude_args = --dangerously-skip-permissions --output-format stream-json --verbose" in config_text

    def test_codex_enabled_false_by_default(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config()

        _write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in config_text

    def test_codex_review_true_maps_to_codex_enabled_true(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(codex_review=True)

        _write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = true" in config_text

    def test_does_not_write_codex_specific_keys(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(agent="codex")

        _write_ralphex_config(config, "/home/goga/bin/codex-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "executor" not in config_text
        assert "codex_command" not in config_text
        assert "codex_sandbox" not in config_text
        assert "codex_reasoning_effort" not in config_text

    def test_does_not_generate_wrapper_scripts(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(agent="claude")

        _write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")

        ralphex_dir = tmp_path / ".ralphex"
        entries = {p.name for p in ralphex_dir.iterdir()}
        assert entries == {"config"}

    def test_overwrites_stale_config_without_merging(self, tmp_path, monkeypatch) -> None:
        """A pre-existing .ralphex/config is overwritten, not merged into."""
        monkeypatch.chdir(tmp_path)
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "config").write_text("stale_key = stale_value\nclaude_command = OLD_PATH\n")

        config = _make_config(agent="codex")
        _write_ralphex_config(config, "/home/goga/bin/codex-as-claude.sh")

        config_text = (ralphex_dir / "config").read_text()
        assert "stale_key" not in config_text
        assert "OLD_PATH" not in config_text
        keys = {line.split(" = ", 1)[0] for line in config_text.strip().splitlines() if " = " in line}
        assert keys == {"claude_command", "claude_args", "codex_enabled"}

    def test_codex_review_none_maps_to_codex_enabled_false(self, tmp_path, monkeypatch) -> None:
        """An explicit codex_review=None still renders codex_enabled = false."""
        monkeypatch.chdir(tmp_path)
        config = _make_config(codex_review=None)

        _write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in config_text


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


class TestBuildEnvDelivery:
    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_env_passed_to_subprocess(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("PARENT_VAR", "parent_val")
        config = _make_config(env=TEST_ENV_VARS)
        result = _run_build_in_tmp(
            tmp_path,
            monkeypatch,
            config=config,
            cli_options={"skip_manifest_check": True},
        )
        assert result == 0

        passed_env = mock_call.call_args.kwargs["env"]
        for key, value in TEST_ENV_VARS.items():
            assert passed_env[key] == value
        assert passed_env["PARENT_VAR"] == "parent_val"
        assert "PATH" in passed_env

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_build_env_overrides_os_environ(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://host.example")
        config = _make_config(env={"ANTHROPIC_BASE_URL": "https://build.example"})
        _run_build_in_tmp(
            tmp_path,
            monkeypatch,
            config=config,
            cli_options={"skip_manifest_check": True},
        )

        passed_env = mock_call.call_args.kwargs["env"]
        assert passed_env["ANTHROPIC_BASE_URL"] == "https://build.example"

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_does_not_write_claude_settings(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        config = _make_config(env=TEST_ENV_VARS)
        _run_build_in_tmp(
            tmp_path,
            monkeypatch,
            config=config,
            cli_options={"skip_manifest_check": True},
        )

        assert not (tmp_path / ".claude" / "settings.json").exists()


class TestBuildArbitraryAgent:
    def test_arbitrary_agent_resolves_and_proceeds(self, tmp_path, monkeypatch) -> None:
        config = _make_config(agent="gemini")
        result = _run_build_in_tmp(
            tmp_path,
            monkeypatch,
            config=config,
            cli_options={"dry_run": True, "skip_manifest_check": True},
        )
        assert result == 0
        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "claude_command = /home/goga/bin/gemini-as-claude.sh" in config_text


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
