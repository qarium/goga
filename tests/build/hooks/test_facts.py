"""Contract and logic tests for the entities declared in
``goga/build/hooks/CODEMANIFEST`` with ``location: facts.py``:

- ``WorkIdentity(branch, slug, year)`` — the identity of the current work
- ``BuildMoment(plan, work, dry_run)`` — the uniform envelope of every
  build context
- ``StageFacts(stage, agent, env, ...)`` — the resolved facts of one stage
  part of the run
- ``AdditionalFacts(agent, patience, max_iterations)`` — the delivered
  mirror of the external-review block
- ``RelocationOutcome(moved, destination)`` — the outcome of the plan
  relocation attempt
- ``Violation(tool, hook, reason)`` — one collected veto of the gate walk
- ``GateVerdict(violations)`` — the collected verdict of the gate walk

Supported data only — no mocks, no filesystem: the models are pure fact
carriers, every resolution happens in the constructing operation and env
values never appear (names only).
"""

from __future__ import annotations

import dataclasses

import pytest
from goga.build.hooks import (
    AdditionalFacts,
    BuildMoment,
    GateVerdict,
    RelocationOutcome,
    StageFacts,
    Violation,
    WorkIdentity,
)

from tests.conftest import is_kw_only_dataclass

FACT_TYPES: tuple[type, ...] = (
    WorkIdentity,
    BuildMoment,
    StageFacts,
    AdditionalFacts,
    RelocationOutcome,
    Violation,
    GateVerdict,
)


def _field_defaults(cls: type) -> list[tuple[str, object]]:
    """(name, default) per declared field — ``MISSING`` for required fields."""
    return [(field.name, field.default) for field in dataclasses.fields(cls)]


def _tasks_facts(**overrides: object) -> StageFacts:
    """A tasks-part ``StageFacts`` — the review-only members None."""
    values: dict[str, object] = {
        "stage": "tasks",
        "agent": "claude",
        "env": ["A", "B"],
        "max_iterations": 9,
        "session_timeout": "30m",
        "idle_timeout": "5m",
        "wait": "1m",
        "roles": None,
        "base_ref": None,
        "strategy": None,
        "finalize": None,
        "additional": None,
    }
    values.update(overrides)

    return StageFacts(**values)  # type: ignore[arg-type]


# --- Contract tests ---


class TestFactsContract:
    def test_entities_are_importable_from_the_zone_facade(self) -> None:
        """All seven fact types live on the zone package and its ``__all__``."""
        import goga.build.hooks as zone

        for cls in FACT_TYPES:
            assert getattr(zone, cls.__name__) is cls

        for name in (cls.__name__ for cls in FACT_TYPES):
            assert name in zone.__all__

    def test_fact_types_are_kw_only_and_non_frozen(self) -> None:
        """kw_only dataclasses; the delivery proxy, not frozen-ness, closes mutability."""
        for cls in FACT_TYPES:
            assert dataclasses.is_dataclass(cls)
            assert is_kw_only_dataclass(cls)
            assert not cls.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            WorkIdentity("feature-x", "feature-x", "2026")  # type: ignore[misc]

        with pytest.raises(TypeError):
            GateVerdict([])  # type: ignore[misc]

    def test_gate_verdict_approved_is_a_property(self) -> None:
        """``approved`` is a computed property, not a stored field."""
        assert isinstance(GateVerdict.approved, property)
        assert "approved" not in [field.name for field in dataclasses.fields(GateVerdict)]

    def test_work_identity_carries_exactly_the_declared_fields(self) -> None:
        """``branch, slug=None, year=None`` — names, order, defaults."""
        assert _field_defaults(WorkIdentity) == [
            ("branch", dataclasses.MISSING),
            ("slug", None),
            ("year", None),
        ]

    def test_build_moment_carries_exactly_the_declared_fields(self) -> None:
        """``plan, work, dry_run`` — all required, no defaults."""
        assert _field_defaults(BuildMoment) == [
            ("plan", dataclasses.MISSING),
            ("work", dataclasses.MISSING),
            ("dry_run", dataclasses.MISSING),
        ]

    def test_stage_facts_carries_exactly_the_declared_fields(self) -> None:
        """Twelve fields in the declared order — all required, no defaults."""
        assert _field_defaults(StageFacts) == [
            ("stage", dataclasses.MISSING),
            ("agent", dataclasses.MISSING),
            ("env", dataclasses.MISSING),
            ("max_iterations", dataclasses.MISSING),
            ("session_timeout", dataclasses.MISSING),
            ("idle_timeout", dataclasses.MISSING),
            ("wait", dataclasses.MISSING),
            ("roles", dataclasses.MISSING),
            ("base_ref", dataclasses.MISSING),
            ("strategy", dataclasses.MISSING),
            ("finalize", dataclasses.MISSING),
            ("additional", dataclasses.MISSING),
        ]

    def test_remaining_facts_carry_exactly_the_declared_fields(self) -> None:
        """``AdditionalFacts``, ``RelocationOutcome``, ``Violation``, ``GateVerdict``."""
        assert _field_defaults(AdditionalFacts) == [
            ("agent", dataclasses.MISSING),
            ("patience", dataclasses.MISSING),
            ("max_iterations", dataclasses.MISSING),
        ]
        assert _field_defaults(RelocationOutcome) == [
            ("moved", dataclasses.MISSING),
            ("destination", dataclasses.MISSING),
        ]
        assert _field_defaults(Violation) == [
            ("tool", dataclasses.MISSING),
            ("hook", dataclasses.MISSING),
            ("reason", dataclasses.MISSING),
        ]
        assert _field_defaults(GateVerdict) == [
            ("violations", dataclasses.MISSING),
        ]


