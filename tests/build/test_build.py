"""Contract and logic tests for the entity declared in ``goga/build/CODEMANIFEST``
with ``location: build.py``:

- ``build(plan, config, cli_options)`` — the stable two-pass build cycle with
  its five hooks checkpoints

Orchestration tests follow the design's General Setup: ``run_build_pass`` is
monkeypatched at ``goga.build.build``'s import point with a recording stub,
runs happen inside ``tmp_path`` (the ``.ralphex/`` writes land there), and
``resolve_current_branch_name``/``resolve_topic_dir``/``collect_topic_statuses``
are pinned at the same import point. Wrapper-existence checks are pinned at
``goga.build.review_config``'s import point. The gate and the notifications run
the real platform over the boundary fixtures of ``tests/hooks/conftest.py``.
"""

from __future__ import annotations

import dataclasses
import inspect
import logging
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import is_dataclass
from pathlib import Path
from unittest import mock

import pytest
from goga.build.build import (
    _parse_porcelain_path,
    _unquote_git_path,
    build,
)
from goga.build.hooks import BuildHooks
from goga.build.plan_relocation import move_completed_plan as _real_move_completed_plan
from goga.config import (
    AdditionalReviewConfig,
    BuildConfig,
    PipelineConfig,
    ProjectConfig,
    ReviewConfig,
)
from goga.history import TopicRecord

build_module = sys.modules["goga.build.build"]

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

_SOFT_ACTIONS = ("build_started", "pass_started", "pass_completed", "build_completed")
_ALL_ACTIONS = ("validate_build", *_SOFT_ACTIONS)

# The full cli_options surface the in-container entrypoint forwards; every
# knob key present with None — the "cli_options all None" form.
_FULL_CLI_OPTIONS = {
    "dry_run": False,
    "skip_manifest_check": True,
    "skip_review": None,
    "base_ref": None,
    "review_patience": None,
    "session_timeout": None,
    "idle_timeout": None,
    "wait": None,
    "max_iterations": None,
}


