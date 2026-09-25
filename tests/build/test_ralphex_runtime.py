from __future__ import annotations

import inspect
import typing
from pathlib import Path

import pytest
from goga.build.ralphex_runtime import sync_ralphex_defaults
from goga.build.run_settings import PassSettings, ReviewPassSettings, RunSettings
from goga.config import AdditionalReviewConfig, BuildConfig

_PROMPT_ROLES = ("quality", "implementation", "testing", "simplification", "documentation")
_SECOND_ROLES = ("quality", "implementation")

_REVIEW_FIRST_TEMPLATE = """# first review prompt
# this prompt is used for the first (comprehensive) review pass in phase 2
# launches 5 parallel reviewer agents for thorough code review
#
# available variables:
#   {{plan_path}} - expands to the absolute path of the plan file
#   {{agent:<name>}} - expands to the executor-appropriate agent invocation
#
# available agents:
#   quality, implementation, testing, simplification, documentation

## Step 1: Understand the Change

Run both commands to understand what was done:
- `git log --oneline -20`
- `git diff HEAD~1`

## Step 2: Launch ALL 5 Review Agents IN PARALLEL

CRITICAL: All 5 agent invocations MUST be issued in a single message for true parallel execution.
These agents are fully independent — no shared state, no dependencies between them, no ordering requirements.

{{agent:quality}}
{{agent:implementation}}
{{agent:testing}}
{{agent:simplification}}
{{agent:documentation}}

CRITICAL: Do NOT proceed to Step 3 until ALL 5 agents have returned results.

## Step 3: Collect and Verify

After agents complete:
- Merge findings from all agents
- Verify each finding against the actual code
"""

_REVIEW_SECOND_TEMPLATE = """# second review prompt
# focuses on critical/major issues only, uses 2 agents
#
# available variables:
#   {{plan_path}} - expands to the absolute path of the plan file
#   {{agent:<name>}} - expands to the executor-appropriate agent invocation
#
# available agents:
#   quality, implementation

## Step 1: Understand the Change

Run both commands to understand what was done:
- `git log --oneline -20`
- `git diff HEAD~1`

## Step 2: Launch Review Agents IN PARALLEL

CRITICAL: Both agent invocations MUST be issued in a single message for true parallel execution.
These agents are fully independent — no shared state, no dependencies between them, no ordering requirements.
Under claude executor: do NOT use run_in_background. Foreground Task tool calls in the same message run in parallel.
Under codex executor: do NOT serialize spawn_agent calls; emit them both in one response and then call wait_agent.

{{agent:quality}}
{{agent:implementation}}

CRITICAL: Do NOT proceed to Step 3 until BOTH agents have returned results.

## Step 3: Collect and Verify

After agents complete:
- Merge findings from all agents
"""

_TASK_TEMPLATE = "# task prompt\n# executes the plan tasks one by one\n"

_CODEX_TEMPLATE = "# codex review prompt\n"


def _make_build_config(**kwargs) -> BuildConfig:
    return BuildConfig(agent=kwargs.pop("agent", "claude"), env={}, **kwargs)


def _make_settings(roles: list[str] | None = None, finalize: str | None = None) -> RunSettings:
    """Run plan carrying exactly the facts the sync reads: roles and finalize of the review part."""
    return RunSettings(
        skip=False,
        tasks=PassSettings(agent="claude", env={}),
        review=ReviewPassSettings(
            agent="claude",
            env={},
            roles=roles,
            strategy="medium",
            finalize=finalize,
            additional=AdditionalReviewConfig(agent="claude", patience=None, max_iterations=None),
        ),
    )


def _write_prompt_sources(prompts_dir: Path) -> None:
    (prompts_dir / "task.txt").write_text(_TASK_TEMPLATE)
    (prompts_dir / "codex.txt").write_text(_CODEX_TEMPLATE)
    (prompts_dir / "review_first.txt").write_text(_REVIEW_FIRST_TEMPLATE)
    (prompts_dir / "review_second.txt").write_text(_REVIEW_SECOND_TEMPLATE)


