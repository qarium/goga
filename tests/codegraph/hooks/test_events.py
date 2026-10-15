"""Contract and logic tests for the entity declared in
``goga/codegraph/hooks/CODEMANIFEST`` with ``location: events.py``:

- ``CodegraphHooks()`` — the checkpoint surface of the codegraph domain:
  the staged per-tool delivery of the hard ``codegraph/amend_node``
  action over the platform facade, and the validation gate
  ``validate_graph`` — the walk-to-completion delivery of the hard
  ``codegraph/validate_graph`` action that collects one violation per
  non-approving tool into a ``GateVerdict``

The delivery runs for real over the platform boundary fixtures of
``tests/hooks/conftest.py`` (re-exported by the zone test package) — the
registry, the registrars, and the delivery execute the actual platform
code; only the installed-packages mapping and the ``sys.modules`` entry of
a fake ``goga_tool_*`` package are pinned.
"""

from __future__ import annotations

import inspect
import typing

import pytest
from goga.codegraph.facts import CodegraphNode
from goga.codegraph.hooks import (
    CodegraphHooks,
    GateVerdict,
    GraphValidation,
    NodeFacts,
    Violation,
)
from goga.hooks import declared_actions


def _node_facts(cell: str = "goga/config") -> NodeFacts:
    """A minimal code-derived node — one type, no dependencies, one child.

    Args:
        cell: the cell path of the returned facts.

    Returns:
        The code-derived facts handed to the checkpoint under test.
    """
    return NodeFacts(
        cell=cell,
        types=["ProjectConfig"],
        dependencies={},
        children=["goga/config/hooks"],
    )


def _final_node(
    cell: str = "goga/config",
    tools: dict[str, dict[str, object]] | None = None,
) -> CodegraphNode:
    """A minimal final-tree node — one type, no dependencies, leaf.

    Args:
        cell: the cell path of the returned node.
        tools: the committed tools overlay of the node; omitted means no
            tool contributed.

    Returns:
        One node of the final assembled tree handed to the gate under test.
    """
    return CodegraphNode(
        cell=cell,
        types=["Thing"],
        dependencies={},
        children=[],
        tools=tools if tools is not None else {},
    )


def _cyclic_payload() -> dict[str, object]:
    """Build a self-referencing payload — a container holding itself is not JSON-representable.

    Returns:
        The cyclic contribution payload of the malformed-contribution table.
    """
    cyclic: dict[str, object] = {"note": "a node fact"}
    cyclic["self"] = cyclic

    return cyclic


# --- Contract tests ---


class TestCheckpointContract:
    def test_surface_is_importable_from_the_facade(self) -> None:
        """The entity lives on the zone facade and resolves to ``events.py``."""
        import goga.codegraph.hooks as facade
        from goga.codegraph.hooks.events import CodegraphHooks as Declared

        assert facade.CodegraphHooks is Declared
        assert facade.CodegraphHooks is CodegraphHooks

        assert "CodegraphHooks" in facade.__all__

    def test_constructor_takes_no_arguments(self) -> None:
        """Cheap construction — the surface declares no parameter."""
        assert list(inspect.signature(CodegraphHooks).parameters) == []

    def test_amend_node_carries_the_declared_signature(self) -> None:
        """The checkpoint takes exactly the declared parameter and returns the tools area."""
        parameters = inspect.signature(CodegraphHooks.amend_node).parameters

        assert list(parameters) == ["self", "node"]
        assert typing.get_type_hints(CodegraphHooks.amend_node) == {
            "node": NodeFacts,
            "return": dict[str, dict[str, object]],
        }

    def test_validate_graph_carries_the_declared_signature(self) -> None:
        """The gate takes exactly the declared parameter and returns the verdict."""
        parameters = inspect.signature(CodegraphHooks.validate_graph).parameters

        assert list(parameters) == ["self", "tree"]
        assert typing.get_type_hints(CodegraphHooks.validate_graph) == {
            "tree": list[CodegraphNode],
            "return": GateVerdict,
        }

    def test_surface_stays_in_the_facade_all_alongside_the_gate_names(self) -> None:
        """The zone facade keeps the checkpoint surface and the gate surface together."""
        import goga.codegraph.hooks as facade

        for name in ("CodegraphHooks", "GateVerdict", "GraphValidation", "NodeFacts", "Violation"):
            assert name in facade.__all__


