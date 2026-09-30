"""Contract and logic tests for the entities declared in
``goga/schema/hooks/CODEMANIFEST`` with ``location: facts.py``:

- ``CellFacts(path, description, types, usages, dependencies, children)`` —
  the authored facts of one cell, the per-cell read view delivered to a
  subscribed hook
- ``DependencyFacts(path, types, usages)`` — the imported facts of one
  dependency (pure data)
- ``SchemaNode(path, description, types, usages, dependencies, children,
  tools)`` — one node of the final assembled tree, the read-only delivered
  view of the validation gate
- ``Violation(tool, hook, reason)`` — one collected veto of the validation
  walk
- ``GateVerdict(violations)`` — the collected verdict with the derived
  ``approved`` property

Supported data only — no mocks, no filesystem: the records carry the
constructor facts verbatim; the schema walk constructs them from
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


class TestGateFactsContract:
    def test_gate_facts_are_importable_from_the_facade(self) -> None:
        """The three gate names live on the zone facade and resolve to ``facts.py``."""
        import goga.schema.hooks as facade
        from goga.schema.hooks.facts import GateVerdict, SchemaNode, Violation

        assert facade.SchemaNode is SchemaNode
        assert facade.Violation is Violation
        assert facade.GateVerdict is GateVerdict

        for name in ("SchemaNode", "Violation", "GateVerdict"):
            assert name in facade.__all__

    def test_gate_facts_are_frozen_kw_only_dataclasses(self) -> None:
        """Pure frozen data, keyword-only construction."""
        from goga.schema.hooks import GateVerdict, SchemaNode, Violation

        for record in (SchemaNode, Violation, GateVerdict):
            assert dataclasses.is_dataclass(record)
            assert is_kw_only_dataclass(record)
            assert record.__dataclass_params__.frozen

    def test_schema_node_carries_exactly_the_seven_declared_fields(self) -> None:
        """``tools`` defaults to an empty mapping; the six authored fields are required."""
        from goga.schema.hooks import SchemaNode

        assert [field.name for field in dataclasses.fields(SchemaNode)] == [
            "path",
            "description",
            "types",
            "usages",
            "dependencies",
            "children",
            "tools",
        ]

        tools = dataclasses.fields(SchemaNode)[-1]

        assert tools.default is dataclasses.MISSING
        assert tools.default_factory is dict

        with pytest.raises(TypeError):
            SchemaNode("p", "d", [], [], [], [])  # type: ignore[misc]

    def test_schema_node_annotates_the_declared_property_types(self) -> None:
        """The fields carry the contract property types."""
        from goga.schema.hooks import DependencyFacts, SchemaNode

        hints = typing.get_type_hints(SchemaNode)

        assert hints["path"] is str
        assert hints["description"] is str
        assert hints["types"] == list[str]
        assert hints["usages"] == list[str]
        assert hints["dependencies"] == list[DependencyFacts]
        assert hints["children"] == list[SchemaNode]
        assert hints["tools"] == dict[str, dict[str, object]]

    def test_violation_carries_exactly_the_declared_fields(self) -> None:
        """``tool``, ``hook``, ``reason`` — names, order, all required."""
        from goga.schema.hooks import Violation

        assert [field.name for field in dataclasses.fields(Violation)] == [
            "tool",
            "hook",
            "reason",
        ]

        assert all(
            field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
            for field in dataclasses.fields(Violation)
        )

        hints = typing.get_type_hints(Violation)

        assert hints["tool"] is str
        assert hints["hook"] is str
        assert hints["reason"] is str

    def test_gate_verdict_carries_violations_only_approved_is_derived(self) -> None:
        """``approved`` is a derived property, not a constructor field."""
        from goga.schema.hooks import GateVerdict, Violation

        assert [field.name for field in dataclasses.fields(GateVerdict)] == ["violations"]

        hints = typing.get_type_hints(GateVerdict)

        assert hints["violations"] == list[Violation]

        assert isinstance(GateVerdict.approved, property)
        assert typing.get_type_hints(GateVerdict.approved.fget)["return"] is bool
        assert "approved" not in hints

        with pytest.raises(TypeError):
            GateVerdict(violations=[], approved=True)  # type: ignore[call-arg]


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


class TestGateFactsValues:
    def _node(self, path: str = "goga/schema") -> object:
        """A minimal leaf node — one dependency, no children, no overlay."""
        from goga.schema.hooks import SchemaNode

        return SchemaNode(
            path=path,
            description="d",
            types=["schema"],
            usages=["convention"],
            dependencies=[_dependency()],
            children=[],
        )

    def test_violation_fields_hold_the_passed_values_verbatim(self) -> None:
        """Pure data — every field round-trips the exact value passed."""
        from goga.schema.hooks import Violation

        violation = Violation(tool="alpha", hook="veto_alpha", reason="broken")

        assert violation.tool == "alpha"
        assert violation.hook == "veto_alpha"
        assert violation.reason == "broken"

    def test_gate_verdict_approved_tracks_the_violations_list(self) -> None:
        """Empty list approves; any collected violation does not."""
        from goga.schema.hooks import GateVerdict, Violation

        assert GateVerdict(violations=[]).approved is True
        assert GateVerdict(violations=[Violation(tool="t", hook="h", reason="r")]).approved is False

        several = GateVerdict(
            violations=[
                Violation(tool="alpha", hook="veto_alpha", reason="broken"),
                Violation(tool="beta", hook="boom_beta", reason="kaboom"),
            ]
        )

        assert several.approved is False
        assert several.violations == [
            Violation(tool="alpha", hook="veto_alpha", reason="broken"),
            Violation(tool="beta", hook="boom_beta", reason="kaboom"),
        ]

    def test_schema_node_tools_defaults_to_empty_mapping(self) -> None:
        """Omitting ``tools`` yields a fresh empty mapping — no tool contributed."""
        first = self._node()
        second = self._node()

        assert first.tools == {}
        assert first.tools is not second.tools

    def test_schema_node_children_recursion_round_trips(self) -> None:
        """A node whose children contain nodes round-trips at every depth."""
        from goga.schema.hooks import SchemaNode

        leaf = self._node("goga/schema/hooks")
        middle = SchemaNode(
            path="goga/schema",
            description="d",
            types=["schema"],
            usages=["convention"],
            dependencies=[],
            children=[leaf],
            tools={"alpha": {"nested": {"k": 1}}},
        )
        root = SchemaNode(
            path="goga",
            description="d",
            types=[],
            usages=[],
            dependencies=[],
            children=[middle],
        )

        assert root.children == [middle]
        assert root.children[0].children == [leaf]
        assert root.children[0].children[0].path == "goga/schema/hooks"
        assert middle.tools == {"alpha": {"nested": {"k": 1}}}

    def test_frozen_gate_facts_block_attribute_assignment(self) -> None:
        """``FrozenInstanceError`` — surfacing as ``AttributeError``."""
        from goga.schema.hooks import GateVerdict, Violation

        node = self._node()
        violation = Violation(tool="t", hook="h", reason="r")
        verdict = GateVerdict(violations=[violation])

        with pytest.raises(AttributeError):
            node.path = "x"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            violation.reason = "x"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            verdict.violations = []  # type: ignore[misc]

        with pytest.raises(AttributeError):
            verdict.approved = True  # type: ignore[misc]
