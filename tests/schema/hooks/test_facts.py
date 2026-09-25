"""Contract and logic tests for the entities declared in
``goga/schema/hooks/CODEMANIFEST`` with ``location: facts.py``:

- ``CellFacts(path, description, types, usages, dependencies, children)`` —
  the authored facts of one cell, the per-cell read view delivered to a
  subscribed hook
- ``DependencyFacts(path, types, usages)`` — the imported facts of one
  dependency (pure data)

Supported data only — no mocks, no filesystem: the records carry the
constructor facts verbatim; the schema walk (Task 7) constructs them from
resolved values, nothing is read inside.
"""

from __future__ import annotations

import dataclasses
import typing

import pytest

from tests.conftest import is_kw_only_dataclass


def _dependency(path: str = "goga/hooks/catalog") -> object:
    """One dependency entry — a source path with its imported names."""
    from goga.schema.hooks import DependencyFacts

    return DependencyFacts(path=path, types=["declared_actions"], usages=["convention"])


@pytest.fixture
def facts() -> object:
    """A minimal authored cell — one type, one usage, one dependency, one child."""
    from goga.schema.hooks import CellFacts

    return CellFacts(
        path="goga/schema",
        description="Owner of the schema generation walk.",
        types=["schema"],
        usages=["schema-usage"],
        dependencies=[_dependency()],
        children=["goga/schema/hooks"],
    )


# --- Contract tests ---


class TestFactsContract:
    def test_facts_are_importable_from_the_facade(self) -> None:
        """Both names live on the zone facade and resolve to ``facts.py``."""
        import goga.schema.hooks as facade
        from goga.schema.hooks.facts import CellFacts, DependencyFacts

        assert facade.CellFacts is CellFacts
        assert facade.DependencyFacts is DependencyFacts

        assert "CellFacts" in facade.__all__
        assert "DependencyFacts" in facade.__all__
        assert facade.__all__ == sorted(facade.__all__)

    def test_cell_facts_is_a_frozen_kw_only_dataclass(self) -> None:
        """Pure frozen data, keyword-only construction."""
        from goga.schema.hooks import CellFacts

        assert dataclasses.is_dataclass(CellFacts)
        assert is_kw_only_dataclass(CellFacts)
        assert CellFacts.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            CellFacts("goga/schema", "d", [], [], [], [])  # type: ignore[misc]

    def test_cell_facts_carries_exactly_the_declared_fields(self) -> None:
        """``path, description, types, usages, dependencies, children``."""
        from goga.schema.hooks import CellFacts

        assert [field.name for field in dataclasses.fields(CellFacts)] == [
            "path",
            "description",
            "types",
            "usages",
            "dependencies",
            "children",
        ]

        defaults = [(field.name, field.default) for field in dataclasses.fields(CellFacts)]

        assert defaults == [
            ("path", dataclasses.MISSING),
            ("description", dataclasses.MISSING),
            ("types", dataclasses.MISSING),
            ("usages", dataclasses.MISSING),
            ("dependencies", dataclasses.MISSING),
            ("children", dataclasses.MISSING),
        ]

    def test_cell_facts_annotates_the_declared_property_types(self) -> None:
        """The fields carry the contract property types."""
        from goga.schema.hooks import CellFacts, DependencyFacts

        hints = typing.get_type_hints(CellFacts)

        assert hints["path"] is str
        assert hints["description"] is str
        assert hints["types"] == list[str]
        assert hints["usages"] == list[str]
        assert hints["dependencies"] == list[DependencyFacts]
        assert hints["children"] == list[str]

    def test_dependency_facts_is_a_frozen_kw_only_dataclass(self) -> None:
        """Pure frozen data, keyword-only construction."""
        from goga.schema.hooks import DependencyFacts

        assert dataclasses.is_dataclass(DependencyFacts)
        assert is_kw_only_dataclass(DependencyFacts)
        assert DependencyFacts.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            DependencyFacts("goga/hooks/catalog", [], [])  # type: ignore[misc]

    def test_dependency_facts_carries_exactly_the_declared_fields(self) -> None:
        """``path, types, usages`` — names, order, all required."""
        from goga.schema.hooks import DependencyFacts

        assert [field.name for field in dataclasses.fields(DependencyFacts)] == [
            "path",
            "types",
            "usages",
        ]

        defaults = [(field.name, field.default) for field in dataclasses.fields(DependencyFacts)]

        assert defaults == [
            ("path", dataclasses.MISSING),
            ("types", dataclasses.MISSING),
            ("usages", dataclasses.MISSING),
        ]

    def test_dependency_facts_annotates_the_declared_property_types(self) -> None:
        """The fields carry the contract property types."""
        from goga.schema.hooks import DependencyFacts

        hints = typing.get_type_hints(DependencyFacts)

        assert hints["path"] is str
        assert hints["types"] == list[str]
        assert hints["usages"] == list[str]