def _make_config(
    agent: str = "claude",
    env: dict | None = None,
    review: ReviewConfig | None = None,
    **build_kwargs: object,
) -> ProjectConfig:
    """Build a ProjectConfig on the two-part build model; review defaults to None."""
    build_section = BuildConfig(agent=agent, env=env or {}, review=review, **build_kwargs)  # type: ignore[arg-type]
    return ProjectConfig(
        lang="python",
        image="goga:latest",
        dockerfile=None,
        build=build_section,
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


def _pin_orchestration_boundary(
    monkeypatch,
    tmp_path: Path,
    *,
    branch: str | None = "add-hooks-to-build",
) -> None:
    """Pin the outside-world reads of the cycle: branch, topic dir, statuses, wrappers.

    The default pins the branch-only form (``resolve_topic_dir`` raises the
    unsluggable-branch ValueError, no topic statuses); the wrapper-existence
    check of the review-config validation resolves every agent to one existing
    tmp file.
    """
    wrapper = tmp_path / "claude-as-claude.sh"
    wrapper.write_text("#!/bin/sh\n")

    def _unsluggable(_topic: str, _year: str | None = None) -> Path:
        raise ValueError(f"topic input {_topic!r} normalizes to an empty topic slug")

    monkeypatch.setattr(build_module, "resolve_current_branch_name", lambda: branch)
    monkeypatch.setattr(build_module, "resolve_topic_dir", _unsluggable)
    monkeypatch.setattr(build_module, "collect_topic_statuses", lambda _year=None: [])
    monkeypatch.setattr("goga.build.review_config.resolve_wrapper_path", lambda _agent: str(wrapper))


def _run_build_in_tmp(
    tmp_path: Path,
    monkeypatch,
    cli_options: dict | None = None,
    config: ProjectConfig | None = None,
    *,
    branch: str | None = "add-hooks-to-build",
) -> int:
    """chdir into tmp_path, write a plan, pin the boundary, and run build()."""
    monkeypatch.chdir(tmp_path)
    Path("plan.md").write_text("# plan\n")
    _pin_orchestration_boundary(monkeypatch, tmp_path, branch=branch)
    if config is None:
        config = _make_config()
    with _mock_vendored_sources(tmp_path):
        return build("plan.md", config, cli_options or {})


def _recording_call(name: str, real, order: list[str]):
    """A delegating wrapper recording ``name`` before every call of ``real``."""

    def _call(*args, **kwargs):
        order.append(name)
        return real(*args, **kwargs)

    return _call


def _install_recording_tool(install_tool_package, recorded: list[tuple[str, object]]):
    """Install one fake tool subscribing to all five build actions, recording contexts."""

    def register(hooks: object) -> None:
        def make(action: str):
            def hook(self: object, context: object) -> None:
                recorded.append((action, context))

            return hook

        for action in _ALL_ACTIONS:
            hooks.subscribe("build", action, action, make(action))  # type: ignore[attr-defined]

    return install_tool_package("goga_tool_demo", register_hooks=register)


def _install_vetoing_tool(install_tool_package, recorded: list[tuple[str, object]]):
    """Install one fake tool whose ``guard`` validation hook vetoes with 'policy'."""

    def register(hooks: object) -> None:
        def guard(self: object, context: object) -> None:
            recorded.append(("validate_build", context))
            context.veto("policy")

        def make(action: str):
            def hook(self: object, context: object) -> None:
                recorded.append((action, context))

            return hook

        hooks.subscribe("build", "validate_build", "guard", guard)  # type: ignore[attr-defined]
        for action in _SOFT_ACTIONS:
            hooks.subscribe("build", action, action, make(action))  # type: ignore[attr-defined]

    return install_tool_package("goga_tool_a", register_hooks=register)


def _assert_no_secret_strings(value: object, secrets: frozenset[str]) -> None:
    """Walk a delivered context recursively; no string member equals a secret value."""
    if is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            _assert_no_secret_strings(getattr(value, field.name), secrets)
    elif isinstance(value, str):
        assert value not in secrets
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _assert_no_secret_strings(item, secrets)


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)


# --- Contract tests ---


class TestBuildCycleContract:
    def test_build_importable_from_facade(self) -> None:
        """build() is accessible from the goga.build facade."""
        from goga.build import build as facade_build

        assert facade_build is build

    def test_build_signature_is_plan_config_cli_options(self) -> None:
        sig = inspect.signature(build)
        assert list(sig.parameters) == ["plan", "config", "cli_options"]
        assert sig.return_annotation in ("int", int)

    def test_cycle_calls_collaborators_in_traced_order(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
    ) -> None:
        """The 12-step cycle: resolution → validation → sync → gate → start →
        passes (compose/emit/launch/emit each) → relocation → statuses → completion."""
        pin_package_environment({})
        order: list[str] = []

        real_compose = build_module.compose_pass_options

        def _compose(settings, stage):
            order.append(f"compose_pass_options:{stage}")
            return real_compose(settings, stage)

        def _move(plan, outcome, dry_run):
            order.append("move_completed_plan")
            return _real_move_completed_plan(plan, outcome, dry_run)

        def _pass(*args, **kwargs):
            order.append("run_build_pass")
            return 0

        class _RecordingHooks(BuildHooks):
            def validate_build(self, moment, tasks, review, skip):
                order.append("validate_build")
                return super().validate_build(moment, tasks, review, skip)

            def emit_build_started(self, moment, tasks, review, skip):
                order.append("emit_build_started")
                super().emit_build_started(moment, tasks, review, skip)

            def emit_pass_started(self, moment, facts):
                order.append("emit_pass_started")
                super().emit_pass_started(moment, facts)

            def emit_pass_completed(self, moment, facts, exit_code):
                order.append("emit_pass_completed")
                super().emit_pass_completed(moment, facts, exit_code)

            def emit_build_completed(self, moment, exit_code, stages, relocation, statuses):
                order.append("emit_build_completed")
                super().emit_build_completed(moment, exit_code, stages, relocation, statuses)

        monkeypatch.setattr(
            build_module,
            "resolve_run_settings",
            _recording_call("resolve_run_settings", build_module.resolve_run_settings, order),
        )
        monkeypatch.setattr(
            build_module,
            "validate_review_config",
            _recording_call("validate_review_config", build_module.validate_review_config, order),
        )
        monkeypatch.setattr(
            build_module,
            "sync_ralphex_defaults",
            _recording_call("sync_ralphex_defaults", build_module.sync_ralphex_defaults, order),
        )
        monkeypatch.setattr(build_module, "compose_pass_options", _compose)
        monkeypatch.setattr(build_module, "move_completed_plan", _move)
        monkeypatch.setattr(build_module, "BuildHooks", _RecordingHooks)

        with mock.patch("goga.build.build.run_build_pass", side_effect=_pass):
            result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 0
        assert order == [
            "resolve_run_settings",
            "validate_review_config",
            "sync_ralphex_defaults",
            "validate_build",
            "emit_build_started",
            "compose_pass_options:tasks",
            "emit_pass_started",
            "run_build_pass",
            "emit_pass_completed",
            "compose_pass_options:review",
            "emit_pass_started",
            "run_build_pass",
            "emit_pass_completed",
            "move_completed_plan",
            "emit_build_completed",
        ]


