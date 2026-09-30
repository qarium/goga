"""Shared fixtures and fact builders of the build hooks zone tests.

Re-exports the two boundary fixtures of the hooks platform tests
(``pin_package_environment`` / ``install_tool_package``) so the zone suites
pin the same two outside-world points — the ``packages_distributions`` read
and the ``sys.modules`` entry of a ``goga_tool_*`` package — with the
platform code under test running for real. The fact builders are the one
copy of the uniform checkpoint facts the zone's three suites share — a
tasks-part and a review-part ``StageFacts`` and the branch-only
``BuildMoment`` envelope.
"""

from __future__ import annotations

from goga.build.hooks import AdditionalFacts, BuildMoment, StageFacts, WorkIdentity

from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401


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
