"""Logic tests for the ``WorkflowBuild`` dataclass.

Covers behavior beyond the contract surface: the all-``None`` defaults (the
"block absent" shape), partial construction per role, verbatim map storage,
and the plain (non-frozen) kw_only nature the contract prescribes.
"""

from __future__ import annotations

from goga.pipeline.workflow import WorkflowBuild


class TestWorkflowBuildLogic:
    """Logic tests — value carriage of the ``WorkflowBuild`` dataclass."""

    def test_defaults_all_six_fields_none(self) -> None:
        """The no-argument construction carries None in every one of the six fields."""
        build = WorkflowBuild()

        assert build.agent is None
        assert build.env is None
        assert build.review_agent is None
        assert build.review_env is None
        assert build.review_additional_agent is None
        assert build.review_additional_env is None

    def test_explicit_all_none_equals_default_construction(self) -> None:
        """A construction with every field explicitly None equals the default one."""
        explicit = WorkflowBuild(
            agent=None,
            env=None,
            review_agent=None,
            review_env=None,
            review_additional_agent=None,
            review_additional_env=None,
        )

        assert explicit == WorkflowBuild()

    def test_partial_construction_agent_only(self) -> None:
        """Specifying only ``agent`` leaves the other five fields at None."""
        build = WorkflowBuild(agent="codex")

        assert build.agent == "codex"
        assert build.env is None
        assert build.review_agent is None
        assert build.review_env is None
        assert build.review_additional_agent is None
        assert build.review_additional_env is None

    def test_partial_construction_review_role_only(self) -> None:
        """Specifying only the review role leaves the tasks and additional roles untouched."""
        build = WorkflowBuild(review_agent="claude", review_env={"C": "3"})

        assert build.agent is None
        assert build.env is None
        assert build.review_agent == "claude"
        assert build.review_env == {"C": "3"}
        assert build.review_additional_agent is None
        assert build.review_additional_env is None

    def test_env_maps_stored_verbatim(self) -> None:
        """The three env overlays store their keyword-passed maps verbatim (same objects)."""
        env = {"A": "1"}
        review_env = {"C": "3"}
        additional_env = {"E": "5"}
        build = WorkflowBuild(env=env, review_env=review_env, review_additional_env=additional_env)

        assert build.env is env
        assert build.review_env is review_env
        assert build.review_additional_env is additional_env

    def test_model_is_plain_kw_only_not_frozen(self) -> None:
        """The dataclass is plain kw_only (NOT frozen) — assignment works, per the contract."""
        build = WorkflowBuild()
        build.agent = "codex"
        build.review_additional_env = {"E": "5"}

        assert build.agent == "codex"
        assert build.review_additional_env == {"E": "5"}

    def test_equality_of_identical_constructions(self) -> None:
        """Two builds with identical fields compare equal."""
        first = WorkflowBuild(agent="codex", env={"A": "1"})
        second = WorkflowBuild(agent="codex", env={"A": "1"})

        assert first == second