# --- Logic tests: the checkpoint delivery (real platform) ---


class TestAmendNodeDelivery:
    def test_amend_node_commits_buffered_facts(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """One tool, one buffered fact — the composed tools area under the platform identity."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"coverage": 3})

            hooks.subscribe("codegraph", "amend_node", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        # The platform derives goga_tool_docs -> docs.
        assert CodegraphHooks().amend_node(node=_node_facts()) == {"docs": {"coverage": 3}}

    def test_amend_node_empty_contribute_commits_nothing(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """An empty mapping buffers but never commits — the key exists iff the merged buffer is non-empty."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})
        payloads: list[dict[str, object]] = [{}]
        views: list[object] = []

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                views.append(context)  # the delivered view — its buffer is inspected after the delivery
                context.contribute(payloads[0])

            hooks.subscribe("codegraph", "amend_node", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        assert CodegraphHooks().amend_node(node=_node_facts()) == {}  # buffered, merged to nothing, no key
        assert views[0]._pending == [{}]  # type: ignore[attr-defined]  # the empty mapping sits in the buffer

        # The inversion on the same fixture: one written fact opens the key.
        payloads[0] = {"a": 1}

        assert CodegraphHooks().amend_node(node=_node_facts()) == {"docs": {"a": 1}}

    def test_contribute_merges_key_wise_later_wins(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two payloads of one tool — the merged buffer keeps the later write per key."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"coverage": 3, "owner": "a"})
                context.contribute({"coverage": 9})

            hooks.subscribe("codegraph", "amend_node", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        assert CodegraphHooks().amend_node(node=_node_facts()) == {"docs": {"coverage": 9, "owner": "a"}}

    def test_amend_node_builds_registry_once_per_run(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two checkpoints on one surface — the package enumeration runs exactly once."""
        boundary = pin_package_environment({"goga_tool_demo": ["demo"]})
        delivered: list[str] = []

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                delivered.append("amend_node")
                context.contribute({"coverage": 3})

            def watch(context: object) -> None:
                delivered.append("validate_graph")

            hooks.subscribe("codegraph", "amend_node", "cover", cover)  # type: ignore[attr-defined]
            hooks.subscribe("codegraph", "validate_graph", "watch", watch)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        surface = CodegraphHooks()
        tools = surface.amend_node(node=_node_facts(cell="a"))
        verdict = surface.validate_graph([_final_node()])

        assert boundary.call_count == 1
        assert tools == {"demo": {"coverage": 3}}
        assert verdict.approved is True
        assert delivered == ["amend_node", "validate_graph"]  # both checkpoints delivered

    def test_amend_node_committed_area_is_owned(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Ownership of the commit — a retained payload mutated at a later node never reaches a committed area.

        The tool's context survives the checkpoint (one instance per tool
        per run) and the merge shares nested containers with the tool's
        buffer: without the commit-point copy, the later node's in-place
        write would pierce the first node's already-validated area.
        """
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def cover(self: object, context: object) -> None:
                if not hasattr(self, "sink"):
                    self.sink = {"coverage": 3}  # type: ignore[attr-defined]
                else:
                    self.sink["coverage"] = 99  # the in-place mutation before every later contribute  # type: ignore[index]

                context.contribute(self.sink)  # type: ignore[arg-type]

            hooks.subscribe("codegraph", "amend_node", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        surface = CodegraphHooks()
        first = surface.amend_node(node=_node_facts(cell="a"))
        second = surface.amend_node(node=_node_facts(cell="b"))

        assert first == {"docs": {"coverage": 3}}
        assert second == {"docs": {"coverage": 99}}
        assert first == {"docs": {"coverage": 3}}  # STILL — the ownership cut of the commit point

    def test_amend_node_crashed_hook_is_a_hard_failure_naming_the_subject(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A raising hook stops the walk — the error names the hook, the tool, the action, and the node."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def boom(context: object) -> None:
                raise RuntimeError("kaboom")

            hooks.subscribe("codegraph", "amend_node", "boom", boom)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(
            ValueError,
            match=r"hook boom of tool docs failed on codegraph\.amend_node at goga/codegraph: kaboom",
        ) as excinfo:
            CodegraphHooks().amend_node(node=_node_facts(cell="goga/codegraph"))

        assert "Traceback" not in str(excinfo.value)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param([("a", 1)], id="a-non-mapping-payload"),
            pytest.param({"k": {}}, id="an-empty-nested-mapping"),
            pytest.param({1: "x"}, id="a-non-string-key"),
            pytest.param({"k": {object()}}, id="a-non-serializable-value"),
            pytest.param({"k": float("nan")}, id="a-non-finite-float"),
            pytest.param(_cyclic_payload(), id="a-self-referencing-dict"),
        ],
    )
    def test_amend_node_structurally_malformed_contribution_fails_the_same_way(
        self,
        pin_package_environment,
        install_tool_package,
        payload: object,
    ) -> None:
        """A malformed payload fails the tool commit — never a coercion, never a raw escape."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute(payload)  # type: ignore[arg-type]

            hooks.subscribe("codegraph", "amend_node", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(
            ValueError,
            match=r"tool docs failed on codegraph\.amend_node at goga/config: structurally malformed contribution",
        ):
            CodegraphHooks().amend_node(node=_node_facts(cell="goga/config"))

    def test_amend_node_unknown_address_is_a_clean_error(
        self,
        pin_package_environment,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An undeclared address is a clean error of the emitting side — the pinned message."""
        pin_package_environment({})

        def without_the_amend_record() -> list[object]:
            return [
                entry
                for entry in declared_actions()
                if not (entry.domain == "codegraph" and entry.name == "amend_node")
            ]

        monkeypatch.setattr("goga.codegraph.hooks.events.declared_actions", without_the_amend_record)

        with pytest.raises(ValueError, match=r"unknown hook action: codegraph\.amend_node"):
            CodegraphHooks().amend_node(node=_node_facts())

    def test_amend_node_accepts_list_tuple_and_float_values(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Sequence and float values pass the structural check — stored verbatim, JSON-serializable."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute(  # type: ignore[arg-defined]
                    {"tags": ["a", 1], "pair": ("x", 1.5, True, None), "mixed": [{"n": 1}]}
                )

            hooks.subscribe("codegraph", "amend_node", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        result = CodegraphHooks().amend_node(node=_node_facts())

        # The buffer stores the sequences verbatim — the tuple stays a tuple;
        # json.dumps serializes it as an array at the command's dump step.
        assert result == {"docs": {"tags": ["a", 1], "pair": ("x", 1.5, True, None), "mixed": [{"n": 1}]}}  # type: ignore[comparison-overlap]

    def test_amend_node_fresh_view_per_tool_keeps_writes_local(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Mutual blindness — one tool's in-place write never reaches another view or the caller."""
        pin_package_environment({"goga_tool_alpha": ["alpha-dist"], "goga_tool_beta": ["beta-dist"]})
        observed: dict[str, object] = {}

        def register_alpha(hooks: object) -> None:
            def mutate(context: object) -> None:
                context.node.types.append("X")  # the in-place channel — local to this view  # type: ignore[attr-defined]

            hooks.subscribe("codegraph", "amend_node", "mutating", mutate)  # type: ignore[attr-defined]

        def register_beta(hooks: object) -> None:
            def read(context: object) -> None:
                observed["types"] = list(context.node.types)  # type: ignore[attr-defined]

            hooks.subscribe("codegraph", "amend_node", "reading", read)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_alpha", register_hooks=register_alpha)
        install_tool_package("goga_tool_beta", register_hooks=register_beta)

        facts = _node_facts()
        tools = CodegraphHooks().amend_node(node=facts)

        assert observed["types"] == ["ProjectConfig"]  # the code-derived list, never alpha's write
        assert facts.types == ["ProjectConfig"]  # the caller's instance untouched
        assert tools == {}  # neither tool contributed a fact

    def test_construction_enumerates_nothing(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Cheap construction — the package environment stays unread."""
        boundary = pin_package_environment({"goga_tool_demo": ["demo"]})

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"a": 1})

            hooks.subscribe("codegraph", "amend_node", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        CodegraphHooks()

        assert boundary.call_count == 0


# --- Logic tests: the validation gate (real platform) ---


class TestValidateGraphDelivery:
    def test_validate_graph_collects_one_violation_per_tool_and_walks_to_completion(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """One vetoing tool — exactly one violation — while every subscribed hook of every tool still runs."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"], "goga_tool_gate": ["gate-dist"]})
        seen: list[int] = []

        def register_gate(hooks: object) -> None:
            def guard(context: GraphValidation) -> None:
                context.veto("broken")

            hooks.subscribe("codegraph", "validate_graph", "guard", guard)  # type: ignore[attr-defined]

        def register_docs(hooks: object) -> None:
            def watch(context: GraphValidation) -> None:
                seen.append(len(context.tree))

            hooks.subscribe("codegraph", "validate_graph", "watch", watch)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register_docs)
        install_tool_package("goga_tool_gate", register_hooks=register_gate)

        node = _final_node(tools={"docs": {"a": 1}})
        tree = [node]

        verdict = CodegraphHooks().validate_graph(tree)

        # Exactly one violation — the tool's veto attributed to the hook that vetoed.
        assert verdict.approved is False
        assert verdict.violations == [Violation(tool="gate", hook="guard", reason="broken")]

        # Walk to completion — the non-vetoing tool's hook ran too.
        assert seen == [1]

        # The caller's tree objects untouched — the gate view is a fresh copy per tool.
        assert tree[0] is node
        assert node.types == ["Thing"]
        assert node.tools == {"docs": {"a": 1}}

    def test_validate_graph_crash_overrides_veto_and_continues(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A hook that vetoes and then a crashing hook of the same tool — the crash wins, the walk does not stop."""
        pin_package_environment({"goga_tool_alpha": ["alpha-dist"], "goga_tool_beta": ["beta-dist"]})
        observed: list[str] = []

        def register_alpha(hooks: object) -> None:
            def veto_and_boom(context: GraphValidation) -> None:
                context.veto("v")
                raise RuntimeError("boom")

            def later(context: GraphValidation) -> None:
                observed.append("alpha_later")

            hooks.subscribe("codegraph", "validate_graph", "veto_and_boom", veto_and_boom)  # type: ignore[attr-defined]
            hooks.subscribe("codegraph", "validate_graph", "later", later)  # type: ignore[attr-defined]

        def register_beta(hooks: object) -> None:
            def watch(context: GraphValidation) -> None:
                observed.append("beta")

            hooks.subscribe("codegraph", "validate_graph", "watch", watch)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_alpha", register_hooks=register_alpha)
        install_tool_package("goga_tool_beta", register_hooks=register_beta)

        verdict = CodegraphHooks().validate_graph([_final_node()])

        # One crash violation — the crash reason overrides the buffered veto, never a raw traceback.
        assert len(verdict.violations) == 1
        assert verdict.violations[0].tool == "alpha"
        assert verdict.violations[0].hook == "veto_and_boom"
        assert verdict.violations[0].reason == "boom"
        assert "Traceback" not in verdict.violations[0].reason

        # The tool's remaining hooks stop; the other tool's hook ran — the walk continues.
        assert observed == ["beta"]

    def test_validate_graph_attributes_the_veto_to_the_vetoing_hook(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A silent hook before the vetoing one — the violation names the vetoer, never the silent hook."""
        pin_package_environment({"goga_tool_gate": ["gate-dist"]})

        def register(hooks: object) -> None:
            def quiet(context: GraphValidation) -> None:
                return None

            def guard(context: GraphValidation) -> None:
                context.veto("broken")

            hooks.subscribe("codegraph", "validate_graph", "quiet", quiet)  # type: ignore[attr-defined]
            hooks.subscribe("codegraph", "validate_graph", "guard", guard)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_gate", register_hooks=register)

        verdict = CodegraphHooks().validate_graph([_final_node()])

        assert verdict.violations == [Violation(tool="gate", hook="guard", reason="broken")]

    def test_validate_graph_delivers_fresh_tree_copy_per_tool(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Mutual blindness over the final tree — an in-place write never pierces the caller or another tool."""
        pin_package_environment({"goga_tool_alpha": ["alpha-dist"], "goga_tool_beta": ["beta-dist"]})
        recorded: list[list[str]] = []

        def register_alpha(hooks: object) -> None:
            def mutate(context: GraphValidation) -> None:
                context.tree[0].types.append("X")  # the in-place channel — local to this view

            hooks.subscribe("codegraph", "validate_graph", "mutating", mutate)  # type: ignore[attr-defined]

        def register_beta(hooks: object) -> None:
            def read(context: GraphValidation) -> None:
                recorded.append(list(context.tree[0].types))

            hooks.subscribe("codegraph", "validate_graph", "reading", read)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_alpha", register_hooks=register_alpha)
        install_tool_package("goga_tool_beta", register_hooks=register_beta)

        tree = [_final_node()]

        verdict = CodegraphHooks().validate_graph(tree)

        assert recorded == [["Thing"]]  # beta read its own fresh copy, never alpha's write
        assert tree[0].types == ["Thing"]  # the caller's tree untouched
        assert verdict.approved is True

    def test_validate_graph_tree_copy_includes_the_tools_overlay(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Mutual blindness reaches the committed overlay — a write into a delivered tools area stays local."""
        pin_package_environment({"goga_tool_alpha": ["alpha-dist"], "goga_tool_beta": ["beta-dist"]})
        recorded: list[list[str]] = []

        def register_alpha(hooks: object) -> None:
            def mutate(context: GraphValidation) -> None:
                context.tree[0].tools["docs"]["tags"].append("X")  # type: ignore[index]  # local to this view

            hooks.subscribe("codegraph", "validate_graph", "mutating", mutate)  # type: ignore[attr-defined]

        def register_beta(hooks: object) -> None:
            def read(context: GraphValidation) -> None:
                recorded.append(list(context.tree[0].tools["docs"]["tags"]))  # type: ignore[index]

            hooks.subscribe("codegraph", "validate_graph", "reading", read)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_alpha", register_hooks=register_alpha)
        install_tool_package("goga_tool_beta", register_hooks=register_beta)

        tree = [_final_node(tools={"docs": {"tags": ["a"]}})]

        CodegraphHooks().validate_graph(tree)

        assert recorded == [["a"]]  # beta read its own fresh copy, never alpha's write
        assert tree[0].tools == {"docs": {"tags": ["a"]}}  # the caller's overlay untouched

    def test_validate_graph_unknown_address_is_emitting_side_error(
        self,
        pin_package_environment,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An undeclared address is a clean error of the emitting side — the pinned message."""
        pin_package_environment({})

        def without_the_gate_record() -> list[object]:
            return [
                entry
                for entry in declared_actions()
                if not (entry.domain == "codegraph" and entry.name == "validate_graph")
            ]

        monkeypatch.setattr("goga.codegraph.hooks.events.declared_actions", without_the_gate_record)

        with pytest.raises(ValueError, match=r"unknown hook action: codegraph\.validate_graph"):
            CodegraphHooks().validate_graph([])


# --- Logic tests: the inert zone ---


class TestZoneInertness:
    @pytest.mark.parametrize("checkpoint", ["amend_node", "validate_graph"])
    def test_zone_checkpoints_without_subscriptions_are_inert(
        self,
        pin_package_environment,
        checkpoint: str,
    ) -> None:
        """No subscriptions — the empty tools area, the approved verdict, no hook ever called.

        This is what keeps plain ``goga codegraph`` byte-identical when no
        tool subscribes: the checkpoints fire, deliver nothing, and leave
        the output untouched.
        """
        pin_package_environment({})
        surface = CodegraphHooks()

        if checkpoint == "amend_node":
            assert surface.amend_node(node=_node_facts()) == {}
        else:
            verdict = surface.validate_graph([_final_node()])

            assert verdict.approved is True
            assert verdict.violations == []
