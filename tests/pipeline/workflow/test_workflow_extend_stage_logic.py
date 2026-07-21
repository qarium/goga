"""Logic tests for the ``WorkflowExtendStage`` dataclass.

Covers construction behavior beyond the contract surface: partial
construction (one of ``before``/``after`` set, the other ``None``), verbatim
storage of nested ``body`` values, and round-trip equality of identical
constructions. The data Entity carries no behavior — these tests pin its
construction semantics.
"""

from __future__ import annotations

from goga.pipeline.workflow import WorkflowExtendStage


class TestWorkflowExtendStageLogic:
    """Logic tests — construction behavior of the ``WorkflowExtendStage`` dataclass."""

    def test_partial_construction_after_only(self) -> None:
        """Specifying only ``after`` leaves ``before`` at None."""
        ext = WorkflowExtendStage(after=["x"], body={})

        assert ext.before is None
        assert ext.after == ["x"]
        assert ext.body == {}

    def test_partial_construction_before_only(self) -> None:
        """Specifying only ``before`` leaves ``after`` at None."""
        ext = WorkflowExtendStage(before=["x"], body={})

        assert ext.before == ["x"]
        assert ext.after is None

    def test_body_stores_nested_values_verbatim(self) -> None:
        """A nested ``body`` is stored verbatim — deep structure round-trips unchanged."""
        ext = WorkflowExtendStage(body={"custom": {"deep": 1}, "list": [1, 2, 3]})

        assert ext.body == {"custom": {"deep": 1}, "list": [1, 2, 3]}

    def test_body_keeps_supplied_identity(self) -> None:
        """The supplied ``body`` dict is kept (the dataclass is not frozen)."""
        payload = {"title": "T", "prompt": "go"}
        ext = WorkflowExtendStage(body=payload)

        assert ext.body is payload

    def test_provided_values_round_trip_unchanged(self) -> None:
        """Provided values round-trip verbatim."""
        ext = WorkflowExtendStage(before=["a"], after=["b"], body={"title": "T"})

        assert ext.before == ["a"]
        assert ext.after == ["b"]
        assert ext.body == {"title": "T"}

    def test_equality_of_identical_constructions(self) -> None:
        """Two extend-stages with identical fields compare equal."""
        first = WorkflowExtendStage(before=["a"], after=["b"], body={"title": "T"})
        second = WorkflowExtendStage(before=["a"], after=["b"], body={"title": "T"})

        assert first == second
