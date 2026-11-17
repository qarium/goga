"""Logic tests of ``merge_workflow_build`` — key-wise layering and construction rules."""

from __future__ import annotations

from goga.build import merge_workflow_build, resolve_run_settings
from goga.config import AdditionalReviewConfig, BuildConfig, ReviewConfig
from goga.pipeline.workflow import WorkflowBuild


class TestMergeWorkflowBuild:
    def test_keywise_env_and_agents(self) -> None:
        config = BuildConfig(
            agent="claude",
            env={"A": "1"},
            max_iterations=7,
            proxy="http://p",
            review=ReviewConfig(
                agent="codex",
                env={"C": "3"},
                roles=["quality"],
                additional=AdditionalReviewConfig(agent="gemini", patience=3, max_iterations=5, env={"X": "9"}),
            ),
        )
        block = WorkflowBuild(env={"B": "over"}, review_env={"D": "4"})

        merged = merge_workflow_build(config, block)

        assert merged.env == {"A": "1", "B": "over"}
        assert merged.agent == "claude"
        assert merged.review is not None
        assert merged.review.env == {"C": "3", "D": "4"}
        assert merged.review.agent == "codex"
        expected_additional = AdditionalReviewConfig(agent="gemini", patience=3, max_iterations=5, env={"X": "9"})

        assert merged.review.additional == expected_additional

        assert merged.max_iterations == 7
        assert merged.proxy == "http://p"
        assert merged.review.roles == ["quality"]

        assert config.env == {"A": "1"}
        assert config.review is not None
        assert config.review.env == {"C": "3"}
        assert config.review.additional is not None
        assert config.review.additional.env == {"X": "9"}

    def test_agents_override_when_set(self) -> None:
        config = BuildConfig(
            agent="claude",
            review=ReviewConfig(agent="codex", additional=AdditionalReviewConfig(agent="gemini")),
        )
        block = WorkflowBuild(agent="aider", review_agent="cursor", review_additional_agent="copilot")

        merged = merge_workflow_build(config, block)

        assert merged.agent == "aider"
        assert merged.review is not None
        assert merged.review.agent == "cursor"
        assert merged.review.additional is not None
        assert merged.review.additional.agent == "copilot"

    def test_constructs_review_when_none(self) -> None:
        config = BuildConfig(env={"A": "1"})
        block = WorkflowBuild(review_additional_agent="gemini")

        merged = merge_workflow_build(config, block)

        assert merged.review is not None
        assert isinstance(merged.review, ReviewConfig)
        assert merged.review.agent is None
        assert merged.review.env == {}
        assert merged.review.additional == AdditionalReviewConfig(agent="gemini", env={})

        assert merged.review.skip is None
        assert merged.review.roles is None
        assert merged.review.base_ref is None
        assert merged.review.strategy is None
        assert merged.review.finalize is None
        assert merged.review.session_timeout is None
        assert merged.review.idle_timeout is None
        assert merged.review.wait is None
        assert merged.review.max_iterations is None

    def test_constructs_review_from_set_fields_only(self) -> None:
        merged = merge_workflow_build(BuildConfig(), WorkflowBuild(review_agent="codex", review_env={"R": "1"}))

        assert merged.review is not None
        assert merged.review.agent == "codex"
        assert merged.review.env == {"R": "1"}
        assert merged.review.additional is None

    def test_absent_fields_never_override(self) -> None:
        config = BuildConfig(
            env={"A": "1"},
            review=ReviewConfig(env={"C": "3"}, additional=AdditionalReviewConfig(patience=2)),
        )
        block = WorkflowBuild(agent="claude")

        merged = merge_workflow_build(config, block)

        assert merged.agent == "claude"
        assert merged.env == {"A": "1"}

        assert merged.review is not None
        assert merged.review.agent is None
        assert merged.review.env == {"C": "3"}
        assert merged.review.additional is not None
        assert merged.review.additional.agent is None
        assert merged.review.additional.patience == 2
        assert merged.review.additional.env == {}

        no_review_block = merge_workflow_build(BuildConfig(proxy="http://p"), WorkflowBuild(agent="claude"))

        assert no_review_block.review is None
        assert no_review_block.proxy == "http://p"

    def test_builds_new_models_and_never_mutates_inputs(self) -> None:
        additional = AdditionalReviewConfig(agent="gemini", env={"X": "9"})
        review = ReviewConfig(agent="codex", env={"C": "3"}, additional=additional)
        config = BuildConfig(agent="claude", env={"A": "1"}, review=review)
        block = WorkflowBuild(env={"A": "over"}, review_env={"C": "over"})

        merged = merge_workflow_build(config, block)

        assert merged is not config
        assert merged.review is not review
        assert merged.review is not config.review
        assert merged.review.additional is not additional

        assert merged.env == {"A": "over"}
        assert merged.review is not None
        assert merged.review.env == {"C": "over"}

        assert config.env == {"A": "1"}
        assert review.env == {"C": "3"}
        assert additional.env == {"X": "9"}

    def test_constructs_additional_when_review_present_and_block_sets_it(self) -> None:
        config = BuildConfig(review=ReviewConfig(env={"C": "3"}))
        block = WorkflowBuild(review_additional_env={"Z": "1"})

        merged = merge_workflow_build(config, block)

        assert merged.review is not None
        assert merged.review.additional is not None
        assert merged.review.additional.agent is None
        assert merged.review.additional.env == {"Z": "1"}
        assert merged.review.additional.patience is None
        assert merged.review.additional.max_iterations is None