# --- Git pre-check helper tests ---


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


# --- Manifest pre-check (step 0) ---


class TestManifestCheck:
    @mock.patch("goga.build.build.run_build_pass", return_value=0)
    def test_all_committed_proceeds(self, mock_pass, tmp_path, monkeypatch) -> None:
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("content")
        subprocess.run(["git", "add", "CODEMANIFEST"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)

        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": False})
        assert result == 0

    def test_uncommitted_manifest_returns_1(self, tmp_path, monkeypatch) -> None:
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("content")

        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": False})
        assert result == 1

    @mock.patch("goga.build.build.run_build_pass", return_value=0)
    def test_skip_manifest_check(self, mock_pass, tmp_path, monkeypatch) -> None:
        _init_git_repo(tmp_path)
        manifest = tmp_path / "CODEMANIFEST"
        manifest.write_text("content")

        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": True})
        assert result == 0

    def test_not_git_repo_returns_1(self, tmp_path, monkeypatch) -> None:
        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": False})
        assert result == 1

    @mock.patch("goga.build.build.run_build_pass", return_value=0)
    def test_no_codemanifest_files_proceeds(self, mock_pass, tmp_path, monkeypatch) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / ".gitkeep").write_text("")
        subprocess.run(["git", "add", ".gitkeep"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)

        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": False})
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

        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": False})
        assert result == 1


# --- The two-pass cycle (steps 4-12) ---


class TestTwoPassCycle:
    def test_build_runs_two_passes_with_bound_settings(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
    ) -> None:
        """Two passes with the resolved settings bound to each: tasks-only with the
        root env layer, review with the review env layer — never the other way."""
        pin_package_environment({})
        config = _make_config(env={"A": "1"}, review=ReviewConfig(agent="codex", env={"R": "2"}))

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 0
        assert mock_pass.call_count == 2

        first, second = mock_pass.call_args_list
        assert first.args[0] == "plan.md"
        assert first.args[2]["tasks_only"] is True
        assert "review" not in first.args[2]
        assert first.kwargs["env"] == {"A": "1"}
        assert first.args[3] == "/home/goga/bin/claude-as-claude.sh"

        assert second.args[2]["review"] is True
        assert "tasks_only" not in second.args[2]
        assert second.kwargs["env"] == {"R": "2"}
        assert second.args[3] == "/home/goga/bin/codex-as-claude.sh"

        # A successful final pass relocates the plan.
        assert not (tmp_path / "plan.md").exists()
        assert (tmp_path / "completed" / "plan.md").read_text() == "# plan\n"

    def test_build_skipped_review_single_tasks_pass(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
    ) -> None:
        """A skipped review yields exactly one tasks pass; the return value is
        that pass's code."""
        pin_package_environment({})
        config = _make_config(review=ReviewConfig(skip=True))

        with mock.patch("goga.build.build.run_build_pass", side_effect=[7]) as mock_pass:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={**_FULL_CLI_OPTIONS, "skip_review": True},
            )

        assert result == 7
        assert mock_pass.call_count == 1
        assert mock_pass.call_args.args[2]["tasks_only"] is True

    def test_build_failed_tasks_pass_skips_review(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A failed tasks pass never reaches the review pass; the completion
        facts carry the failure."""
        recorded: list[tuple[str, object]] = []
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})
        _install_recording_tool(install_tool_package, recorded)

        with mock.patch("goga.build.build.run_build_pass", return_value=1) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 1
        assert mock_pass.call_count == 1

        pass_completed = next(context for action, context in recorded if action == "pass_completed")
        assert pass_completed.exit_code == 1
        assert pass_completed.facts.stage == "tasks"

        completed = next(context for action, context in recorded if action == "build_completed")
        assert completed.exit_code == 1
        assert completed.stages == ["tasks"]
        assert completed.relocation.moved is False

        # A failed run keeps the plan in place for ralphex to resume.
        assert (tmp_path / "plan.md").is_file()
        assert not (tmp_path / "completed").exists()

    def test_build_vetoed_run_blocks_before_any_pass(
        self,
        tmp_path: Path,
        monkeypatch,
        caplog,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A vetoed gate: one merged error, exit 1, no pass, no relocation, and
        no notification of the tool ever runs."""
        recorded: list[tuple[str, object]] = []
        pin_package_environment({"goga_tool_a": ["a-dist"]})
        _install_vetoing_tool(install_tool_package, recorded)

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 1
        mock_pass.assert_not_called()
        assert (tmp_path / "plan.md").is_file()
        assert not (tmp_path / "completed").exists()

        # Only the validation hook of the tool ran — no notification fired.
        assert [action for action, _context in recorded] == ["validate_build"]

        errors = [
            record
            for record in caplog.records
            if record.name == "goga.build.build" and record.levelno == logging.ERROR
        ]
        assert len(errors) == 1
        assert errors[0].getMessage() == "build blocked by hook vetoes"
        assert errors[0].violations == ["a/guard: policy"]

    @pytest.mark.parametrize(
        "variant",
        ["uncommitted-manifests", "invalid-review-config", "defaults-unavailable", "no-build-agent-skip-run"],
    )
    def test_build_pre_launch_failures_fire_no_events(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
        variant: str,
    ) -> None:
        """Steps 0-3.5 failures return 1 before the moment exists — zero hook
        invocations across all five actions in every variant."""
        recorded: list[tuple[str, object]] = []
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})
        _install_recording_tool(install_tool_package, recorded)

        config = _make_config()
        cli_options = {**_FULL_CLI_OPTIONS, "skip_manifest_check": True}

        if variant == "uncommitted-manifests":
            cli_options["skip_manifest_check"] = False
            monkeypatch.setattr(build_module, "_find_uncommitted_manifests", lambda: ["x/CODEMANIFEST"])
        elif variant == "invalid-review-config":
            monkeypatch.setattr(
                build_module,
                "validate_review_config",
                mock.Mock(side_effect=ValueError("bad review config")),
            )
        elif variant == "defaults-unavailable":
            monkeypatch.setattr(
                build_module,
                "sync_ralphex_defaults",
                mock.Mock(side_effect=ValueError("no defaults")),
            )
        else:
            # The degenerate skip-run: no root agent and the review skipped —
            # the step-3.5 guard path (validation returns early on skip).
            config = _make_config(agent=None, review=ReviewConfig(skip=True))
            cli_options["skip_review"] = True

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options=cli_options)

        assert result == 1
        mock_pass.assert_not_called()
        assert recorded == []

    def test_unsluggable_branch_falls_back_to_branch_only(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """An unresolvable branch yields the 'unknown' branch-only work identity;
        the run proceeds normally with empty statuses."""
        recorded: list[tuple[str, object]] = []
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})
        _install_recording_tool(install_tool_package, recorded)

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options=dict(_FULL_CLI_OPTIONS), branch=None)

        assert result == 0
        assert mock_pass.call_count == 2

        completed = next(context for action, context in recorded if action == "build_completed")
        assert completed.moment.work.branch == "unknown"
        assert completed.moment.work.slug is None
        assert completed.moment.work.year is None
        assert completed.statuses == []

    @pytest.mark.parametrize("topic_hosted", [True, False])
    def test_build_statuses_recomputed_after_relocation(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
        topic_hosted: bool,
    ) -> None:
        """The statuses re-read happens AFTER the relocation attempt and carries
        the hosted topic's record; the branch-only form delivers []."""
        recorded: list[tuple[str, object]] = []
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})
        _install_recording_tool(install_tool_package, recorded)

        topic_dir = tmp_path / ".goga" / "history" / "2026" / "add-hooks-to-build"
        if topic_hosted:
            topic_dir.mkdir(parents=True)

        order: list[str] = []
        seen_years: list[str | None] = []

        def _collect(year=None):
            order.append("statuses")
            seen_years.append(year)
            return [TopicRecord(topic="add-hooks-to-build", statuses=["backlog", "designed"])]

        def _move(plan, outcome, dry_run):
            order.append("move")
            return _real_move_completed_plan(plan, outcome, dry_run)

        monkeypatch.chdir(tmp_path)
        Path("plan.md").write_text("# plan\n")

        wrapper = tmp_path / "claude-as-claude.sh"
        wrapper.write_text("#!/bin/sh\n")
        monkeypatch.setattr(build_module, "resolve_current_branch_name", lambda: "add-hooks-to-build")
        monkeypatch.setattr(
            build_module,
            "resolve_topic_dir",
            lambda _topic, _year=None: Path(".goga/history/2026/add-hooks-to-build"),
        )
        monkeypatch.setattr(build_module, "collect_topic_statuses", _collect)
        monkeypatch.setattr(build_module, "move_completed_plan", _move)
        monkeypatch.setattr("goga.build.review_config.resolve_wrapper_path", lambda _agent: str(wrapper))

        with (
            _mock_vendored_sources(tmp_path),
            mock.patch("goga.build.build.run_build_pass", return_value=0),
        ):
            result = build("plan.md", _make_config(), dict(_FULL_CLI_OPTIONS))

        assert result == 0

        completed = next(context for action, context in recorded if action == "build_completed")

        if topic_hosted:
            assert order == ["move", "statuses"]
            assert seen_years == ["2026"]
            assert completed.statuses == ["backlog", "designed"]
        else:
            # The branch hosts no topic: no statuses read happens at all — the
            # branch-only form delivers [] without touching the tree.
            assert order == ["move"]
            assert seen_years == []
            assert completed.statuses == []

    def test_stage_facts_carry_env_names_only(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The delivered facts carry env NAMES (sorted), never values — walking
        every delivered context finds no tasks-env value string."""
        recorded: list[tuple[str, object]] = []
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})
        _install_recording_tool(install_tool_package, recorded)

        config = _make_config(env={"B": "2", "A": "1"}, review=ReviewConfig(agent="codex", env={"C": "3"}))

        with mock.patch("goga.build.build.run_build_pass", return_value=0):
            result = _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 0

        tasks_started = next(
            context for action, context in recorded if action == "pass_started" and context.facts.stage == "tasks"
        )
        review_started = next(
            context for action, context in recorded if action == "pass_started" and context.facts.stage == "review"
        )
        assert tasks_started.facts.env == ["A", "B"]
        assert review_started.facts.env == ["C"]

        for _action, context in recorded:
            _assert_no_secret_strings(context, frozenset({"1", "2"}))

    def test_build_short_strategy_review_pass_under_additional_wrapper(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
    ) -> None:
        """Under short, the review pass is the external-only pass under the
        additional agent's wrapper."""
        pin_package_environment({})
        config = _make_config(
            review=ReviewConfig(
                agent="codex",
                strategy="short",
                additional=AdditionalReviewConfig(agent="cursor", patience=2, max_iterations=None),
            ),
        )

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 0
        assert mock_pass.call_count == 2

        second = mock_pass.call_args_list[1]
        assert second.args[2]["external_only"] is True
        assert "review" not in second.args[2]
        assert second.args[2]["review_patience"] == 2
        assert second.args[3] == "/home/goga/bin/cursor-as-claude.sh"

    def test_build_cli_no_skip_review_overrides_config_skip(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
    ) -> None:
        """CLI False beats config skip: true — the full two-pass cycle runs
        with validation active."""
        pin_package_environment({})
        config = _make_config(review=ReviewConfig(skip=True))

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={**_FULL_CLI_OPTIONS, "skip_review": False},
            )

        assert result == 0
        assert mock_pass.call_count == 2

    def test_build_review_pass_failure_propagates_and_keeps_plan(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
    ) -> None:
        """A failed review pass after a successful tasks pass: the LAST pass's
        code returns and the relocation outcome follows it."""
        pin_package_environment({})
        config = _make_config(review=ReviewConfig(agent="codex"))

        with mock.patch("goga.build.build.run_build_pass", side_effect=[0, 1]) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 1
        assert mock_pass.call_count == 2
        assert (tmp_path / "plan.md").is_file()
        assert not (tmp_path / "completed").exists()

    def test_build_empty_review_env_means_pure_inheritance(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
    ) -> None:
        """An empty review env is no layer at all — env None, never {}."""
        pin_package_environment({})
        config = _make_config(review=ReviewConfig(agent="codex", env={}))

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 0
        second = mock_pass.call_args_list[1]
        assert second.kwargs["env"] is None