# --- Logic tests ---


class TestGateVerdict:
    def test_empty_verdict_is_approved(self) -> None:
        """No violations — the run may proceed."""
        verdict = GateVerdict(violations=[])

        assert verdict.approved is True
        assert verdict.violations == []

    def test_violated_verdict_is_not_approved(self) -> None:
        """Any collected violation blocks the run."""
        verdict = GateVerdict(violations=[Violation(tool="t", hook="h", reason="r")])

        assert verdict.approved is False
        assert verdict.violations == [Violation(tool="t", hook="h", reason="r")]


class TestWorkIdentity:
    def test_branch_only_form_leaves_slug_and_year_none(self) -> None:
        """``WorkIdentity(branch=...)`` alone serves a branch hosting no topic."""
        work = WorkIdentity(branch="feature-x")

        assert work.branch == "feature-x"
        assert work.slug is None
        assert work.year is None

    def test_hosting_form_carries_slug_and_year(self) -> None:
        """The topic-hosting form carries the normalized slug and the year."""
        work = WorkIdentity(branch="feature-x", slug="feature-x", year="2026")

        assert work.branch == "feature-x"
        assert work.slug == "feature-x"
        assert work.year == "2026"


class TestBuildMoment:
    def test_carries_the_envelope_values_verbatim(self) -> None:
        """The plan path, the work identity, and the rehearsal fact."""
        work = WorkIdentity(branch="add-hooks-to-build")
        moment = BuildMoment(plan="docs/plans/plan.md", work=work, dry_run=True)

        assert moment.plan == "docs/plans/plan.md"
        assert moment.work is work
        assert moment.dry_run is True


class TestStageFacts:
    def test_tasks_part_accepts_none_review_members(self) -> None:
        """The review-only members are None on the tasks part."""
        facts = _tasks_facts()

        assert facts.stage == "tasks"
        assert facts.agent == "claude"
        assert facts.env == ["A", "B"]
        assert facts.roles is None
        assert facts.base_ref is None
        assert facts.strategy is None
        assert facts.finalize is None
        assert facts.additional is None

    def test_review_part_carries_the_full_fact_set(self) -> None:
        """The review part carries the review-only members and the additional mirror."""
        additional = AdditionalFacts(agent="codex", patience=2, max_iterations=4)
        facts = _tasks_facts(
            stage="review",
            agent="codex",
            env=[],
            roles=["quality", "testing"],
            base_ref="main",
            strategy="short",
            finalize="Final pass: merge the review.",
            additional=additional,
        )

        assert facts.stage == "review"
        assert facts.env == []
        assert facts.roles == ["quality", "testing"]
        assert facts.base_ref == "main"
        assert facts.strategy == "short"
        assert facts.finalize == "Final pass: merge the review."
        assert facts.additional is additional

    def test_env_carries_names_only(self) -> None:
        """``env`` is the presence list of names — values never appear."""
        facts = _tasks_facts(env=["API_KEY", "HTTP_PROXY"])

        assert facts.env == ["API_KEY", "HTTP_PROXY"]


class TestAdditionalFacts:
    def test_stores_zero_verbatim(self) -> None:
        """0 is a meaningful value, not an unset marker — it stays 0."""
        facts = AdditionalFacts(agent="codex", patience=0, max_iterations=0)

        assert facts.agent == "codex"
        assert facts.patience == 0
        assert facts.max_iterations == 0

    def test_unset_members_are_none(self) -> None:
        """The absent form carries None for every member."""
        facts = AdditionalFacts(agent=None, patience=None, max_iterations=None)

        assert facts.agent is None
        assert facts.patience is None
        assert facts.max_iterations is None


class TestOutcomeAndViolation:
    def test_relocation_outcome_carries_both_forms(self) -> None:
        """The moved form carries the destination; the not-moved form None."""
        moved = RelocationOutcome(moved=True, destination="docs/plans/completed/plan.md")
        stayed = RelocationOutcome(moved=False, destination=None)

        assert moved.moved is True
        assert moved.destination == "docs/plans/completed/plan.md"
        assert stayed.moved is False
        assert stayed.destination is None

    def test_violation_carries_the_triple_verbatim(self) -> None:
        """Tool, hook, reason — the reason is a message, never a traceback."""
        violation = Violation(tool="goga_tool_a", hook="policy", reason="no deploys on friday")

        assert violation.tool == "goga_tool_a"
        assert violation.hook == "policy"
        assert violation.reason == "no deploys on friday"
