"""Contract and logic tests for the entities declared in
``goga/build/hooks/CODEMANIFEST`` with ``location: contexts.py``:

- ``BuildValidation(moment, tasks, review, skip)`` — the gate's per-tool
  view with the veto buffer
- ``BuildStarted(moment, tasks, review, skip)`` — the read-only context
  of the start notification
- ``PassStarted(moment, facts)`` — the read-only context of the
  pass-start notification
- ``PassCompleted(moment, facts, exit_code)`` — the read-only context of
  the pass-completion notification (completion is a fact, not a success
  claim)
- ``BuildCompleted(moment, exit_code, stages, relocation, statuses)`` —
  the read-only context of the completion notification

Supported data only — no mocks, no filesystem: the contexts are read-only
views over caller-resolved facts; the veto buffer of ``BuildValidation``
is the single write channel and belongs to one tool alone.
"""

from __future__ import annotations

import dataclasses

import pytest
from goga.build.hooks import (
    AdditionalFacts,
    BuildCompleted,
    BuildMoment,
    BuildStarted,
    BuildValidation,
    PassCompleted,
    PassStarted,
    RelocationOutcome,
    StageFacts,
    WorkIdentity,
)

from tests.conftest import is_kw_only_dataclass

CONTEXT_TYPES: tuple[type, ...] = (
    BuildValidation,
    BuildStarted,
    PassStarted,
    PassCompleted,
    BuildCompleted,
)


def _field_names(cls: type) -> list[str]:
    """The declared field names — the private init=False buffer included."""
    return [field.name for field in dataclasses.fields(cls)]


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


def _review_facts(**overrides: object) -> StageFacts:
    """A review-part ``StageFacts`` — the review-only members populated."""
    values: dict[str, object] = {
        "stage": "review",
        "agent": "codex",
        "env": [],
        "max_iterations": None,
        "session_timeout": "30m",
        "idle_timeout": "5m",
        "wait": "1m",
        "roles": ["quality"],
        "base_ref": "main",
        "strategy": "medium",
        "finalize": None,
        "additional": AdditionalFacts(agent="codex", patience=None, max_iterations=None),
    }
    values.update(overrides)

    return StageFacts(**values)  # type: ignore[arg-type]


def _moment() -> BuildMoment:
    """The uniform envelope — a branch-only work identity."""
    return BuildMoment(
        plan="docs/plans/plan.md",
        work=WorkIdentity(branch="add-hooks-to-build"),
        dry_run=False,
    )


# --- Contract tests ---


class TestContextsContract:
    def test_entities_are_importable_from_the_zone_facade(self) -> None:
        """All five context types live on the zone package and its ``__all__``."""
        import goga.build.hooks as zone

        for cls in CONTEXT_TYPES:
            assert getattr(zone, cls.__name__) is cls

        for name in (cls.__name__ for cls in CONTEXT_TYPES):
            assert name in zone.__all__

    def test_context_types_are_kw_only_and_non_frozen(self) -> None:
        """kw_only dataclasses; the delivery proxy, not frozen-ness, closes mutability."""
        for cls in CONTEXT_TYPES:
            assert dataclasses.is_dataclass(cls)
            assert is_kw_only_dataclass(cls)
            assert not cls.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            BuildValidation(_moment(), _tasks_facts(), _review_facts(), False)  # type: ignore[misc]

    def test_build_validation_veto_is_callable(self) -> None:
        """``veto`` is a method of ``BuildValidation`` — the single write channel."""
        assert callable(BuildValidation.veto)

        view = BuildValidation(
            moment=_moment(), tasks=_tasks_facts(), review=_review_facts(), skip=False
        )
        view.veto("blocked")

    def test_build_validation_carries_exactly_the_declared_fields(self) -> None:
        """``moment, tasks, review, skip`` plus the private init=False buffer."""
        assert _field_names(BuildValidation) == ["moment", "tasks", "review", "skip", "_veto"]

        buffer_field = dataclasses.fields(BuildValidation)[-1]
        assert buffer_field.init is False
        assert buffer_field.default is None

    def test_remaining_contexts_carry_exactly_the_declared_fields(self) -> None:
        """``BuildStarted``, ``PassStarted``, ``PassCompleted``, ``BuildCompleted``."""
        assert _field_names(BuildStarted) == ["moment", "tasks", "review", "skip"]
        assert _field_names(PassStarted) == ["moment", "facts"]
        assert _field_names(PassCompleted) == ["moment", "facts", "exit_code"]
        assert _field_names(BuildCompleted) == [
            "moment",
            "exit_code",
            "stages",
            "relocation",
            "statuses",
        ]


