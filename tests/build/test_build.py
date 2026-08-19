from __future__ import annotations

import inspect
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest
from goga.build.build import (
    _parse_porcelain_path,
    _resolve_options,
    _unquote_git_path,
    build,
)
from goga.build.ralphex_config import write_ralphex_config
from goga.build.ralphex_runtime import sync_ralphex_defaults
from goga.build.review_options import ReviewOptions
from goga.config import (
    BuildConfig,
    PipelineConfig,
    ProjectConfig,
    ReviewExecutorConfig,
    TaskExecutorConfig,
)

TEST_ENV_VARS = {
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.7",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5-turbo",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.1",
    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
}

# Synthetic stand-ins for the vendored ralphex v1.6.1 defaults, carrying the
# literal counter fragments the role filter adapts (see .goga/usages/cooks/
# ralphex.md § Review prompt composition). The real assets land with the
# maintainers' artifact; tests never depend on it.
_VENDORED_ROLES = ("quality", "implementation", "testing", "simplification", "documentation")

_VENDORED_REVIEW_FIRST = (
    "# first review prompt\n"
    "# launches 5 parallel reviewer agents\n"
    "Launch ALL 5 Review Agents\n"
    "All 5 agent invocations\n"
    + "".join(f"{{{{agent:{role}}}}}\n" for role in _VENDORED_ROLES)
    + "until ALL 5 agents\n"
)

_VENDORED_REVIEW_SECOND = (
    "# second review prompt\n"
    "# uses 2 agents\n"
    "Both agent invocations\n"
    "{{agent:quality}}\n"
    "{{agent:implementation}}\n"
    "until both complete\n"
    "until BOTH agents\n"
    "emit them both in one response\n"
)


def _make_config(
    agent: str = "claude",
    env: dict | None = None,
    review_executor: ReviewExecutorConfig | None = None,
    **build_kwargs: object,
) -> ProjectConfig:
    """Build a ProjectConfig; review_executor defaults to None (no review section)."""
    task_executor = TaskExecutorConfig(agent=agent, env=env or {})
    build = BuildConfig(task_executor=task_executor, review_executor=review_executor, **build_kwargs)  # type: ignore[arg-type]
    return ProjectConfig(
        lang="python",
        image="goga:latest",
        dockerfile=None,
        build=build,
        pipeline=PipelineConfig(agent="claude"),
    )


@contextmanager
def _mock_vendored_sources(tmp_path: Path):
    """Point the vendored ralphex defaults at synthetic tmp sources (external boundary)."""
    from goga.build import ralphex_runtime

    prompts_dir = tmp_path / "vendored-prompts"
    agents_dir = tmp_path / "vendored-agents"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    agents_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "task.txt").write_text("# task prompt\n")
    (prompts_dir / "codex.txt").write_text("# codex review prompt\n")
    (prompts_dir / "review_first.txt").write_text(_VENDORED_REVIEW_FIRST)
    (prompts_dir / "review_second.txt").write_text(_VENDORED_REVIEW_SECOND)
    for role in _VENDORED_ROLES:
        (agents_dir / f"{role}.txt").write_text(f"# {role} agent definition\n")

    with (
        mock.patch.object(ralphex_runtime, "_VENDORED_PROMPTS", prompts_dir),
        mock.patch.object(ralphex_runtime, "_VENDORED_AGENTS", agents_dir),
    ):
        yield prompts_dir, agents_dir