def _write_agent_sources(agents_dir: Path) -> None:
    for role in _PROMPT_ROLES:
        (agents_dir / f"{role}.txt").write_text(f"# {role} agent definition\n")


@pytest.fixture
def vendored_sources(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "vendored-prompts"
    agents_dir = tmp_path / "vendored-agents"
    prompts_dir.mkdir()
    agents_dir.mkdir()
    _write_prompt_sources(prompts_dir)
    _write_agent_sources(agents_dir)

    from goga.build import ralphex_runtime

    monkeypatch.setattr(ralphex_runtime, "_VENDORED_PROMPTS", prompts_dir)
    monkeypatch.setattr(ralphex_runtime, "_VENDORED_AGENTS", agents_dir)
    return prompts_dir, agents_dir


class TestSyncRalphexDefaultsContract:
    def test_sync_ralphex_defaults_importable_from_module(self) -> None:
        assert callable(sync_ralphex_defaults)

    def test_sync_ralphex_defaults_has_correct_signature(self) -> None:
        sig = inspect.signature(sync_ralphex_defaults)
        params = list(sig.parameters.keys())
        assert params == ["config", "settings"]

    def test_sync_ralphex_defaults_param_types(self) -> None:
        hints = typing.get_type_hints(sync_ralphex_defaults)
        assert hints.get("config") is BuildConfig
        assert hints.get("settings") is RunSettings

    def test_sync_ralphex_defaults_returns_none(self) -> None:
        hints = typing.get_type_hints(sync_ralphex_defaults)
        assert hints.get("return") is type(None)

    def test_vendored_constants_point_into_assets(self) -> None:
        from goga.build.ralphex_runtime import _VENDORED_AGENTS, _VENDORED_PROMPTS

        package_root = Path(__file__).resolve().parents[2]
        assert package_root / "goga" / "assets" / "ralphex" / "prompts" == _VENDORED_PROMPTS
        assert package_root / "goga" / "assets" / "ralphex" / "agents" == _VENDORED_AGENTS


class TestSyncRalphexDefaultsLogic:
    def test_sync_ralphex_defaults_full_rewrite_byte_identical(self, tmp_path, monkeypatch, vendored_sources) -> None:
        prompts_src, agents_src = vendored_sources
        monkeypatch.chdir(tmp_path)

        stale = Path(".ralphex") / "prompts"
        stale.mkdir(parents=True)
        (stale / "obsolete.txt").write_text("stale content\n")

        sync_ralphex_defaults(_make_build_config(), _make_settings(roles=None))

        dest_prompts = tmp_path / ".ralphex" / "prompts"
        assert not (dest_prompts / "obsolete.txt").exists()
        assert {p.name for p in dest_prompts.iterdir()} == {
            "task.txt",
            "review_first.txt",
            "review_second.txt",
            "codex.txt",
        }
        assert (dest_prompts / "review_first.txt").read_bytes() == (prompts_src / "review_first.txt").read_bytes()
        assert (dest_prompts / "review_second.txt").read_bytes() == (prompts_src / "review_second.txt").read_bytes()
        assert (dest_prompts / "task.txt").read_bytes() == (prompts_src / "task.txt").read_bytes()

        dest_agents = tmp_path / ".ralphex" / "agents"
        assert {a.name for a in dest_agents.iterdir()} == {f"{role}.txt" for role in _PROMPT_ROLES}
        for role in _PROMPT_ROLES:
            assert (dest_agents / f"{role}.txt").read_bytes() == (agents_src / f"{role}.txt").read_bytes()

    def test_sync_ralphex_defaults_full_roles_byte_identical(self, tmp_path, monkeypatch, vendored_sources) -> None:
        prompts_src, _ = vendored_sources
        monkeypatch.chdir(tmp_path)

        sync_ralphex_defaults(_make_build_config(), _make_settings(roles=list(_PROMPT_ROLES)))

        dest_prompts = tmp_path / ".ralphex" / "prompts"
        assert (dest_prompts / "review_first.txt").read_bytes() == (prompts_src / "review_first.txt").read_bytes()
        assert (dest_prompts / "review_second.txt").read_bytes() == (prompts_src / "review_second.txt").read_bytes()

    def test_sync_filters_roles_and_adapts_counters(self, tmp_path, monkeypatch, vendored_sources) -> None:
        prompts_src, _ = vendored_sources
        monkeypatch.chdir(tmp_path)

        sync_ralphex_defaults(_make_build_config(), _make_settings(roles=["quality", "testing"]))

        first = (tmp_path / ".ralphex" / "prompts" / "review_first.txt").read_text()
        assert "{{agent:quality}}" in first
        assert "{{agent:testing}}" in first
        assert "{{agent:implementation}}" not in first
        assert "{{agent:simplification}}" not in first
        assert "{{agent:documentation}}" not in first
        assert "Launch ALL 2 Review Agents" in first

        second = (tmp_path / ".ralphex" / "prompts" / "review_second.txt").read_text()
        assert "{{agent:quality}}" in second
        assert "{{agent:implementation}}" not in second
        assert "uses 1 agents" in second
        assert "until the agent" in second

        assert (tmp_path / ".ralphex" / "prompts" / "task.txt").read_bytes() == (prompts_src / "task.txt").read_bytes()

    def test_sync_ralphex_defaults_empty_roles_eq_absent(self, tmp_path, monkeypatch, vendored_sources) -> None:
        prompts_src, _ = vendored_sources
        monkeypatch.chdir(tmp_path)

        sync_ralphex_defaults(_make_build_config(), _make_settings(roles=[]))

        dest_prompts = tmp_path / ".ralphex" / "prompts"
        assert (dest_prompts / "review_first.txt").read_bytes() == (prompts_src / "review_first.txt").read_bytes()

    def test_sync_ralphex_defaults_missing_vendored_source_raises(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        from goga.build import ralphex_runtime

        monkeypatch.setattr(
            ralphex_runtime,
            "_VENDORED_PROMPTS",
            tmp_path / "does-not-exist" / "prompts",
        )
        monkeypatch.setattr(
            ralphex_runtime,
            "_VENDORED_AGENTS",
            tmp_path / "does-not-exist" / "agents",
        )

        with pytest.raises(ValueError, match="dump-defaults"):
            sync_ralphex_defaults(_make_build_config(), _make_settings(roles=None))

    def test_sync_ralphex_defaults_empty_intersection(self, tmp_path, monkeypatch, vendored_sources) -> None:
        monkeypatch.chdir(tmp_path)

        sync_ralphex_defaults(_make_build_config(), _make_settings(roles=["codex"]))

        first = (tmp_path / ".ralphex" / "prompts" / "review_first.txt").read_text()
        second = (tmp_path / ".ralphex" / "prompts" / "review_second.txt").read_text()

        for role in _PROMPT_ROLES:
            assert f"{{{{agent:{role}}}}}" not in first
            assert f"{{{{agent:{role}}}}}" not in second
        assert first.strip()
        assert second.strip()

    def test_sync_ralphex_defaults_custom_dirs_copied_as_is(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        custom_prompts = tmp_path / "custom-prompts"
        custom_agents = tmp_path / "custom-agents"
        custom_prompts.mkdir()
        custom_agents.mkdir()
        (custom_prompts / "review_first.txt").write_text("custom review first\n")
        (custom_prompts / "review_second.txt").write_text("custom review second\n")
        (custom_prompts / "task.txt").write_text("custom task\n")
        (custom_agents / "quality.txt").write_text("custom quality agent\n")

        config = _make_build_config(prompts_dir=str(custom_prompts), agents_dir=str(custom_agents))
        sync_ralphex_defaults(config, _make_settings(roles=["quality"]))

        dest_prompts = tmp_path / ".ralphex" / "prompts"
        assert (dest_prompts / "review_first.txt").read_bytes() == (custom_prompts / "review_first.txt").read_bytes()
        assert (dest_prompts / "review_second.txt").read_bytes() == (custom_prompts / "review_second.txt").read_bytes()
        assert (dest_prompts / "task.txt").read_bytes() == (custom_prompts / "task.txt").read_bytes()
        dest_agents = tmp_path / ".ralphex" / "agents"
        assert (dest_agents / "quality.txt").read_bytes() == (custom_agents / "quality.txt").read_bytes()

    def test_sync_ralphex_defaults_partial_custom_independent_sources(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        custom_agents = tmp_path / "custom-agents"
        custom_agents.mkdir()
        (custom_agents / "quality.txt").write_text("custom quality agent\n")
        from goga.build import ralphex_runtime

        monkeypatch.setattr(
            ralphex_runtime,
            "_VENDORED_PROMPTS",
            tmp_path / "does-not-exist" / "prompts",
        )

        config = _make_build_config(agents_dir=str(custom_agents))
        with pytest.raises(ValueError, match="vendored ralphex defaults not found") as excinfo:
            sync_ralphex_defaults(config, _make_settings(roles=None))

        assert "prompts" in str(excinfo.value)
        assert str(tmp_path / "does-not-exist" / "prompts") in str(excinfo.value)

    def test_filter_review_prompt_counts_by_remaining_lines(self, tmp_path, monkeypatch, vendored_sources) -> None:
        monkeypatch.chdir(tmp_path)

        sync_ralphex_defaults(_make_build_config(), _make_settings(roles=["testing"]))

        first = (tmp_path / ".ralphex" / "prompts" / "review_first.txt").read_text()
        assert "{{agent:testing}}" in first
        assert "Launch ALL 1 Review Agents" in first

    def test_filter_review_prompt_zero_remaining_lines_leaves_counters_untouched(
        self, tmp_path, monkeypatch, vendored_sources
    ) -> None:
        """A whitelisted role absent from a phase (testing is not in review_second's
        default set) leaves n == 0 — a regular phase without subagents, so the
        accompanying text keeps its source wording, with no counter rewrites."""
        monkeypatch.chdir(tmp_path)

        sync_ralphex_defaults(_make_build_config(), _make_settings(roles=["testing"]))

        second = (tmp_path / ".ralphex" / "prompts" / "review_second.txt").read_text()

        for role in _SECOND_ROLES:
            assert f"{{{{agent:{role}}}}}" not in second
        assert "uses 2 agents" in second
        assert "Both agent invocations" in second
        assert "until BOTH agents" in second
        assert "uses 0 agents" not in second
        assert "The agent invocation" not in second
        assert "until the agent" not in second

    def test_sync_ralphex_defaults_materializes_finalize(self, tmp_path, monkeypatch, vendored_sources) -> None:
        monkeypatch.chdir(tmp_path)

        settings = _make_settings(finalize="Final pass: merge the review.")
        sync_ralphex_defaults(_make_build_config(), settings)

        finalize_file = tmp_path / ".ralphex" / "agents" / "finalize.txt"
        assert finalize_file.read_text() == "Final pass: merge the review."

        # The step artifact is goga's own file — it materializes even when the
        # agents source is a custom directory that does not carry it.
        custom_agents = tmp_path / "custom-agents"
        custom_agents.mkdir()
        (custom_agents / "quality.txt").write_text("custom quality agent\n")

        sync_ralphex_defaults(_make_build_config(agents_dir=str(custom_agents)), settings)
        assert finalize_file.read_text() == "Final pass: merge the review."

        # Unset finalize writes nothing — and the full rewrite clears a stale
        # finalize.txt left by a previous run, so the step falls back to the
        # ralphex default (off).
        sync_ralphex_defaults(_make_build_config(), _make_settings(finalize=None))
        assert not finalize_file.exists()

    def test_sync_ralphex_defaults_never_touches_ralphex_config(self, tmp_path, monkeypatch, vendored_sources) -> None:
        """`.ralphex/config` belongs to the config routine; the sync leaves it byte-identical."""
        monkeypatch.chdir(tmp_path)
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        sentinel = ralphex_dir / "config"
        sentinel.write_text("claude_command = /sentinel\n")

        sync_ralphex_defaults(_make_build_config(), _make_settings(roles=["quality"], finalize="done"))

        assert sentinel.read_text() == "claude_command = /sentinel\n"
