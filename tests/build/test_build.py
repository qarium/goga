from __future__ import annotations

import inspect
import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

from goga.build.build import (
    _copy_defaults,
    _parse_porcelain_path,
    _resolve_options,
    _unquote_git_path,
    _write_ralphex_config,
    build,
)
from goga.config import BuildConfig, PipelineConfig, ProjectConfig, TaskExecutorConfig

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
) -> ProjectConfig:
    task_executor = TaskExecutorConfig(agent=agent, env=env or {})
    build = BuildConfig(task_executor=task_executor, **build_kwargs)
    return ProjectConfig(
        lang="python",
        image="goga:latest",
        dockerfile=None,
        build=build,
        pipeline=PipelineConfig(agent="claude"),
    )


def _run_build_in_tmp(
    tmp_path: Path,
    monkeypatch,
    plan: str = "plan.md",
    cli_options: dict | None = None,
    config: ProjectConfig | None = None,
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


class TestResolveOptions:
    def test_resolve_options_cli_overrides_config_scalar(self) -> None:
        # CLI present wins over BuildConfig for scalar keys.
        resolved = _resolve_options(_make_config(max_iterations=5), {"max_iterations": 10})
        assert resolved["max_iterations"] == 10

    def test_resolve_options_bool_false_defers_to_config(self) -> None:
        # store_true nuance: a CLI False is "not set" -> defer to config.
        resolved = _resolve_options(_make_config(worktree=True), {"worktree": False})
        assert resolved["worktree"] is True

    def test_resolve_options_config_value_when_cli_absent(self) -> None:
        # No CLI value -> fall back to BuildConfig.
        resolved = _resolve_options(_make_config(worktree=True), {})
        assert resolved["worktree"] is True

    def test_resolve_options_omits_when_config_none(self) -> None:
        # With neither CLI nor config set, the resolved values carry the omit
        # semantics through to run_ralphex (bool False, scalar None).
        resolved = _resolve_options(_make_config(), {})
        assert resolved["worktree"] is False
        assert resolved["skip_finalize"] is False
        assert resolved["session_timeout"] is None
        assert resolved["max_iterations"] is None


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
        assert keys == {
            "claude_command",
            "claude_args",
            "codex_enabled",
            "preserve_anthropic_api_key",
        }

    def test_codex_review_none_maps_to_codex_enabled_false(self, tmp_path, monkeypatch) -> None:
        """An explicit codex_review=None still renders codex_enabled = false."""
        monkeypatch.chdir(tmp_path)
        config = _make_config(codex_review=None)

        _write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in config_text

    def test_writes_preserve_anthropic_api_key_true(self, tmp_path, monkeypatch) -> None:
        """preserve_anthropic_api_key is pinned to true so ralphex keeps ANTHROPIC_API_KEY."""
        monkeypatch.chdir(tmp_path)
        config = _make_config()

        _write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "preserve_anthropic_api_key = true" in config_text


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


# --- Full build function tests ---


class TestBuildDryRun:
    """build() delegates dry_run to run_ralphex (the dry-run short-circuit now lives
    in run_ralphex, not in build). These verify the delegation seam directly rather
    than the internal subprocess call run_ralphex would make."""

    def test_dry_run_returns_0(self, tmp_path, monkeypatch) -> None:
        with mock.patch("goga.build.build.run_ralphex", return_value=0):
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                cli_options={"dry_run": True, "skip_manifest_check": True},
            )
        assert result == 0

    def test_dry_run_passes_dry_run_to_run_ralphex(self, tmp_path, monkeypatch) -> None:
        with mock.patch("goga.build.build.run_ralphex", return_value=0) as mock_run:
            _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                cli_options={"dry_run": True, "skip_manifest_check": True},
            )
        # dry_run reaches run_ralphex as the positional 3rd arg.
        assert mock_run.call_args.args[2] is True