class TestMergeWorkflowBuildGlobalLayering:
    def test_merge_workflow_build_four_layer_agent_precedence(self) -> None:
        config = BuildConfig(
            agent="cfg-root",
            review=ReviewConfig(
                agent="cfg-rev",
                additional=AdditionalReviewConfig(agent="cfg-add"),
            ),
        )
        block = WorkflowBuild(review_agent="blk-rev")

        merged = merge_workflow_build(config, block, "g-global", None)

        assert merged.agent == "g-global"
        assert merged.review is not None
        assert merged.review.agent == "blk-rev"
        assert merged.review.additional is not None
        assert merged.review.additional.agent == "g-global"

    def test_merge_workflow_build_env_layering_config_global_block(self) -> None:
        config = BuildConfig(
            env={"R": "cfg", "S": "cfg"},
            review=ReviewConfig(env={"X": "cfg"}),
        )
        block = WorkflowBuild(env={"R": "blk"}, review_env={"X": "blk"})

        merged = merge_workflow_build(config, block, None, {"S": "glob", "T": "glob"})

        assert merged.env == {"R": "blk", "S": "glob", "T": "glob"}
        assert merged.review is not None
        assert merged.review.env == {"X": "blk", "S": "glob", "T": "glob"}
        assert merged.review.additional is not None
        assert merged.review.additional.env == {"S": "glob", "T": "glob"}

        assert config.env == {"R": "cfg", "S": "cfg"}
        assert config.review is not None
        assert config.review.env == {"X": "cfg"}

    def test_merge_workflow_build_globals_with_none_block(self) -> None:
        config = BuildConfig(env={"A": "1"}, review=None)

        merged = merge_workflow_build(config, None, "g", {"E": "2"})

        assert merged.agent == "g"
        assert merged.env == {"A": "1", "E": "2"}

        assert merged.review is not None
        assert isinstance(merged.review, ReviewConfig)
        assert merged.review.agent == "g"
        assert merged.review.env == {"E": "2"}
        assert merged.review.additional is not None
        assert isinstance(merged.review.additional, AdditionalReviewConfig)
        assert merged.review.additional.agent == "g"
        assert merged.review.additional.env == {"E": "2"}

        assert merged.review.skip is None
        assert merged.review.roles is None
        assert merged.review.additional.patience is None
        assert merged.review.additional.max_iterations is None

        assert config.review is None

    def test_merge_workflow_build_globals_none_matches_block_only_overlay(self) -> None:
        config = BuildConfig(
            agent="cfg-root",
            env={"A": "1"},
            proxy="http://p",
            review=ReviewConfig(
                agent="cfg-rev",
                env={"C": "3"},
                roles=["quality"],
                additional=AdditionalReviewConfig(agent="gemini", patience=3, env={"X": "9"}),
            ),
        )
        block = WorkflowBuild(agent="blk", env={"B": "over"}, review_agent="blk-rev", review_env={"D": "4"})

        merged = merge_workflow_build(config, block, None, None)

        assert merged.agent == "blk"
        assert merged.env == {"A": "1", "B": "over"}
        assert merged.proxy == "http://p"
        assert merged.review is not None
        assert merged.review.agent == "blk-rev"
        assert merged.review.env == {"C": "3", "D": "4"}
        assert merged.review.roles == ["quality"]
        assert merged.review.additional is not None
        assert merged.review.additional.agent == "gemini"
        assert merged.review.additional.env == {"X": "9"}
        assert merged.review.additional.patience == 3

        no_review_config = BuildConfig(proxy="http://p")

        no_review_merged = merge_workflow_build(no_review_config, WorkflowBuild(agent="blk"), None, None)

        assert no_review_merged.review is None
        assert no_review_merged.proxy == "http://p"

        copied = merge_workflow_build(config, None, None, None)

        assert copied == config
        assert copied is not config

    def test_merge_workflow_build_never_mutates_inputs(self) -> None:
        additional = AdditionalReviewConfig(agent="gemini", env={"X": "9"}, patience=3, max_iterations=5)
        review = ReviewConfig(agent="codex", env={"C": "3"}, roles=["quality"], additional=additional)
        config = BuildConfig(agent="claude", env={"A": "1"}, proxy="http://p", hosts={"h": "1"}, review=review)
        block = WorkflowBuild(env={"A": "over"}, review_env={"C": "over"}, review_additional_env={"X": "over"})
        global_env = {"A": "glob", "C": "glob", "X": "glob"}

        merged = merge_workflow_build(config, block, "g-global", global_env)

        assert merged is not config
        assert merged.review is not review
        assert merged.review is not config.review
        assert merged.review.additional is not additional

        assert merged.env == {"A": "over", "C": "glob", "X": "glob"}
        assert merged.review is not None
        assert merged.review.env == {"C": "over", "A": "glob", "X": "glob"}
        assert merged.review.additional is not None
        assert merged.review.additional.env == {"X": "over", "A": "glob", "C": "glob"}

        assert config.env == {"A": "1"}
        assert review.env == {"C": "3"}
        assert additional.env == {"X": "9"}
        assert block.env == {"A": "over"}
        assert global_env == {"A": "glob", "C": "glob", "X": "glob"}

    def test_empty_string_block_agent_falls_through_to_global(self) -> None:
        config = BuildConfig(agent="cfg-root")

        to_global = merge_workflow_build(config, WorkflowBuild(agent=""), "glob", None)

        assert to_global.agent == "glob"

        to_config = merge_workflow_build(config, WorkflowBuild(agent=""), None, None)

        assert to_config.agent == "cfg-root"


class TestBuildCascadeIntegration:
    """Integration — the layered root feeds the settings resolution cascade."""

    def test_build_cascade_runs_from_layered_root(self) -> None:
        """The agent-inheritance cascade of ``resolve_run_settings`` runs from the LAYERED root.

        The configuration roots the tasks agent at "cfg-root" with a review
        part whose agent is unset; the workflow global agent "g" (no build
        block) overrides the root through ``merge_workflow_build``, and the
        settings resolution consumes the layered value — the review and tasks
        agents both resolve "g", never "cfg-root" (the unlayered cascade
        would inherit the configuration root instead).
        """
        config = BuildConfig(agent="cfg-root", review=ReviewConfig(agent=None))

        layered = merge_workflow_build(config, None, "g", None)
        settings = resolve_run_settings(layered, {})

        assert settings.tasks.agent == "g"
        assert settings.review.agent == "g"
        assert settings.review.additional.agent == "g"
