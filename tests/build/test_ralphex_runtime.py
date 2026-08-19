from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path

import pytest
from goga.build.ralphex_runtime import sync_ralphex_defaults
from goga.build.review_options import ReviewOptions
from goga.config import BuildConfig, TaskExecutorConfig

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


@dataclass(kw_only=True, frozen=True)
class _StubReview:
    """Duck-typed stand-in for ReviewOptions until Task 7 lands."""

    skip: bool = False
    review_agent: str | None = None
    roles: list[str] | None = None
    two_pass: bool = False


def _make_build_config(**kwargs) -> BuildConfig:
    task_executor = TaskExecutorConfig(agent=kwargs.pop("agent", "claude"), env={})
    return BuildConfig(task_executor=task_executor, **kwargs)


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
        assert params == ["config", "review"]

    def test_sync_ralphex_defaults_config_param_type(self) -> None:
        # ReviewOptions (Task 7) stays an unresolvable string annotation by design,
        # so raw signature annotations are asserted instead of get_type_hints.
        sig = inspect.signature(sync_ralphex_defaults)
        assert sig.parameters["config"].annotation == "BuildConfig"

    def test_sync_ralphex_defaults_review_param_is_string_annotation(self) -> None:
        """`from __future__ import annotations` keeps every annotation a string, import or not."""
        sig = inspect.signature(sync_ralphex_defaults)
        assert sig.parameters["review"].annotation == "ReviewOptions"

    def test_sync_ralphex_defaults_returns_none(self) -> None:
        sig = inspect.signature(sync_ralphex_defaults)
        assert sig.return_annotation == "None"

    def test_review_options_imported_from_sibling_module(self) -> None:
        """Since Task 7 the parameter type is a real relative import, not a duck-typed placeholder."""
        import goga.build.ralphex_runtime as module

        assert module.ReviewOptions is ReviewOptions

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

        sync_ralphex_defaults(_make_build_config(), _StubReview(roles=None))

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

        sync_ralphex_defaults(_make_build_config(), _StubReview(roles=list(_PROMPT_ROLES)))

        dest_prompts = tmp_path / ".ralphex" / "prompts"
        assert (dest_prompts / "review_first.txt").read_bytes() == (prompts_src / "review_first.txt").read_bytes()
        assert (dest_prompts / "review_second.txt").read_bytes() == (prompts_src / "review_second.txt").read_bytes()

    def test_sync_filters_roles_and_adapts_counters(self, tmp_path, monkeypatch, vendored_sources) -> None:
        prompts_src, _ = vendored_sources
        monkeypatch.chdir(tmp_path)

        sync_ralphex_defaults(_make_build_config(), _StubReview(roles=["quality", "testing"]))

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

        sync_ralphex_defaults(_make_build_config(), _StubReview(roles=[]))

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
            sync_ralphex_defaults(_make_build_config(), _StubReview(roles=None))

    def test_sync_ralphex_defaults_empty_intersection(self, tmp_path, monkeypatch, vendored_sources) -> None:
        monkeypatch.chdir(tmp_path)

        sync_ralphex_defaults(_make_build_config(), _StubReview(roles=["codex"]))

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
        sync_ralphex_defaults(config, _StubReview(roles=["quality"]))

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
            sync_ralphex_defaults(config, _StubReview(roles=None))

        assert "prompts" in str(excinfo.value)
        assert str(tmp_path / "does-not-exist" / "prompts") in str(excinfo.value)

    def test_filter_review_prompt_counts_by_remaining_lines(self, tmp_path, monkeypatch, vendored_sources) -> None:
        monkeypatch.chdir(tmp_path)

        sync_ralphex_defaults(_make_build_config(), _StubReview(roles=["testing"]))

        first = (tmp_path / ".ralphex" / "prompts" / "review_first.txt").read_text()
        assert "{{agent:testing}}" in first
        assert "Launch ALL 1 Review Agents" in first