# --- Pre-launch failure paths through the real collaborators ---


class TestPreLaunchFailures:
    def test_build_invalid_review_config_returns_1_before_side_effects(self, tmp_path, monkeypatch) -> None:
        """A bogus role is rejected by the real validation before any side effect."""
        config = _make_config(review=ReviewConfig(roles=["bogus"]))

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 1
        mock_pass.assert_not_called()
        assert not (tmp_path / ".ralphex").exists()

    def test_defaults_missing_returns_1(self, tmp_path, monkeypatch) -> None:
        """Missing vendored defaults abort the run before any pass."""
        from goga.build import ralphex_runtime

        monkeypatch.chdir(tmp_path)
        Path("plan.md").write_text("# plan\n")
        _pin_orchestration_boundary(monkeypatch, tmp_path)

        with (
            mock.patch.object(ralphex_runtime, "_VENDORED_PROMPTS", Path("/nonexistent")),
            mock.patch.object(ralphex_runtime, "_VENDORED_AGENTS", Path("/nonexistent")),
            mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass,
        ):
            result = build("plan.md", _make_config(), {"skip_manifest_check": True})

        assert result == 1
        mock_pass.assert_not_called()

    def test_missing_custom_prompts_dir_returns_1(self, tmp_path, monkeypatch) -> None:
        """A non-existent custom prompts_dir aborts at the sync, before any pass."""
        config = _make_config(prompts_dir="/nonexistent/prompts-path")

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 1
        mock_pass.assert_not_called()
        assert not (tmp_path / ".ralphex" / "prompts").exists()

    def test_no_build_agent_on_non_skipped_run_returns_1(self, tmp_path, monkeypatch) -> None:
        """Without an agent, the review-config validation rejects the run first
        (env-requires-agent aside, the None resolved agent is a clean error)."""
        config = _make_config(agent=None)

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 1
        mock_pass.assert_not_called()

    def test_returns_1_when_ralphex_missing(self, tmp_path, monkeypatch) -> None:
        """A PATH-missing ralphex (launcher exit 1) fails the tasks pass; the
        review pass never launches and subprocess is never invoked directly."""

        def _fail(*args, **kwargs):
            raise AssertionError("must not invoke subprocess.call")

        monkeypatch.setattr(subprocess, "call", _fail)

        with mock.patch("goga.build.build_pass.run_ralphex", return_value=1) as mock_run:
            result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={**_FULL_CLI_OPTIONS, "dry_run": False})

        assert result == 1
        mock_run.assert_called_once()


