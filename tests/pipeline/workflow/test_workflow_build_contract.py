"""Contract tests for the ``WorkflowBuild`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the six
declared properties in the fixed canonical order (``agent``, ``env``,
``review_agent``, ``review_env``, ``review_additional_agent``,
``review_additional_env``), the all-``None`` defaults, and kw_only
construction. These tests pin the contract surface — behavior lives in the
logic test module.
"""

from __future__ import annotations

from dataclasses import fields

import pytest
from goga.pipeline.workflow import WorkflowBuild


class TestWorkflowBuildContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_workflow_build_importable_from_facade(self) -> None:
        """WorkflowBuild is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.WorkflowBuild is WorkflowBuild
        assert "WorkflowBuild" in facade.__all__

    def test_workflow_build_has_agent_property(self) -> None:
        """WorkflowBuild exposes an ``agent`` property defaulting to None."""
        assert hasattr(WorkflowBuild(), "agent")
        assert WorkflowBuild(agent="codex").agent == "codex"

    def test_workflow_build_has_env_property(self) -> None:
        """WorkflowBuild exposes an ``env`` property defaulting to None."""
        assert hasattr(WorkflowBuild(), "env")
        assert WorkflowBuild(env={"A": "1"}).env == {"A": "1"}

    def test_workflow_build_has_review_agent_property(self) -> None:
        """WorkflowBuild exposes a ``review_agent`` property defaulting to None."""
        assert hasattr(WorkflowBuild(), "review_agent")
        assert WorkflowBuild(review_agent="claude").review_agent == "claude"

    def test_workflow_build_has_review_env_property(self) -> None:
        """WorkflowBuild exposes a ``review_env`` property defaulting to None."""
        assert hasattr(WorkflowBuild(), "review_env")
        assert WorkflowBuild(review_env={"C": "3"}).review_env == {"C": "3"}

    def test_workflow_build_has_review_additional_agent_property(self) -> None:
        """WorkflowBuild exposes a ``review_additional_agent`` property defaulting to None."""
        assert hasattr(WorkflowBuild(), "review_additional_agent")
        assert WorkflowBuild(review_additional_agent="gemini").review_additional_agent == "gemini"

    def test_workflow_build_has_review_additional_env_property(self) -> None:
        """WorkflowBuild exposes a ``review_additional_env`` property defaulting to None."""
        assert hasattr(WorkflowBuild(), "review_additional_env")
        assert WorkflowBuild(review_additional_env={"E": "5"}).review_additional_env == {"E": "5"}

    def test_workflow_build_field_order_fixed(self) -> None:
        """Field order is fixed across all six fields.

        agent, env, review_agent, review_env, review_additional_agent,
        review_additional_env — the strict six-field set of the workflow
        build block, matching the layering order of the build path.
        """
        names = [field.name for field in fields(WorkflowBuild)]

        assert names == [
            "agent",
            "env",
            "review_agent",
            "review_env",
            "review_additional_agent",
            "review_additional_env",
        ]

    def test_workflow_build_defaults_all_none(self) -> None:
        """Every field defaults to None when constructed with no arguments."""
        build = WorkflowBuild()

        assert build.agent is None
        assert build.env is None
        assert build.review_agent is None
        assert build.review_env is None
        assert build.review_additional_agent is None
        assert build.review_additional_env is None

    def test_workflow_build_constructible_kw_only(self) -> None:
        """WorkflowBuild is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            WorkflowBuild("codex")  # type: ignore[misc]

    def test_workflow_build_constructible_with_all_six_fields(self) -> None:
        """All six fields are accepted as keyword-only arguments and round-trip verbatim."""
        build = WorkflowBuild(
            agent="codex",
            env={"A": "1"},
            review_agent="claude",
            review_env={"C": "3"},
            review_additional_agent="gemini",
            review_additional_env={"E": "5"},
        )

        assert build.agent == "codex"
        assert build.env == {"A": "1"}
        assert build.review_agent == "claude"
        assert build.review_env == {"C": "3"}
        assert build.review_additional_agent == "gemini"
        assert build.review_additional_env == {"E": "5"}
