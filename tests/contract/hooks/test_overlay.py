"""Contract and logic tests for the entities declared in
``goga/contract/hooks/CODEMANIFEST`` with ``location: overlay.py``:

- ``ToolContribution(tool, facts)`` — the committed contribution of one
  tool for one cell (pure data)
- ``merge_type_contributions(contributions)`` — the deterministic, pure
  composition of the committed contributions into the tools area of
  each addressed type node

Supported data only — no mocks, no filesystem: structural validation is
not here, it happened at the tool commit point of the delivery. The
tests import from ``goga.contract.hooks.overlay`` directly — the facade
identity assertions belong to the facade suite.
"""

from __future__ import annotations

import dataclasses
import inspect
import typing

import pytest

from tests.conftest import is_kw_only_dataclass

# --- Contract tests ---


class TestOverlayContract:
    def test_both_names_are_importable_from_the_module(self) -> None:
        """Both names live in ``overlay.py`` of the zone."""
        from goga.contract.hooks.overlay import ToolContribution, merge_type_contributions

        assert callable(ToolContribution)
        assert callable(merge_type_contributions)

    def test_tool_contribution_is_a_frozen_kw_only_dataclass(self) -> None:
        """Pure frozen data, keyword-only construction."""
        from goga.contract.hooks.overlay import ToolContribution

        assert dataclasses.is_dataclass(ToolContribution)
        assert is_kw_only_dataclass(ToolContribution)
        assert ToolContribution.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            ToolContribution("docs", {"A": {"x": 1}})  # type: ignore[misc]

    def test_tool_contribution_carries_exactly_the_declared_fields(self) -> None:
        """``tool, facts`` — names, order, all required."""
        from goga.contract.hooks.overlay import ToolContribution

        assert [field.name for field in dataclasses.fields(ToolContribution)] == ["tool", "facts"]

        defaults = [(field.name, field.default) for field in dataclasses.fields(ToolContribution)]

        assert defaults == [
            ("tool", dataclasses.MISSING),
            ("facts", dataclasses.MISSING),
        ]

    def test_tool_contribution_annotates_the_declared_property_types(self) -> None:
        """The fields carry the contract property types."""
        from goga.contract.hooks.overlay import ToolContribution

        hints = typing.get_type_hints(ToolContribution)

        assert hints["tool"] is str
        assert hints["facts"] == dict[str, dict[str, object]]

    def test_merge_is_a_module_level_function_with_the_declared_signature(self) -> None:
        """``merge_type_contributions(contributions) -> dict`` — one typed parameter."""
        from goga.contract.hooks.overlay import ToolContribution, merge_type_contributions

        assert inspect.isfunction(merge_type_contributions)
        assert merge_type_contributions.__module__ == "goga.contract.hooks.overlay"

        parameters = inspect.signature(merge_type_contributions).parameters

        assert list(parameters) == ["contributions"]

        hints = typing.get_type_hints(merge_type_contributions)

        assert hints["contributions"] == list[ToolContribution]
        assert hints["return"] == dict[str, dict[str, dict[str, object]]]


# --- Logic tests: the composition ---


class TestMergeComposition:
    def test_merge_type_contributions_skips_empty_and_orders_by_enumeration(self) -> None:
        """Empty areas skip; the rest place per type in enumeration order."""
        from goga.contract.hooks.overlay import ToolContribution, merge_type_contributions

        contributions = [
            ToolContribution(tool="docs", facts={"A": {"x": 1}, "B": {"y": 2}}),
            ToolContribution(tool="lint", facts={"A": {}}),
            ToolContribution(tool="lint", facts={"C": {"z": 3}}),
        ]
        snapshot = [
            (contribution.tool, {type_name: dict(facts) for type_name, facts in contribution.facts.items()})
            for contribution in contributions
        ]

        result = merge_type_contributions(contributions)

        assert result == {"A": {"docs": {"x": 1}}, "B": {"docs": {"y": 2}}, "C": {"lint": {"z": 3}}}
        assert list(result) == ["A", "B", "C"]
        assert list(result["A"]) == ["docs"]
        assert [
            (contribution.tool, {type_name: dict(facts) for type_name, facts in contribution.facts.items()})
            for contribution in contributions
        ] == snapshot

    def test_merge_of_no_contributions_is_the_empty_mapping(self) -> None:
        """Nothing committed — the empty tools area."""
        from goga.contract.hooks.overlay import merge_type_contributions

        assert merge_type_contributions([]) == {}

    def test_two_tools_addressing_the_same_type_both_appear(self) -> None:
        """Both tools place their facts inside the shared type's area."""
        from goga.contract.hooks.overlay import ToolContribution, merge_type_contributions

        contributions = [
            ToolContribution(tool="docs", facts={"ProjectConfig": {"coverage": 3}}),
            ToolContribution(tool="lint", facts={"ProjectConfig": {"rules": 7}}),
        ]

        result = merge_type_contributions(contributions)

        assert result == {"ProjectConfig": {"docs": {"coverage": 3}, "lint": {"rules": 7}}}
        assert list(result["ProjectConfig"]) == ["docs", "lint"]