# --- Pass delegation and env boundaries ---


class TestPassDelegation:
    def test_build_returns_last_pass_exit_code(self, tmp_path, monkeypatch) -> None:
        """The returned code is the LAST executed pass's code, not an aggregate."""
        with mock.patch("goga.build.build.run_build_pass", side_effect=[0, 42]) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 42
        assert mock_pass.call_count == 2
        assert (tmp_path / "plan.md").is_file()

    def test_dry_run_reaches_every_pass(self, tmp_path, monkeypatch) -> None:
        """Both passes of a dry run rehearse with dry_run=True and the plan
        stays in place."""
        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                cli_options={**_FULL_CLI_OPTIONS, "dry_run": True},
            )

        assert result == 0
        assert mock_pass.call_count == 2
        assert all(call.args[4] is True for call in mock_pass.call_args_list)
        assert (tmp_path / "plan.md").is_file()
        assert not (tmp_path / "completed").exists()

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_does_not_write_claude_settings(self, mock_run, tmp_path, monkeypatch) -> None:
        config = _make_config(env=TEST_ENV_VARS)
        _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options=dict(_FULL_CLI_OPTIONS))

        assert not (tmp_path / ".claude" / "settings.json").exists()

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_repeated_build_overwrites(self, mock_run, tmp_path, monkeypatch) -> None:
        cli_options = {"skip_manifest_check": True}
        _run_build_in_tmp(tmp_path, monkeypatch, cli_options=cli_options)

        prompts_dir = tmp_path / ".ralphex" / "prompts"
        modified_file = prompts_dir / "task.txt"
        modified_file.write_text("USER MODIFICATION")

        _run_build_in_tmp(tmp_path, monkeypatch, cli_options=cli_options)
        assert modified_file.read_text() != "USER MODIFICATION"

    @mock.patch("goga.build.build_pass.run_ralphex", return_value=0)
    def test_custom_prompts_dir(self, mock_run, tmp_path, monkeypatch) -> None:
        custom_prompts = tmp_path / "custom" / "prompts"
        custom_prompts.mkdir(parents=True)
        (custom_prompts / "custom_task.txt").write_text("custom content")

        config = _make_config(prompts_dir=str(custom_prompts))
        _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options={"skip_manifest_check": True})

        copied = tmp_path / ".ralphex" / "prompts" / "custom_task.txt"
        assert copied.read_text() == "custom content"