# --- Logic tests: pure facts ---


class TestFactsValues:
    def test_fields_hold_the_passed_values_verbatim(self, facts: object) -> None:
        """Pure facts — every field round-trips the exact value passed."""
        assert facts.path == "goga/schema"
        assert facts.description == "Owner of the schema generation walk."
        assert facts.types == ["schema"]
        assert facts.usages == ["schema-usage"]
        assert facts.dependencies == [_dependency()]
        assert facts.children == ["goga/schema/hooks"]

    def test_constructor_values_are_stored_by_reference(self) -> None:
        """Nothing is read, copied, or resolved inside — the passed objects stay."""
        from goga.schema.hooks import CellFacts

        types = ["schema"]
        usages = ["schema-usage"]
        dependencies = [_dependency()]
        children = ["goga/schema/hooks"]

        facts = CellFacts(
            path="goga/schema",
            description="d",
            types=types,
            usages=usages,
            dependencies=dependencies,
            children=children,
        )

        assert facts.types is types
        assert facts.usages is usages
        assert facts.dependencies is dependencies
        assert facts.children is children

    def test_dependency_fields_hold_the_passed_values_verbatim(self) -> None:
        """Pure data — every field round-trips the exact value passed."""
        from goga.schema.hooks import DependencyFacts

        dependency = DependencyFacts(
            path="goga/hooks/catalog",
            types=["Action", "declared_actions"],
            usages=["convention"],
        )

        assert dependency.path == "goga/hooks/catalog"
        assert dependency.types == ["Action", "declared_actions"]
        assert dependency.usages == ["convention"]

    def test_frozen_facts_block_attribute_assignment(self, facts: object) -> None:
        """``FrozenInstanceError`` — surfacing as ``AttributeError``."""
        with pytest.raises(dataclasses.FrozenInstanceError) as raise_info:
            facts.path = "x"  # type: ignore[misc]

        assert isinstance(raise_info.value, AttributeError)

        with pytest.raises(AttributeError):
            facts.description = "x"  # type: ignore[misc]


class TestFactsEdgeCases:
    def test_empty_usages_children_and_dependencies_construct_and_compare_equal(self) -> None:
        """A leaf import-free cell without ``.usages/`` — empty lists all around."""
        from goga.schema.hooks import CellFacts

        def leaf() -> CellFacts:
            return CellFacts(
                path="goga/commands/schema",
                description="d",
                types=["schema"],
                usages=[],
                dependencies=[],
                children=[],
            )

        first = leaf()
        second = leaf()

        assert first.usages == []
        assert first.children == []
        assert first.dependencies == []
        assert first == second

    def test_empty_dependency_lists_construct_and_compare_equal(self) -> None:
        """A dependency importing no types and no usages still constructs."""
        from goga.schema.hooks import DependencyFacts

        first = DependencyFacts(path="goga/hooks", types=[], usages=[])
        second = DependencyFacts(path="goga/hooks", types=[], usages=[])

        assert first.types == []
        assert first.usages == []
        assert first == second
