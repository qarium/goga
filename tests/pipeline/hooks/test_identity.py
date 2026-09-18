"""Contract and logic tests for the entities declared in
``goga/pipeline/hooks/CODEMANIFEST`` with ``location: identity.py``:

- ``PipelineIdentity(name, display_name, description, source)`` — the identity
  vocabulary of every pipeline event
- ``WorkflowDecision(kind, workflow_name)`` — the outcome of the workflow
  resolution
- ``WorkIdentity(branch, slug, year)`` — the topics-shaped identity of the
  current work

Supported data only — no mocks, no filesystem: the models are pure fact
carriers, every resolution happens in the constructing operation.
"""

from __future__ import annotations

import dataclasses

import pytest
from goga.pipeline.hooks import PipelineIdentity, WorkflowDecision, WorkIdentity

from tests.conftest import is_kw_only_dataclass


def _field_defaults(cls: type) -> list[tuple[str, object]]:
    """(name, default) per declared field — ``MISSING`` for required fields."""
    return [(field.name, field.default) for field in dataclasses.fields(cls)]


# --- Contract tests ---


class TestIdentityContract:
    def test_entities_are_importable_from_the_zone_facade(self) -> None:
        """All three models live on the zone package and its ``__all__`` is exact."""
        import goga.pipeline.hooks as zone

        assert zone.PipelineIdentity is PipelineIdentity
        assert zone.WorkflowDecision is WorkflowDecision
        assert zone.WorkIdentity is WorkIdentity
        assert zone.__all__ == ["PipelineIdentity", "WorkIdentity", "WorkflowDecision"]

    def test_models_are_kw_only_dataclasses(self) -> None:
        """Positional construction raises ``TypeError`` for every model."""
        for cls in (PipelineIdentity, WorkflowDecision, WorkIdentity):
            assert dataclasses.is_dataclass(cls)
            assert is_kw_only_dataclass(cls)

        with pytest.raises(TypeError):
            PipelineIdentity("deploy", "", "d", "project")  # type: ignore[misc]

        with pytest.raises(TypeError):
            WorkflowDecision("explicit", "ci")  # type: ignore[misc]

        with pytest.raises(TypeError):
            WorkIdentity("feature-demo", "feature-demo", "2026")  # type: ignore[misc]

    def test_pipeline_identity_carries_exactly_the_declared_fields(self) -> None:
        """``name, display_name="", description, source`` — names, order, defaults."""
        assert _field_defaults(PipelineIdentity) == [
            ("name", dataclasses.MISSING),
            ("display_name", ""),
            ("description", dataclasses.MISSING),
            ("source", dataclasses.MISSING),
        ]

    def test_workflow_decision_carries_exactly_the_declared_fields(self) -> None:
        """``kind, workflow_name`` — both required, no defaults."""
        assert _field_defaults(WorkflowDecision) == [
            ("kind", dataclasses.MISSING),
            ("workflow_name", dataclasses.MISSING),
        ]

    def test_work_identity_carries_exactly_the_declared_fields(self) -> None:
        """``branch, slug=None, year=None`` — names, order, defaults."""
        assert _field_defaults(WorkIdentity) == [
            ("branch", dataclasses.MISSING),
            ("slug", None),
            ("year", None),
        ]


# --- Logic tests ---


class TestPipelineIdentity:
    def test_source_rejects_anything_but_project_or_user(self) -> None:
        """The ``source`` literal is guarded — exactly project or user."""
        with pytest.raises(ValueError, match="pipeline source must be one of"):
            PipelineIdentity(name="deploy", description="d", source="elsewhere")

        for source in ("project", "user"):
            identity = PipelineIdentity(name="deploy", description="d", source=source)

            assert identity.source == source

    def test_name_rejects_empty_separators_and_yml_suffix(self) -> None:
        """The ``name`` rules: non-empty, no ``/``/``\\``, no ``.yml`` suffix."""
        for bad_name, pattern in (
            ("", "must not be empty"),
            ("dir/x", "path separators"),
            ("dir\\x", "path separators"),
            ("deploy.yml", "'.yml' extension"),
        ):
            with pytest.raises(ValueError, match=pattern):
                PipelineIdentity(name=bad_name, description="d", source="project")

    def test_fields_round_trip_and_display_name_defaults_empty(self) -> None:
        """Authored header facts carry verbatim; ``display_name`` defaults to ``""``."""
        default = PipelineIdentity(name="deploy", description="Ships the service", source="project")

        assert default.display_name == ""

        authored = PipelineIdentity(
            name="deploy",
            display_name="Deploy the service",
            description="Ships the service",
            source="user",
        )

        assert authored.name == "deploy"
        assert authored.display_name == "Deploy the service"
        assert authored.description == "Ships the service"
        assert authored.source == "user"


class TestWorkflowDecision:
    def test_kind_rejects_unknown_literals(self) -> None:
        """The ``kind`` literal is guarded — exactly the four fixed values."""
        with pytest.raises(ValueError, match="workflow decision kind must be one of"):
            WorkflowDecision(kind="bogus", workflow_name=None)

    def test_all_four_kinds_construct(self) -> None:
        """disabled, explicit, auto-match, and silent-miss all construct."""
        decisions = [
            WorkflowDecision(kind="disabled", workflow_name=None),
            WorkflowDecision(kind="explicit", workflow_name="ci"),
            WorkflowDecision(kind="auto-match", workflow_name="deploy"),
            WorkflowDecision(kind="silent-miss", workflow_name=None),
        ]

        assert [decision.kind for decision in decisions] == [
            "disabled",
            "explicit",
            "auto-match",
            "silent-miss",
        ]
        assert decisions[0].workflow_name is None
        assert decisions[1].workflow_name == "ci"
        assert decisions[2].workflow_name == "deploy"
        assert decisions[3].workflow_name is None


class TestWorkIdentity:
    def test_branch_only_form_leaves_slug_and_year_none(self) -> None:
        """``WorkIdentity(branch="b")`` alone serves a branch hosting no topic."""
        work = WorkIdentity(branch="b")

        assert work.branch == "b"
        assert work.slug is None
        assert work.year is None

    def test_hosting_form_carries_slug_and_year(self) -> None:
        """The topic-hosting form carries the normalized slug and the year."""
        work = WorkIdentity(branch="feature-demo", slug="feature-demo", year="2026")

        assert work.branch == "feature-demo"
        assert work.slug == "feature-demo"
        assert work.year == "2026"