# --- Review-scoped pass composition ---


class TestReviewScopedPassComposition:
    """Review-scoped options (base_ref, review_patience) join the review pass
    only; the tasks pass carries the tasks knobs only."""

    def test_scoped_options_only_on_review_pass(self, tmp_path, monkeypatch) -> None:
        config = _make_config(review=ReviewConfig(agent="codex", base_ref="origin/1.2.x"))

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={**_FULL_CLI_OPTIONS, "review_patience": 7},
            )

        assert result == 0
        first, second = mock_pass.call_args_list
        assert "base_ref" not in first.args[2]
        assert "review_patience" not in first.args[2]
        assert second.args[2]["base_ref"] == "origin/1.2.x"
        assert second.args[2]["review_patience"] == 7
        assert second.args[2]["review"] is True

    def test_tasks_knobs_bound_to_tasks_pass(self, tmp_path, monkeypatch) -> None:
        """The root knobs reach the tasks pass; the review pass carries the
        review session knobs with inheritance applied."""
        config = _make_config(
            session_timeout="30m",
            max_iterations=9,
            review=ReviewConfig(agent="codex", session_timeout="10m"),
        )

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, config=config, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 0
        first, second = mock_pass.call_args_list
        assert first.args[2]["session_timeout"] == "30m"
        assert first.args[2]["max_iterations"] == 9
        assert second.args[2]["session_timeout"] == "10m"
        assert "max_iterations" not in second.args[2]

    def test_cli_knobs_override_config(self, tmp_path, monkeypatch) -> None:
        config = _make_config(max_iterations=5, session_timeout="30m")

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={**_FULL_CLI_OPTIONS, "max_iterations": 10, "session_timeout": "99m"},
            )

        assert result == 0
        first = mock_pass.call_args_list[0]
        assert first.args[2]["max_iterations"] == 10
        assert first.args[2]["session_timeout"] == "99m"

    def test_skip_run_omits_scoped_options(self, tmp_path, monkeypatch) -> None:
        config = _make_config(review=ReviewConfig(skip=True, base_ref="origin/1.2.x"))

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={**_FULL_CLI_OPTIONS, "skip_review": True},
            )

        assert result == 0
        assert mock_pass.call_count == 1
        options = mock_pass.call_args.args[2]
        assert options["tasks_only"] is True
        assert "base_ref" not in options
        assert "review_patience" not in options

    def test_no_source_scoped_keys_absent(self, tmp_path, monkeypatch) -> None:
        """With neither a config source nor CLI values, the review pass options
        carry exactly the mode flag."""
        from goga.ralphex.run_ralphex import _build_command

        with mock.patch("goga.build.build.run_build_pass", return_value=0) as mock_pass:
            result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 0
        second_options = mock_pass.call_args_list[1].args[2]
        assert second_options == {"review": True}
        assert _build_command("plan.md", second_options) == [
            "ralphex",
            "plan.md",
            "--config-dir",
            ".ralphex/",
            "--review",
        ]