def _run_build_in_tmp(
    tmp_path: Path,
    monkeypatch,
    plan: str = "plan.md",
    cli_options: dict | None = None,
    config: ProjectConfig | None = None,
) -> int:
    """chdir into tmp_path, write a plan, and run build() with mocked defaults sources."""
    monkeypatch.chdir(tmp_path)
    Path(plan).write_text("# plan\n")
    if config is None:
        config = _make_config()
    with _mock_vendored_sources(tmp_path):
        return build(plan, config, cli_options or {})  # type: ignore[arg-type]


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

    # The absorbed-private-helpers assertion lives in test_contract.py
    # (test_absorbed_private_helpers_removed_from_module) — the plan assigns
    # that contract check to the contract file.


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
        assert resolved["idle_timeout"] is None
        assert resolved["wait"] is None
        assert resolved["max_iterations"] is None
        assert resolved["review_patience"] is None

    def test_resolve_options_skip_finalize_config_value_when_cli_absent(self) -> None:
        # Mirror of the worktree case for skip_finalize (the second bool key):
        # no CLI value -> fall back to BuildConfig.
        resolved = _resolve_options(_make_config(skip_finalize=True), {})

        assert resolved["skip_finalize"] is True

    def test_resolve_options_round_trips_into_build_command(self) -> None:
        # End-to-end pin: resolved options flow bit-identically through
        # _build_command. Covers the split contract _resolve_options (build) ->
        # _build_command (ralphex), including the ""/None scalar filter so the
        # two halves cannot drift on what "omitted" means.
        from goga.ralphex.run_ralphex import _build_command

        config = _make_config(worktree=True, skip_finalize=True)
        cli = {"session_timeout": "30m", "max_iterations": 10, "idle_timeout": "", "wait": None}
        resolved = _resolve_options(config, cli)
        cmd = _build_command("plan.md", resolved)

        assert cmd == [
            "ralphex",
            "plan.md",
            "--config-dir",
            ".ralphex/",
            "--worktree",
            "--skip-finalize",
            "--session-timeout",
            "30m",
            "--max-iterations",
            "10",
        ]

    def test_resolve_options_has_no_pass_mode_keys(self) -> None:
        # tasks_only/review are pass-mode flags laid on by the orchestrator's
        # dict copy, never resolved from CLI or config.
        cli = {"tasks_only": True, "review": True}
        resolved = _resolve_options(_make_config(), cli)
        assert "tasks_only" not in resolved
        assert "review" not in resolved


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


# --- Ralphex config writer tests (migrated to the public write_ralphex_config) ---