# --- Logic tests ---


class TestBuildValidation:
    def test_veto_replaces_the_buffer_whole(self) -> None:
        """``veto("one")`` then ``veto("two")`` — the buffer holds exactly ``"two"``."""
        view = BuildValidation(
            moment=_moment(), tasks=_tasks_facts(), review=_review_facts(), skip=False
        )

        assert view._veto is None

        view.veto("one")
        assert view._veto == "one"

        view.veto("two")
        assert view._veto == "two"

    def test_veto_stores_whitespace_reason_verbatim(self) -> None:
        """An empty or whitespace-only reason is stored as given."""
        view = BuildValidation(
            moment=_moment(), tasks=_tasks_facts(), review=_review_facts(), skip=False
        )

        view.veto("   ")

        assert view._veto == "   "

    def test_read_only_fields_carry_the_constructed_values(self) -> None:
        """``moment``, ``tasks``, ``review``, ``skip`` — the observed facts, unchanged."""
        moment = _moment()
        tasks = _tasks_facts()
        review = _review_facts()
        view = BuildValidation(moment=moment, tasks=tasks, review=review, skip=True)

        assert view.moment is moment
        assert view.tasks is tasks
        assert view.review is review
        assert view.skip is True

    def test_veto_changes_no_delivered_fact(self) -> None:
        """The write channel touches the buffer alone — the facts stay as constructed."""
        view = BuildValidation(
            moment=_moment(), tasks=_tasks_facts(), review=_review_facts(), skip=False
        )

        view.veto("policy")

        assert view.tasks.agent == "claude"
        assert view.review.strategy == "medium"
        assert view.skip is False


class TestNotificationContexts:
    def test_build_started_carries_the_constructed_values(self) -> None:
        """The same resolved facts the gate saw, immediately before the first pass."""
        moment = _moment()
        tasks = _tasks_facts()
        review = _review_facts()
        context = BuildStarted(moment=moment, tasks=tasks, review=review, skip=True)

        assert context.moment is moment
        assert context.tasks is tasks
        assert context.review is review
        assert context.skip is True

    def test_pass_started_carries_the_constructed_values(self) -> None:
        """The facts of the pass about to launch."""
        moment = _moment()
        facts = _tasks_facts()
        context = PassStarted(moment=moment, facts=facts)

        assert context.moment is moment
        assert context.facts is facts

    def test_pass_completed_carries_the_actual_exit_code(self) -> None:
        """Completion is a fact — the code travels verbatim, zero and non-zero alike."""
        for code in (0, 2, 126):
            moment = _moment()
            facts = _review_facts()
            context = PassCompleted(moment=moment, facts=facts, exit_code=code)

            assert context.moment is moment
            assert context.facts is facts
            assert context.exit_code == code

    def test_build_completed_carries_the_constructed_values(self) -> None:
        """The outcome facts of the started run — the status integration builds from them."""
        moment = _moment()
        relocation = RelocationOutcome(moved=True, destination="docs/plans/completed/plan.md")
        context = BuildCompleted(
            moment=moment,
            exit_code=0,
            stages=["tasks", "review"],
            relocation=relocation,
            statuses=["backlog", "designed"],
        )

        assert context.moment is moment
        assert context.exit_code == 0
        assert context.stages == ["tasks", "review"]
        assert context.relocation is relocation
        assert context.statuses == ["backlog", "designed"]

    def test_build_completed_accepts_the_empty_completion_forms(self) -> None:
        """A skipped review leaves ``stages`` without it; branch-only delivers ``[]``."""
        context = BuildCompleted(
            moment=_moment(),
            exit_code=1,
            stages=["tasks"],
            relocation=RelocationOutcome(moved=False, destination=None),
            statuses=[],
        )

        assert context.stages == ["tasks"]
        assert context.relocation.moved is False
        assert context.relocation.destination is None
        assert context.statuses == []