class TestBuildDelegation:
    """build() delegates the ralphex launch to run_ralphex with resolved options."""

    def test_build_delegates_to_run_ralphex_with_resolved_options(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        with mock.patch("goga.build.build.run_ralphex", return_value=0) as mock_run:
            result = build("plan.md", _make_config(worktree=True), {"skip_manifest_check": True})

        assert result == 0
        mock_run.assert_called_once()
        args = mock_run.call_args.args
        assert args[0] == "plan.md"
        assert args[1]["worktree"] is True
        assert args[2] is False  # dry_run positional
        assert "dry_run" not in args[1]

    def test_build_returns_run_ralphex_exit_code(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        with mock.patch("goga.build.build.run_ralphex", return_value=42) as mock_run:
            result = build("plan.md", _make_config(), {"skip_manifest_check": True})

        assert result == 42
        assert mock_run.return_value == 42

    def test_build_dry_run_delegates_with_dry_run_true(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        with mock.patch("goga.build.build.run_ralphex", return_value=0) as mock_run:
            build("plan.md", _make_config(), {"dry_run": True, "skip_manifest_check": True})

        assert mock_run.call_args.args[2] is True


class TestBuildFullExecution:
    """build() returns whatever run_ralphex returns — mocked at the delegation seam
    rather than at run_ralphex's internal subprocess.call, decoupling the build test
    from ralphex internals."""

    @mock.patch("goga.build.build.run_ralphex", return_value=0)
    def test_full_execution_returns_0(self, mock_run, tmp_path, monkeypatch) -> None:
        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": True})
        assert result == 0

    @mock.patch("goga.build.build.run_ralphex", return_value=42)
    def test_propagates_exit_code(self, mock_run, tmp_path, monkeypatch) -> None:
        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": True})
        assert result == 42


class TestBuildDoesNotWriteClaudeSettings:
    """build()/run_ralphex never writes a .claude/settings.json — env delivery is
    handled by the host launcher's docker env-file, not by this code path."""

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


# --- Ralphex lifecycle reuse tests ---
#
# The in-container build() must NOT wipe .ralphex/. The directory now arrives as
# a prepared bind-mount owned by the host launcher (goga/commands/build); build()
# reuses whatever state the mounted .ralphex/ provides. The host wipes it only
# when `goga build --clean` is passed before launch.


class TestRalphexLifecycleReuse:
    """build() reuses the mounted .ralphex/ instead of wiping it."""

    def test_build_reuses_existing_ralphex_dir(self, tmp_path, monkeypatch) -> None:
        """A pre-existing .ralphex/config is overwritten with the new claude_command,
        but unrelated state under .ralphex/prompts/ is preserved (not wiped)."""
        monkeypatch.chdir(tmp_path)
        ralphex_dir = tmp_path / ".ralphex"
        prompts_dir = ralphex_dir / "prompts"
        prompts_dir.mkdir(parents=True)
        (ralphex_dir / "config").write_text("claude_command = OLD_PATH\n")
        (prompts_dir / "custom.txt").write_text("user prompt")

        result = _run_build_in_tmp(
            tmp_path,
            monkeypatch,
            cli_options={"dry_run": True, "skip_manifest_check": True},
        )
        assert result == 0

        config_text = (ralphex_dir / "config").read_text()
        assert "claude_command = /home/goga/bin/claude-as-claude.sh" in config_text
        assert "OLD_PATH" not in config_text
        # The cleanup step that previously wiped .ralphex/ is gone, so the user's
        # custom prompt survives alongside the copied defaults.
        assert (prompts_dir / "custom.txt").read_text() == "user prompt"

    def test_build_does_not_wipe_ralphex_on_manifest_check_failure(self, tmp_path, monkeypatch) -> None:
        """When the manifest check fails (not a git repo), build returns 1 without
        touching the pre-existing .ralphex/ directory."""
        monkeypatch.chdir(tmp_path)
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "keep.txt").write_text("survivor")

        # tmp_path is not a git repo, so the manifest check fails before any
        # .ralphex/ interaction occurs.
        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={})
        assert result == 1
        assert (ralphex_dir / "keep.txt").read_text() == "survivor"

    @mock.patch.object(subprocess, "call", return_value=0)
    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    def test_build_writes_ralphex_config_when_dir_exists(self, mock_which, mock_call, tmp_path, monkeypatch) -> None:
        """Full execution writes .ralphex/config with the resolved wrapper path even
        when .ralphex/ already exists (_write_ralphex_config uses idempotent mkdir)."""
        monkeypatch.chdir(tmp_path)
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "config").write_text("claude_command = STALE\n")

        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": True})
        assert result == 0

        config_text = (ralphex_dir / "config").read_text()
        assert "claude_command = /home/goga/bin/claude-as-claude.sh" in config_text
        assert "STALE" not in config_text


