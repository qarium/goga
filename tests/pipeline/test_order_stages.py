"""Contract and logic tests for the ``order_stages`` Routine.

The pipeline cell's CODEMANIFEST declares ``order_stages`` as the deterministic
topological ordering of compiled flow stages — the execution order the pipeline
card reports. Dependencies come from ``FlowStage.depends_on`` (tristate:
``None`` means no references, i.e. always ready); a reference to an id that is
not declared counts as satisfied (dangling → satisfied); declaration order is
both the tie-break among ready stages and the fallback order when a dependency
cycle blocks all progress.

The Routine is pure: the input list and its stages are never mutated, the
result contains the SAME objects (identity), each exactly once, and
``depends_on`` is never rewritten.

Contract tests pin the import surface and the signature. Logic tests cover
each algorithm branch.
"""

from __future__ import annotations

import inspect
from typing import get_type_hints

from goga.pipeline.compiler import FlowStage
from goga.pipeline.order_stages import order_stages


def _stage(stage_id: str, depends_on: list[str] | None = None) -> FlowStage:
    """Build a minimal FlowStage — only id/name/depends_on matter to ordering."""
    return FlowStage(id=stage_id, name=stage_id.title(), depends_on=depends_on, fields={})


def _snapshot(stages: list[FlowStage]) -> list[tuple[str, str, list[str] | None, dict]]:
    """Capture the comparable state of a stage list (id, name, depends_on, fields)."""
    return [(s.id, s.name, list(s.depends_on) if s.depends_on is not None else None, dict(s.fields)) for s in stages]


class TestOrderStagesContract:
    def test_order_stages_is_importable_from_module(self) -> None:
        """The routine lives at its declared location ``goga.pipeline.order_stages``."""
        import goga.pipeline.order_stages as module

        assert module.order_stages is order_stages

    def test_order_stages_signature(self) -> None:
        """Signature: (stages: list[FlowStage]) -> list[FlowStage]."""
        signature = inspect.signature(order_stages)
        # The module uses ``from __future__ import annotations``, so raw
        # annotations are strings — resolve them through get_type_hints.
        hints = get_type_hints(order_stages)

        assert list(signature.parameters) == ["stages"]
        assert hints["stages"] == list[FlowStage]
        assert hints["return"] == list[FlowStage]


class TestOrderStagesLogic:
    def test_order_stages_topologically_reorders(self) -> None:
        """A stage declared before its dependency is emitted after it."""
        stages = [_stage("review", ["build"]), _stage("build", None)]

        result = order_stages(stages)

        assert [s.id for s in result] == ["build", "review"]
        # The input list itself keeps its declaration order.
        assert [s.id for s in stages] == ["review", "build"]

    def test_order_stages_tie_breaks_by_declaration_order(self) -> None:
        """Independent stages stay in declaration order."""
        stages = [_stage("a"), _stage("b"), _stage("c")]

        result = order_stages(stages)

        assert [s.id for s in result] == ["a", "b", "c"]

    def test_order_stages_empty_input_returns_empty(self) -> None:
        """An empty input yields an empty output."""
        assert order_stages([]) == []

    def test_order_stages_cycle_appends_remaining_in_declaration_order(self) -> None:
        """When a cycle blocks progress, remaining stages append in declaration order."""
        stages = [_stage("a", ["b"]), _stage("b", ["a"]), _stage("c", None)]

        result = order_stages(stages)

        assert [s.id for s in result] == ["c", "a", "b"]
        # Completeness — the result's id set equals the input's.
        assert {s.id for s in result} == {"a", "b", "c"}

    def test_order_stages_dangling_reference_is_satisfied(self) -> None:
        """A depends_on id that is not declared counts as satisfied."""
        stages = [_stage("a", ["ghost"]), _stage("b", None)]

        result = order_stages(stages)

        assert [s.id for s in result] == ["a", "b"]

    def test_order_stages_is_pure(self) -> None:
        """The input list and its stages are untouched; the result holds the same objects."""
        stages = [
            _stage("second", ["first"]),
            _stage("first", None),
            _stage("third", ["second"]),
        ]
        original = list(stages)
        before = _snapshot(stages)

        result = order_stages(stages)

        # The input list and every stage on it are unchanged.
        assert stages == original
        assert [s.id for s in stages] == ["second", "first", "third"]
        assert _snapshot(stages) == before
        # Identity — the result carries the very same objects, each exactly once.
        assert {id(s) for s in result} == {id(s) for s in stages}
        assert len({id(s) for s in result}) == len(result)
        # depends_on is not rewritten.
        assert _snapshot(result) == [
            ("first", "First", None, {}),
            ("second", "Second", ["first"], {}),
            ("third", "Third", ["second"], {}),
        ]
