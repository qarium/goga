"""Contract and logic tests for the entities declared in
``goga/codegraph/hooks/CODEMANIFEST`` with ``location: facts.py``:

- ``NodeFacts(cell, types, dependencies, children)`` — the code-derived
  facts of one node, the per-node read view delivered to a subscribed hook
- ``Violation(tool, hook, reason)`` — one collected veto of the validation
  walk
- ``GateVerdict(violations)`` — the collected verdict with the derived
  ``approved`` property

Supported data only — no mocks, no filesystem: the records carry the
constructor facts verbatim in fresh containers at every level; the
assembly constructs them from resolved values, nothing is read inside.
"""

from __future__ import annotations

import dataclasses
import typing

import pytest

from tests.conftest import is_kw_only_dataclass


@pytest.fixture
def facts() -> object:
    """A minimal code-derived node — one type, one dependency, one child."""
    from goga.codegraph.hooks import NodeFacts

    return NodeFacts(
        cell="goga/config",
        types=["ProjectConfig"],
        dependencies={"goga/hooks": ["HookRegistry"]},
        children=["goga/config/hooks"],
    )


# --- Contract tests ---


class TestFactsContract:
    def test_facts_are_importable_from_the_facade(self) -> None:
        """The three names live on the zone facade and resolve to ``facts.py``."""
        import goga.codegraph.hooks as facade
        from goga.codegraph.hooks.facts import GateVerdict, NodeFacts, Violation

        assert facade.NodeFacts is NodeFacts
        assert facade.Violation is Violation
        assert facade.GateVerdict is GateVerdict

        for name in ("NodeFacts", "Violation", "GateVerdict"):
            assert name in facade.__all__

        assert facade.__all__ == sorted(facade.__all__)

    def test_facts_are_frozen_kw_only_dataclasses(self) -> None:
        """Pure frozen data, keyword-only construction."""
        from goga.codegraph.hooks import GateVerdict, NodeFacts, Violation

        for record in (NodeFacts, Violation, GateVerdict):
            assert dataclasses.is_dataclass(record)
            assert is_kw_only_dataclass(record)
            assert record.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            NodeFacts("goga/config", [], {}, [])  # type: ignore[misc]

        with pytest.raises(TypeError):
            Violation("t", "h", "r")  # type: ignore[misc]

        with pytest.raises(TypeError):
            GateVerdict([])  # type: ignore[misc]

    def test_node_facts_carries_exactly_the_declared_fields(self) -> None:
        """``cell, types, dependencies, children`` — names, order, all required."""
        from goga.codegraph.hooks import NodeFacts

        assert [field.name for field in dataclasses.fields(NodeFacts)] == [
            "cell",
            "types",
            "dependencies",
            "children",
        ]

        assert all(
            field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
            for field in dataclasses.fields(NodeFacts)
        )

    def test_node_facts_annotates_the_declared_property_types(self) -> None:
        """The fields carry the contract property types."""
        from goga.codegraph.hooks import NodeFacts

        hints = typing.get_type_hints(NodeFacts)

        assert hints["cell"] is str
        assert hints["types"] == list[str]
        assert hints["dependencies"] == dict[str, list[str]]
        assert hints["children"] == list[str]

    def test_violation_carries_exactly_the_declared_fields(self) -> None:
        """``tool``, ``hook``, ``reason`` — names, order, all required."""
        from goga.codegraph.hooks import Violation

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
        from goga.codegraph.hooks import GateVerdict, Violation

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
        assert facts.cell == "goga/config"
        assert facts.types == ["ProjectConfig"]
        assert facts.dependencies == {"goga/hooks": ["HookRegistry"]}
        assert facts.children == ["goga/config/hooks"]

    def test_constructor_containers_are_copied_fresh_at_every_level(self) -> None:
        """Mutating the caller's containers never reaches the delivered facts."""
        from goga.codegraph.hooks import NodeFacts

        types = ["ProjectConfig"]
        dependency_types = ["HookRegistry"]
        dependencies = {"goga/hooks": dependency_types}
        children = ["goga/config/hooks"]

        facts = NodeFacts(cell="goga/config", types=types, dependencies=dependencies, children=children)

        types.append("LintConfig")
        dependency_types.append("ToolHooks")
        dependencies["goga/commands"] = ["schema"]
        children.append("goga/config/commands")

        assert facts.types == ["ProjectConfig"]
        assert facts.dependencies == {"goga/hooks": ["HookRegistry"]}
        assert facts.children == ["goga/config/hooks"]

    def test_frozen_facts_block_attribute_assignment(self, facts: object) -> None:
        """``FrozenInstanceError`` — surfacing as ``AttributeError``."""
        with pytest.raises(dataclasses.FrozenInstanceError) as raise_info:
            facts.cell = "x"  # type: ignore[misc]

        assert isinstance(raise_info.value, AttributeError)

        with pytest.raises(AttributeError):
            facts.types = []  # type: ignore[misc]


class TestFactsEdgeCases:
    def test_empty_types_dependencies_and_children_construct_and_compare_equal(self) -> None:
        """A leaf dependency-less cell — empty containers all around."""
        from goga.codegraph.hooks import NodeFacts

        def leaf() -> NodeFacts:
            return NodeFacts(cell="goga/commands/config", types=[], dependencies={}, children=[])

        first = leaf()
        second = leaf()

        assert first.types == []
        assert first.dependencies == {}
        assert first.children == []
        assert first == second

    def test_children_may_name_cells_pruned_from_the_current_run(self) -> None:
        """The facts never prune — the child list is the complete code-derived subtree."""
        from goga.codegraph.hooks import NodeFacts

        facts = NodeFacts(
            cell="goga",
            types=[],
            dependencies={},
            children=["goga/commands", "goga/hooks"],
        )

        assert facts.children == ["goga/commands", "goga/hooks"]


class TestGateFactsValues:
    def test_violation_fields_hold_the_passed_values_verbatim(self) -> None:
        """Pure data — every field round-trips the exact value passed."""
        from goga.codegraph.hooks import Violation

        violation = Violation(tool="gate", hook="veto_tree", reason="broken")

        assert violation.tool == "gate"
        assert violation.hook == "veto_tree"
        assert violation.reason == "broken"

    def test_gate_verdict_approved_tracks_the_violations_list(self) -> None:
        """Empty list approves; any collected violation does not."""
        from goga.codegraph.hooks import GateVerdict, Violation

        violation = Violation(tool="t", hook="h", reason="r")

        assert GateVerdict(violations=[]).approved is True

        verdict = GateVerdict(violations=[violation])

        assert verdict.approved is False
        assert verdict.violations == [Violation(tool="t", hook="h", reason="r")]

    def test_frozen_gate_facts_block_attribute_assignment(self) -> None:
        """``FrozenInstanceError`` — surfacing as ``AttributeError``."""
        from goga.codegraph.hooks import GateVerdict, Violation

        violation = Violation(tool="t", hook="h", reason="r")
        verdict = GateVerdict(violations=[violation])

        with pytest.raises(AttributeError):
            violation.reason = "x"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            verdict.violations = []  # type: ignore[misc]

        with pytest.raises(AttributeError):
            verdict.approved = True  # type: ignore[misc]
