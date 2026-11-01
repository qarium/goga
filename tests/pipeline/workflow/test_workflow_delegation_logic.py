"""Logic tests for the ``WorkflowDelegation`` dataclass.

Covers construction behavior beyond the contract surface: the materialized
defaults (``max_tasks`` 50 — a value, not an omission), the verbatim
round-trip of an authored block, and the authored-zero boundary — ``depth: 0``
is a VALUE, never an absence, so the consumers can deliver a depth bound of
zero without a falsy trap.
"""

from __future__ import annotations

from goga.pipeline.workflow import WorkflowDelegation


class TestWorkflowDelegationLogic:
    """Logic tests — construction behavior of the ``WorkflowDelegation`` dataclass."""

    def test_workflow_delegation_defaults_are_materialized(self) -> None:
        """Constructing with no arguments yields the absence/default pair (None, 50).

        An empty delegation block parses to exactly this value — ``depth``
        absent (no bound delivered) and ``max_tasks`` materialized to 50 (the
        engine default of 20 is never relied upon).
        """
        delegation = WorkflowDelegation()

        assert delegation.depth is None
        assert delegation.max_tasks == 50

    def test_workflow_delegation_stores_authored_values_verbatim(self) -> None:
        """Every field round-trips an authored block verbatim (no composition, no rewrite)."""
        delegation = WorkflowDelegation(depth=3, max_tasks=7)

        assert delegation.depth == 3
        assert delegation.max_tasks == 7

    def test_workflow_delegation_authored_depth_zero_is_a_value(self) -> None:
        """An authored ``depth: 0`` survives as the integer zero, not as absence.

        The falsy-zero boundary: any consumer distinguishing "no bound"
        (``None``) from "zero depth" (``0``) must key on ``is None``, never on
        truthiness — this pin keeps the authored zero distinguishable.
        """
        delegation = WorkflowDelegation(depth=0)

        assert delegation.depth == 0
        assert delegation.depth is not None

    def test_equality_of_identical_constructions(self) -> None:
        """Two blocks with identical fields compare equal.

        The empty-block default equals an explicitly authored
        ``delegation: {}`` — the parser's materialized block and the
        consumer's default construction must compare equal.
        """
        assert WorkflowDelegation() == WorkflowDelegation(depth=None, max_tasks=50)