# --- .ralphex/ lifecycle reuse ---


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
        result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options={"skip_manifest_check": False})
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
        assert not hasattr(build_module, "_cleanup_ralphex_dir")

    def test_retired_helpers_removed_from_module(self) -> None:
        """The superseded private option helpers are gone — their contracts
        were absorbed by resolve_run_settings / compose_pass_options."""
        assert not hasattr(build_module, "_resolve_options")
        assert not hasattr(build_module, "_review_scoped_options")

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


# --- Integration: secret-safe dry-run across the orchestration/launcher seam ---


class TestBuildDryRunSecretSafeIntegration:
    """Cross-entity scenario joining the orchestrator (goga/build) with the
    launcher's print (goga/ralphex): a two-pass dry run prints the argv of both
    passes and never the contents of any env layer.

    The real launcher and the real pass executor run here: the dry-run branch
    performs no PATH check and no subprocess, so the seam under test is the
    actual print the container would emit — a regression in either the
    orchestration (folding an env into the options) or the launcher's print
    fails this test."""

    def test_build_dry_run_two_pass_no_env_in_output(self, tmp_path, monkeypatch, capsys) -> None:
        config = _make_config(
            env={"TASKS_SECRET": "tasks-value"},
            review=ReviewConfig(agent="codex", env={"ANTHROPIC_MODEL": "reviewer"}),
        )

        with _mock_vendored_sources(tmp_path):
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={**_FULL_CLI_OPTIONS, "dry_run": True},
            )

        assert result == 0
        captured = capsys.readouterr()
        # Both planned passes had their argv printed to stderr.
        assert captured.err.count("ralphex") >= 2
        assert "--tasks-only" in captured.err
        assert "--review" in captured.err
        # No env layer value or name reaches the dry-run output.
        assert "reviewer" not in captured.err
        assert "ANTHROPIC_MODEL" not in captured.err
        assert "tasks-value" not in captured.err
        assert "TASKS_SECRET" not in captured.err
        # A dry run relocates nothing.
        assert (tmp_path / "plan.md").is_file()
        assert not (tmp_path / "completed").exists()