class TestWriteRalphexConfig:
    def test_writes_resolved_wrapper_to_claude_command(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(agent="codex")

        write_ralphex_config(config.build, "/home/goga/bin/codex-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "claude_command = /home/goga/bin/codex-as-claude.sh" in config_text

    def test_writes_claude_args_default(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config()

        write_ralphex_config(config.build, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "claude_args = --dangerously-skip-permissions --output-format stream-json --verbose" in config_text

    def test_codex_enabled_false_by_default(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config()

        write_ralphex_config(config.build, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in config_text

    def test_codex_review_true_maps_to_codex_enabled_true(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(codex_review=True)

        write_ralphex_config(config.build, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = true" in config_text

    def test_does_not_write_codex_specific_keys(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(agent="codex")

        write_ralphex_config(config.build, "/home/goga/bin/codex-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "executor" not in config_text
        assert "codex_command" not in config_text
        assert "codex_sandbox" not in config_text
        assert "codex_reasoning_effort" not in config_text

    def test_does_not_generate_wrapper_scripts(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_config(agent="claude")

        write_ralphex_config(config.build, "/home/goga/bin/claude-as-claude.sh")

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
        write_ralphex_config(config.build, "/home/goga/bin/codex-as-claude.sh")

        config_text = (ralphex_dir / "config").read_text()
        assert "stale_key" not in config_text
        assert "OLD_PATH" not in config_text
        keys = {line.split(" = ", 1)[0] for line in config_text.strip().splitlines() if " = " in line}
        assert keys == {
            "claude_command",
            "claude_args",
            "codex_enabled",
            "preserve_anthropic_api_key",
            "move_plan_on_completion",
        }

    def test_move_plan_on_completion_always_false(self, tmp_path, monkeypatch) -> None:
        """goga relocates the plan itself, so ralphex never must."""
        monkeypatch.chdir(tmp_path)
        config = _make_config()

        write_ralphex_config(config.build, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "move_plan_on_completion = false" in config_text

    def test_codex_review_none_maps_to_codex_enabled_false(self, tmp_path, monkeypatch) -> None:
        """An explicit codex_review=None still renders codex_enabled = false."""
        monkeypatch.chdir(tmp_path)
        config = _make_config(codex_review=None)

        write_ralphex_config(config.build, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in config_text

    def test_writes_preserve_anthropic_api_key_true(self, tmp_path, monkeypatch) -> None:
        """preserve_anthropic_api_key is pinned to true so ralphex keeps ANTHROPIC_API_KEY."""
        monkeypatch.chdir(tmp_path)
        config = _make_config()

        write_ralphex_config(config.build, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "preserve_anthropic_api_key = true" in config_text


class TestSyncDefaults:
    """Migrated from TestCopyDefaults onto the public sync_ralphex_defaults."""

    def _review(self, roles: list[str] | None = None) -> ReviewOptions:
        return ReviewOptions(skip=False, review_agent=None, roles=roles, two_pass=False)

    def test_prompts_copied(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        with _mock_vendored_sources(tmp_path):
            sync_ralphex_defaults(_make_config().build, self._review())

        prompts_dir = tmp_path / ".ralphex" / "prompts"
        assert prompts_dir.is_dir()
        expected = {"task.txt", "codex.txt", "review_first.txt", "review_second.txt"}
        actual = {f.name for f in prompts_dir.iterdir() if f.is_file()}
        assert expected.issubset(actual)

    def test_agents_copied(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        with _mock_vendored_sources(tmp_path):
            sync_ralphex_defaults(_make_config().build, self._review())

        agents_dir = tmp_path / ".ralphex" / "agents"
        assert agents_dir.is_dir()
        expected = {f"{role}.txt" for role in _VENDORED_ROLES}
        actual = {f.name for f in agents_dir.iterdir() if f.is_file()}
        assert expected.issubset(actual)

    def test_overwrites_existing(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        prompts_dir = tmp_path / ".ralphex" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "task.txt").write_text("ORIGINAL")

        with _mock_vendored_sources(tmp_path):
            sync_ralphex_defaults(_make_config().build, self._review())

        assert (prompts_dir / "task.txt").read_text() != "ORIGINAL"

    def test_missing_vendored_source_raises_value_error(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        from goga.build import ralphex_runtime

        with (
            mock.patch.object(ralphex_runtime, "_VENDORED_PROMPTS", Path("/nonexistent")),
            mock.patch.object(ralphex_runtime, "_VENDORED_AGENTS", Path("/nonexistent")),
            pytest.raises(ValueError, match="dump-defaults"),
        ):
            sync_ralphex_defaults(_make_config().build, self._review())

    def test_empty_defaults_subdirs_no_error(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        empty_prompts = tmp_path / "fake" / "prompts"
        empty_agents = tmp_path / "fake" / "agents"
        empty_prompts.mkdir(parents=True)
        empty_agents.mkdir(parents=True)
        config = _make_config(prompts_dir=str(empty_prompts), agents_dir=str(empty_agents))

        sync_ralphex_defaults(config.build, self._review())

        assert (tmp_path / ".ralphex" / "prompts").is_dir()
        assert (tmp_path / ".ralphex" / "agents").is_dir()

    def test_custom_prompts_dir(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        custom_prompts = tmp_path / "custom" / "prompts"
        custom_prompts.mkdir(parents=True)
        (custom_prompts / "custom_task.txt").write_text("custom content")

        config = _make_config(prompts_dir=str(custom_prompts))
        with _mock_vendored_sources(tmp_path):
            sync_ralphex_defaults(config.build, self._review())

        copied = tmp_path / ".ralphex" / "prompts" / "custom_task.txt"
        assert copied.is_file()
        assert copied.read_text() == "custom content"


# --- Full build function tests ---


class TestBuildDryRun:
    """build() delegates dry_run to run_ralphex through run_build_pass (the
    dry-run short-circuit lives in run_ralphex). Verified at the delegation
    seam of the pass unit."""

    def test_dry_run_returns_0(self, tmp_path, monkeypatch) -> None:
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0):
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                cli_options={"dry_run": True, "skip_manifest_check": True},
            )
        assert result == 0

    def test_dry_run_passes_dry_run_to_run_ralphex(self, tmp_path, monkeypatch) -> None:
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                cli_options={"dry_run": True, "skip_manifest_check": True},
            )
        # dry_run reaches run_ralphex as the positional 3rd arg.
        assert mock_run.call_args.args[2] is True


class TestBuildDelegation:
    """build() delegates each pass to run_ralphex (via run_build_pass) with resolved options."""

    def test_build_delegates_to_run_ralphex_with_resolved_options(self, tmp_path, monkeypatch) -> None:
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=_make_config(worktree=True),
                cli_options={"skip_manifest_check": True},
            )

        assert result == 0
        mock_run.assert_called_once()
        args = mock_run.call_args.args
        assert args[0] == "plan.md"
        assert args[1]["worktree"] is True
        assert args[2] is False  # dry_run positional
        assert "dry_run" not in args[1]

    def test_build_returns_run_ralphex_exit_code(self, tmp_path, monkeypatch) -> None:
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=42):
            result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": True})

        assert result == 42

    def test_build_dry_run_delegates_with_dry_run_true(self, tmp_path, monkeypatch) -> None:
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"dry_run": True, "skip_manifest_check": True})

        assert mock_run.call_args.args[2] is True


class TestBuildFullExecution:
    """build() returns whatever the last pass returns — mocked at the delegation
    seam of the pass unit, decoupling the build tests from ralphex internals."""

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_full_execution_returns_0(self, mock_run, tmp_path, monkeypatch) -> None:
        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": True})
        assert result == 0

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=42)
    def test_propagates_exit_code(self, mock_run, tmp_path, monkeypatch) -> None:
        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": True})
        assert result == 42


class TestBuildDoesNotWriteClaudeSettings:
    """build()/run_ralphex never writes a .claude/settings.json — env delivery is
    handled by the host launcher's docker env-file, not by this code path."""

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_does_not_write_claude_settings(self, mock_run, tmp_path, monkeypatch) -> None:
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

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_codex_no_claude_settings(self, mock_run, tmp_path, monkeypatch) -> None:
        config = _make_config(agent="codex")
        _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options={"skip_manifest_check": True})

        assert not (tmp_path / ".claude").exists()


class TestBuildDefaultsDirNotFound:
    def test_defaults_missing_returns_1(self, tmp_path, monkeypatch) -> None:
        """Missing vendored defaults abort the run: the ValueError of the sync is
        caught by the orchestrator, which logs and returns 1 before any pass."""
        from goga.build import ralphex_runtime

        monkeypatch.chdir(tmp_path)
        Path("plan.md").write_text("# plan\n")
        with (
            mock.patch.object(ralphex_runtime, "_VENDORED_PROMPTS", Path("/nonexistent")),
            mock.patch.object(ralphex_runtime, "_VENDORED_AGENTS", Path("/nonexistent")),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run,
        ):
            result = build("plan.md", _make_config(), {"skip_manifest_check": True})
        assert result == 1
        mock_run.assert_not_called()


class TestBuildRepeatedBuild:
    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_repeated_build_overwrites(self, mock_run, tmp_path, monkeypatch) -> None:
        cli_options = {"skip_manifest_check": True}
        _run_build_in_tmp(tmp_path, monkeypatch, cli_options=cli_options)

        prompts_dir = tmp_path / ".ralphex" / "prompts"
        modified_file = prompts_dir / "task.txt"
        modified_file.write_text("USER MODIFICATION")

        _run_build_in_tmp(tmp_path, monkeypatch, cli_options=cli_options)
        assert modified_file.read_text() != "USER MODIFICATION"


# --- Ralphex lifecycle reuse tests ---
#
# The in-container build() must NOT wipe .ralphex/ itself. The directory
# arrives as a prepared bind-mount owned by the host launcher
# (goga/commands/build); build() only rewrites the prompts/agents subdirectories
# (the sync contract) and the pass config. The host wipes .ralphex/ only when
# `goga build --clean` is passed before launch.


class TestRalphexLifecycleReuse:
    def test_build_reuses_existing_ralphex_dir(self, tmp_path, monkeypatch) -> None:
        """A pre-existing .ralphex/config is overwritten with the new claude_command;
        prompts/agents are brought to the source state (full rewrite), while
        unrelated state directly under .ralphex/ survives — build() never wipes
        the mounted directory itself."""
        monkeypatch.chdir(tmp_path)
        Path("plan.md").write_text("# plan\n")
        ralphex_dir = tmp_path / ".ralphex"
        prompts_dir = ralphex_dir / "prompts"
        prompts_dir.mkdir(parents=True)
        (ralphex_dir / "config").write_text("claude_command = OLD_PATH\n")
        (prompts_dir / "custom.txt").write_text("user prompt")
        (ralphex_dir / "keep.txt").write_text("unrelated state")

        with (
            _mock_vendored_sources(tmp_path),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0),
        ):
            result = build("plan.md", _make_config(), {"dry_run": True, "skip_manifest_check": True})
        assert result == 0

        config_text = (ralphex_dir / "config").read_text()
        assert "claude_command = /home/goga/bin/claude-as-claude.sh" in config_text
        assert "OLD_PATH" not in config_text
        # The sync contract fully rewrites prompts/: the stale custom prompt is
        # gone, replaced by the source files.
        assert not (prompts_dir / "custom.txt").exists()
        assert (prompts_dir / "task.txt").is_file()
        # ... but state directly under .ralphex/ is untouched (host-owned).
        assert (ralphex_dir / "keep.txt").read_text() == "unrelated state"

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

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_build_writes_ralphex_config_when_dir_exists(self, mock_run, tmp_path, monkeypatch) -> None:
        """Full execution writes .ralphex/config with the resolved wrapper path even
        when .ralphex/ already exists (write_ralphex_config uses idempotent mkdir)."""
        monkeypatch.chdir(tmp_path)
        Path("plan.md").write_text("# plan\n")
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "config").write_text("claude_command = STALE\n")

        with _mock_vendored_sources(tmp_path):
            result = build("plan.md", _make_config(), {"skip_manifest_check": True})
        assert result == 0

        config_text = (ralphex_dir / "config").read_text()
        assert "claude_command = /home/goga/bin/claude-as-claude.sh" in config_text
        assert "STALE" not in config_text


class TestRalphexCleanupRemovedContract:
    """Contract: build() no longer owns the .ralphex/ lifecycle, so the cleanup
    helper must be gone and .ralphex/ itself is never wiped during build() —
    only its prompts/ and agents/ subdirectories are rewritten by the sync."""

    def test_cleanup_ralphex_dir_not_defined_in_module(self) -> None:
        # Use sys.modules because goga/build/__init__.py shadows the `build`
        # attribute with the function of the same name.
        build_module = sys.modules["goga.build.build"]
        assert not hasattr(build_module, "_cleanup_ralphex_dir")

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_build_never_calls_rmtree_on_ralphex_path(self, mock_run, tmp_path, monkeypatch) -> None:
        """During a full build execution, shutil.rmtree is called only on
        .ralphex/prompts and .ralphex/agents (the sync rewrite), never on
        .ralphex/ itself — even when .ralphex/ already exists."""
        monkeypatch.chdir(tmp_path)
        Path("plan.md").write_text("# plan\n")
        (tmp_path / ".ralphex").mkdir()
        (tmp_path / ".ralphex" / "keep.txt").write_text("survivor")
        with mock.patch("shutil.rmtree") as mock_rmtree, _mock_vendored_sources(tmp_path):
            build("plan.md", _make_config(), {"skip_manifest_check": True})

        allowed_targets = {".ralphex/prompts", ".ralphex/agents"}
        ralphex_wipe_calls = [
            call for call in mock_rmtree.call_args_list if call.args and str(call.args[0]) not in allowed_targets
        ]
        assert ralphex_wipe_calls == []
        # ... and the directory itself survived.
        assert (tmp_path / ".ralphex" / "keep.txt").read_text() == "survivor"


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)


class TestManifestCheck:
    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_all_committed_proceeds(self, mock_run, tmp_path, monkeypatch) -> None:
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

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_skip_manifest_check(self, mock_run, tmp_path, monkeypatch) -> None:
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("content")

        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": True})
        assert result == 0

    def test_not_git_repo_returns_1(self, tmp_path, monkeypatch) -> None:
        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={})
        assert result == 1

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_no_codemanifest_files_proceeds(self, mock_run, tmp_path, monkeypatch) -> None:
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

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_worktree_from_config(self, mock_run, tmp_path, monkeypatch) -> None:
        config = _make_config(worktree=True)
        _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options={"skip_manifest_check": True})

        assert mock_run.call_args.args[1]["worktree"] is True

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
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

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_custom_prompts_dir(self, mock_run, tmp_path, monkeypatch) -> None:
        custom_prompts = tmp_path / "custom" / "prompts"
        custom_prompts.mkdir(parents=True)
        (custom_prompts / "custom_task.txt").write_text("custom content")

        config = _make_config(prompts_dir=str(custom_prompts))
        _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options={"skip_manifest_check": True})

        assert (tmp_path / ".ralphex" / "prompts" / "custom_task.txt").is_file()
        assert (tmp_path / ".ralphex" / "prompts" / "custom_task.txt").read_text() == "custom content"


# --- Review-phase orchestration (skip / two-pass / relocation) ---


class TestBuildReviewPhaseOrchestration:
    """The orchestrator's pass modes on top of run_build_pass."""

    def _passes(self, mock_run) -> list[dict]:
        return [call.args[1] for call in mock_run.call_args_list]

    def test_build_skip_run_single_tasks_only_pass(self, tmp_path, monkeypatch) -> None:
        config = _make_config(review_executor=ReviewExecutorConfig(skip=True))
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={"skip_manifest_check": True, "skip_review": None},
            )

        assert result == 0
        assert mock_run.call_count == 1
        options = mock_run.call_args.args[1]
        assert options["tasks_only"] is True
        assert "review" not in options
        # Success relocates the plan.
        assert not (tmp_path / "plan.md").exists()
        assert (tmp_path / "completed" / "plan.md").read_text() == "# plan\n"

    def test_build_skip_run_still_syncs_and_filters_roles(self, tmp_path, monkeypatch) -> None:
        config = _make_config(review_executor=ReviewExecutorConfig(skip=True, roles=["quality"]))
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={"skip_manifest_check": True},
            )

        assert result == 0
        assert mock_run.call_count == 1
        assert mock_run.call_args.args[1]["tasks_only"] is True
        # The skip decision never suppresses the defaults sync: roles filter
        # the review prompts even though no review pass will run.
        review_first = (tmp_path / ".ralphex" / "prompts" / "review_first.txt").read_text()
        assert "{{agent:quality}}" in review_first
        assert "{{agent:implementation}}" not in review_first
        assert not (tmp_path / "plan.md").exists()
        assert (tmp_path / "completed" / "plan.md").is_file()

    def test_build_two_pass_second_pass_review_mode(self, tmp_path, monkeypatch) -> None:
        config = _make_config(review_executor=ReviewExecutorConfig(agent="codex"))
        review_wrapper = tmp_path / "codex-as-claude.sh"
        review_wrapper.write_text("#!/bin/sh\n")

        with (
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(review_wrapper)),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run,
        ):
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={"skip_manifest_check": True},
            )

        assert result == 0
        assert mock_run.call_count == 2
        first, second = self._passes(mock_run)
        assert first["tasks_only"] is True
        assert "review" not in first
        assert second["review"] is True
        assert "tasks_only" not in second
        # The final pass config carries the review executor wrapper; the real
        # resolve_wrapper_path of the orchestrator built it (string resolve).
        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "claude_command = /home/goga/bin/codex-as-claude.sh" in config_text
        assert "move_plan_on_completion = false" in config_text

    def test_build_two_pass_pass1_failure_skips_pass2(self, tmp_path, monkeypatch) -> None:
        config = _make_config(review_executor=ReviewExecutorConfig(agent="codex"))
        review_wrapper = tmp_path / "codex-as-claude.sh"
        review_wrapper.write_text("#!/bin/sh\n")

        with (
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(review_wrapper)),
            mock.patch("goga.build.build_pass.run_ralphex", side_effect=[1]) as mock_run,
        ):
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={"skip_manifest_check": True},
            )

        assert result == 1
        assert mock_run.call_count == 1
        # A failed run keeps the plan in place for ralphex to resume.
        assert (tmp_path / "plan.md").is_file()
        assert not (tmp_path / "completed").exists()

    def test_build_two_pass_pass2_failure_propagates_and_keeps_plan(self, tmp_path, monkeypatch) -> None:
        """Pass 1 succeeded but pass 2 failed — the run is a failure.

        The returned code is the LAST pass's code and the relocation outcome is
        computed from it, so a failed review pass must keep the plan in place
        exactly like a failed task pass.
        """
        config = _make_config(review_executor=ReviewExecutorConfig(agent="codex"))
        review_wrapper = tmp_path / "codex-as-claude.sh"
        review_wrapper.write_text("#!/bin/sh\n")

        with (
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(review_wrapper)),
            mock.patch("goga.build.build_pass.run_ralphex", side_effect=[0, 1]) as mock_run,
        ):
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={"skip_manifest_check": True},
            )

        assert result == 1
        assert mock_run.call_count == 2
        second = self._passes(mock_run)[1]
        assert second["review"] is True
        assert "tasks_only" not in second
        assert (tmp_path / "plan.md").is_file()
        assert not (tmp_path / "completed").exists()

    def test_build_invalid_review_config_returns_1_before_side_effects(self, tmp_path, monkeypatch) -> None:
        config = _make_config(review_executor=ReviewExecutorConfig(roles=["bogus"]))
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={"skip_manifest_check": True},
            )

        assert result == 1
        mock_run.assert_not_called()
        assert not (tmp_path / ".ralphex").exists()

    def test_build_resolves_skip_from_config_when_cli_none(self, tmp_path, monkeypatch) -> None:
        config = _make_config(review_executor=ReviewExecutorConfig(skip=True))
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={"skip_manifest_check": True},
            )

        assert result == 0
        assert mock_run.call_count == 1
        assert mock_run.call_args.args[1]["tasks_only"] is True

    def test_build_skip_wins_over_two_pass(self, tmp_path, monkeypatch) -> None:
        # agent differs from the task agent, so two_pass resolves True — but the
        # skip branch takes priority: no review phase of any kind.
        config = _make_config(review_executor=ReviewExecutorConfig(skip=True, agent="codex"))
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={"skip_manifest_check": True},
            )

        assert result == 0
        assert mock_run.call_count == 1
        assert mock_run.call_args.args[1]["tasks_only"] is True

    def test_build_dry_run_two_pass_prints_both_and_keeps_plan(self, tmp_path, monkeypatch) -> None:
        config = _make_config(review_executor=ReviewExecutorConfig(agent="codex"))
        review_wrapper = tmp_path / "codex-as-claude.sh"
        review_wrapper.write_text("#!/bin/sh\n")

        with (
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(review_wrapper)),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run,
        ):
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={"skip_manifest_check": True, "dry_run": True},
            )

        assert result == 0
        # A dry run prints the commands of EVERY planned pass.
        assert mock_run.call_count == 2
        assert all(call.args[2] is True for call in mock_run.call_args_list)
        # ... and moves nothing.
        assert (tmp_path / "plan.md").is_file()
        assert not (tmp_path / "completed").exists()

    def test_build_no_review_config_single_full_pass(self, tmp_path, monkeypatch) -> None:
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=_make_config(review_executor=None),
                cli_options={"skip_manifest_check": True},
            )

        assert result == 0
        assert mock_run.call_count == 1
        options = mock_run.call_args.args[1]
        assert "tasks_only" not in options
        assert "review" not in options
        assert not (tmp_path / "plan.md").exists()
        assert (tmp_path / "completed" / "plan.md").is_file()

    def test_build_cli_no_skip_review_overrides_config_skip(self, tmp_path, monkeypatch) -> None:
        """CLI False beats config `skip: true` — the full cycle runs with validation."""
        config = _make_config(review_executor=ReviewExecutorConfig(skip=True, roles=["bogus"]))
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={"skip_manifest_check": True, "skip_review": False},
            )

        # The forced full pass activates validation, which rejects the bogus role.
        assert result == 1
        mock_run.assert_not_called()

    def test_build_cli_no_skip_review_forces_full_pass(self, tmp_path, monkeypatch) -> None:
        """CLI False against a valid config-skip runs the full single pass."""
        config = _make_config(review_executor=ReviewExecutorConfig(skip=True))
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={"skip_manifest_check": True, "skip_review": False},
            )

        assert result == 0
        assert mock_run.call_count == 1
        options = mock_run.call_args.args[1]
        assert "tasks_only" not in options
        assert "review" not in options

    def test_build_skip_run_skips_validation(self, tmp_path, monkeypatch) -> None:
        """A skipped run never validates roles — a bogus role is never read."""
        config = _make_config(review_executor=ReviewExecutorConfig(skip=True, roles=["bogus"]))
        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={"skip_manifest_check": True},
            )

        assert result == 0
        assert mock_run.call_count == 1
        assert mock_run.call_args.args[1]["tasks_only"] is True
