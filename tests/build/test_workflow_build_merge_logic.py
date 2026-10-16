"""Logic tests of ``merge_workflow_build`` — key-wise layering and construction rules."""

from __future__ import annotations

from goga.build import merge_workflow_build
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
