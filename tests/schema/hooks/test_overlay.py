"""Contract and logic tests for the entities declared in
``goga/schema/hooks/CODEMANIFEST`` with ``location: overlay.py``:

- ``ToolContribution(tool, facts)`` — the committed contribution of one
  tool for one cell (pure data)
- ``merge_cell_contributions(contributions)`` — the deterministic, pure
  composition of the committed contributions into the tools area of one
  cell node

Supported data only — no mocks, no filesystem: structural validation is
not here, it happened at the tool commit point of the delivery.
"""

from __future__ import annotations

import dataclasses
import inspect
import typing

import pytest

from tests.conftest import is_kw_only_dataclass

# --- Contract tests ---


class TestOverlayContract:
    def test_both_names_are_importable_from_the_facade(self) -> None:
        """Both names live on the zone facade and resolve to ``overlay.py``."""
        import goga.schema.hooks as facade
        from goga.schema.hooks.overlay import ToolContribution, merge_cell_contributions

        assert facade.ToolContribution is ToolContribution
        assert facade.merge_cell_contributions is merge_cell_contributions

        assert "ToolContribution" in facade.__all__
        assert "merge_cell_contributions" in facade.__all__
        assert facade.__all__ == sorted(facade.__all__)

    def test_tool_contribution_is_a_frozen_kw_only_dataclass(self) -> None:
        """Pure frozen data, keyword-only construction."""
        from goga.schema.hooks import ToolContribution

        assert dataclasses.is_dataclass(ToolContribution)
        assert is_kw_only_dataclass(ToolContribution)
        assert ToolContribution.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            ToolContribution("alpha", {"x": 1})  # type: ignore[misc]

    def test_tool_contribution_carries_exactly_the_declared_fields(self) -> None:
        """``tool, facts`` — names, order, all required."""
        from goga.schema.hooks import ToolContribution

        assert [field.name for field in dataclasses.fields(ToolContribution)] == ["tool", "facts"]

        defaults = [(field.name, field.default) for field in dataclasses.fields(ToolContribution)]

        assert defaults == [
            ("tool", dataclasses.MISSING),
            ("facts", dataclasses.MISSING),
        ]

    def test_tool_contribution_annotates_the_declared_property_types(self) -> None:
        """The fields carry the contract property types."""
        from goga.schema.hooks import ToolContribution

        hints = typing.get_type_hints(ToolContribution)

        assert hints["tool"] is str
        assert hints["facts"] == dict[str, object]

    def test_merge_is_a_module_level_function_with_the_declared_signature(self) -> None:
        """``merge_cell_contributions(contributions) -> dict`` — one typed parameter."""
        from goga.schema.hooks import merge_cell_contributions
        from goga.schema.hooks.overlay import ToolContribution

        assert callable(merge_cell_contributions)
        assert inspect.isfunction(merge_cell_contributions)
        assert merge_cell_contributions.__module__ == "goga.schema.hooks.overlay"

        parameters = inspect.signature(merge_cell_contributions).parameters

        assert list(parameters) == ["contributions"]

        hints = typing.get_type_hints(merge_cell_contributions)

        assert hints["contributions"] == list[ToolContribution]
        assert hints["return"] == dict[str, dict[str, object]]


# --- Logic tests: the committed record ---


class TestContributionRecord:
    def test_fields_hold_the_passed_values_verbatim(self) -> None:
        """Pure data — every field round-trips the exact value passed."""
        from goga.schema.hooks import ToolContribution

        facts = {"coverage": 3}
        contribution = ToolContribution(tool="docs", facts=facts)

        assert contribution.tool == "docs"
        assert contribution.facts is facts

    def test_frozen_record_blocks_attribute_assignment(self) -> None:
        """``FrozenInstanceError`` — surfacing as ``AttributeError``."""
        from goga.schema.hooks import ToolContribution

        contribution = ToolContribution(tool="docs", facts={"coverage": 3})

        with pytest.raises(dataclasses.FrozenInstanceError) as raise_info:
            contribution.tool = "beta"  # type: ignore[misc]

        assert isinstance(raise_info.value, AttributeError)


# --- Logic tests: the composition ---


class TestMergeComposition:
    def test_merge_cell_contributions_composes_in_enumeration_order(self) -> None:
        """Non-empty mappings place under their tool key; an empty skips."""
        from goga.schema.hooks import ToolContribution, merge_cell_contributions

        contributions = [
            ToolContribution(tool="alpha", facts={"x": 1}),
            ToolContribution(tool="beta", facts={"y": 2}),
            ToolContribution(tool="gamma", facts={}),
        ]
        snapshot = [(contribution.tool, dict(contribution.facts)) for contribution in contributions]

        result = merge_cell_contributions(contributions)

        assert result == {"alpha": {"x": 1}, "beta": {"y": 2}}
        assert list(result) == ["alpha", "beta"]
        assert [(contribution.tool, dict(contribution.facts)) for contribution in contributions] == snapshot

    def test_merge_is_pure_the_inputs_stay_unmutated(self) -> None:
        """The list and each mapping are unmutated; the result is a new mapping."""
        from goga.schema.hooks import ToolContribution, merge_cell_contributions

        alpha_facts = {"x": 1}
        beta_facts = {"y": 2}
        contributions = [
            ToolContribution(tool="alpha", facts=alpha_facts),
            ToolContribution(tool="beta", facts=beta_facts),
        ]

        result = merge_cell_contributions(contributions)

        assert alpha_facts == {"x": 1}
        assert beta_facts == {"y": 2}
        assert len(contributions) == 2
        assert isinstance(result, dict)

    def test_merge_returns_a_new_mapping_every_call(self) -> None:
        """The composed mapping is fresh — repeated calls never alias."""
        from goga.schema.hooks import ToolContribution, merge_cell_contributions

        contributions = [ToolContribution(tool="alpha", facts={"x": 1})]

        first = merge_cell_contributions(contributions)
        second = merge_cell_contributions(contributions)

        assert first == second
        assert first is not second

    def test_merge_of_no_contributions_is_the_empty_mapping(self) -> None:
        """Nothing committed — the empty tools area."""
        from goga.schema.hooks import merge_cell_contributions

        assert merge_cell_contributions([]) == {}

    def test_merge_skips_every_empty_contribution(self) -> None:
        """A tool's key exists iff that tool wrote at least one fact."""
        from goga.schema.hooks import ToolContribution, merge_cell_contributions

        contributions = [
            ToolContribution(tool="alpha", facts={}),
            ToolContribution(tool="beta", facts={}),
        ]

        assert merge_cell_contributions(contributions) == {}