class TestRalphexCleanupRemovedContract:
    """Contract: build() no longer owns the .ralphex/ lifecycle, so the cleanup
    helper must be gone and ralphex paths must never be wiped during build()."""

    def test_cleanup_ralphex_dir_not_defined_in_module(self) -> None:
        # Use sys.modules because goga/build/__init__.py shadows the `build`
        # attribute with the function of the same name.
        build_module = sys.modules["goga.build.build"]
        assert not hasattr(build_module, "_cleanup_ralphex_dir")

    @mock.patch.object(shutil, "which", return_value="/usr/local/bin/ralphex")
    @mock.patch.object(subprocess, "call", return_value=0)
    def test_build_never_calls_rmtree_on_ralphex_path(self, mock_call, mock_which, tmp_path, monkeypatch) -> None:
        """During a full build execution, shutil.rmtree is never called with a
        .ralphex path — even when .ralphex/ already exists (which would have
        triggered the old cleanup's rmtree)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".ralphex").mkdir()
        (tmp_path / ".ralphex" / "keep.txt").write_text("survivor")
        with mock.patch("shutil.rmtree") as mock_rmtree:
            _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": True})

        ralphex_wipe_calls = [
            call for call in mock_rmtree.call_args_list if call.args and ".ralphex" in str(call.args[0])
        ]
        assert ralphex_wipe_calls == []


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
    """Option precedence (CLI > BuildConfig) flows through to run_ralphex as the
    resolved `options` dict. Verified at the delegation seam; the bool/scalar flag
    assembly itself is covered in tests/ralphex/test_run_ralphex.py."""

    @mock.patch("goga.build.build.run_ralphex", return_value=0)
    def test_worktree_from_config(self, mock_run, tmp_path, monkeypatch) -> None:
        config = _make_config(worktree=True)
        _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options={"skip_manifest_check": True})

        assert mock_run.call_args.args[1]["worktree"] is True

    @mock.patch("goga.build.build.run_ralphex", return_value=0)
    def test_cli_worktree_overrides_config(self, mock_run, tmp_path, monkeypatch) -> None:
        config = _make_config(worktree=False)
        _run_build_in_tmp(
            tmp_path,
            monkeypatch,
            config=config,
            cli_options={"worktree": True, "skip_manifest_check": True},
        )

        # CLI worktree=True overrides config=False via _resolve_options.
        assert mock_run.call_args.args[1]["worktree"] is True

    @mock.patch("goga.build.build.run_ralphex", return_value=0)
    def test_custom_prompts_dir(self, mock_run, tmp_path, monkeypatch) -> None:
        custom_prompts = tmp_path / "custom" / "prompts"
        custom_prompts.mkdir(parents=True)
        (custom_prompts / "custom_task.txt").write_text("custom content")

        config = _make_config(prompts_dir=str(custom_prompts))
        _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options={"skip_manifest_check": True})

        assert (tmp_path / ".ralphex" / "prompts" / "custom_task.txt").is_file()
        assert (tmp_path / ".ralphex" / "prompts" / "custom_task.txt").read_text() == "custom content"
