"""Contract and logic tests for the entity declared in
``goga/contract/hooks/CODEMANIFEST`` with ``location: events.py``:

- ``ContractHooks()`` — the checkpoint surface of the contract domain: the
  staged per-tool delivery of the hard ``contract/amend_contract`` action
  over the platform facade

The delivery runs for real over the platform boundary fixtures of
``tests/hooks/conftest.py`` (re-exported by the zone test package) — the
registry, the registrars, and the delivery execute the actual platform
code; only the installed-packages mapping and the ``sys.modules`` entry of
a fake ``goga_tool_*`` package are pinned. The tests import from
``goga.contract.hooks.events`` directly — the facade identity assertions
belong to the facade suite.
"""

from __future__ import annotations

import inspect
import typing
from types import MappingProxyType

import pytest
from goga.contract.hooks.events import ContractHooks
from goga.contract.hooks.facts import CellFacts, FormFacts, MemberFacts, TypeFacts
from goga.hooks import declared_actions


def _cell(path: str = "goga/config") -> CellFacts:
    """A minimal compared cell — one entity type, one routine type.

    Args:
        path: the normalized cell path of the returned facts.

    Returns:
        The comparison facts handed to the checkpoint under test.
    """
    return CellFacts(
        path=path,
        types=[
            TypeFacts(
                name="ProjectConfig",
                signature=FormFacts(
                    codemanifest="ProjectConfig(language: str)",
                    implementation="ProjectConfig(language: str)",
                ),
                properties=[MemberFacts(name="language", form=FormFacts(codemanifest="str", implementation="str"))],
                methods=[
                    MemberFacts(name="reload", form=FormFacts(codemanifest="reload() -> None", implementation=None))
                ],
            ),
            TypeFacts(
                name="load_project_config",
                signature=FormFacts(
                    codemanifest="load_project_config() -> config: ProjectConfig",
                    implementation="load_project_config() -> config: ProjectConfig",
                ),
                properties=[],
                methods=[],
            ),
        ],
    )


# --- Contract tests ---


class TestCheckpointContract:
    def test_surface_is_importable_from_the_module(self) -> None:
        """The entity lives in ``events.py`` of the zone."""
        from goga.contract.hooks import events

        assert events.ContractHooks is ContractHooks
        assert callable(ContractHooks)

    def test_constructor_takes_no_arguments(self) -> None:
        """Cheap construction — the surface declares no parameter."""
        assert list(inspect.signature(ContractHooks).parameters) == []

    def test_amend_contract_carries_the_declared_signature(self) -> None:
        """The checkpoint takes exactly the declared parameter and returns the tools area."""
        parameters = inspect.signature(ContractHooks.amend_contract).parameters

        assert list(parameters) == ["self", "cell"]
        assert typing.get_type_hints(ContractHooks.amend_contract) == {
            "cell": CellFacts,
            "return": dict[str, dict[str, dict[str, object]]],
        }


# --- Logic tests: the checkpoint delivery (real platform) ---


class TestAmendContractDelivery:
    def test_amend_contract_commits_buffered_facts(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """One tool, one buffered fact — the composed tools area under the platform identity."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"ProjectConfig": {"coverage": 3}})

            hooks.subscribe("contract", "amend_contract", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        # The platform derives goga_tool_docs -> docs.
        assert ContractHooks().amend_contract(cell=_cell()) == {"ProjectConfig": {"docs": {"coverage": 3}}}

    def test_amend_contract_two_tools_compose_per_type(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two tools addressing the same type — both appear in that type's area, in enumeration order."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"], "goga_tool_lint": ["lint-dist"]})

        def register_docs(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"ProjectConfig": {"coverage": 3}})

            hooks.subscribe("contract", "amend_contract", "cover", cover)  # type: ignore[attr-defined]

        def register_lint(hooks: object) -> None:
            def rules(context: object) -> None:
                context.contribute({"ProjectConfig": {"rules": 7}})

            hooks.subscribe("contract", "amend_contract", "rules", rules)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register_docs)
        install_tool_package("goga_tool_lint", register_hooks=register_lint)

        result = ContractHooks().amend_contract(cell=_cell())

        assert result == {"ProjectConfig": {"docs": {"coverage": 3}, "lint": {"rules": 7}}}
        assert list(result["ProjectConfig"]) == ["docs", "lint"]  # enumeration order

    def test_amend_contract_repeated_type_address_merges_facts(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two payloads of one tool addressing one type — the merged facts of both writes."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"ProjectConfig": {"coverage": 3}})
                context.contribute({"ProjectConfig": {"tests": 12}})

            hooks.subscribe("contract", "amend_contract", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        assert ContractHooks().amend_contract(cell=_cell()) == {"ProjectConfig": {"docs": {"coverage": 3, "tests": 12}}}

    def test_amend_contract_fact_conflict_later_write_wins(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The same fact name written twice — the later write replaces the earlier one."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"ProjectConfig": {"coverage": 3}})
                context.contribute({"ProjectConfig": {"coverage": 9}})

            hooks.subscribe("contract", "amend_contract", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        assert ContractHooks().amend_contract(cell=_cell()) == {"ProjectConfig": {"docs": {"coverage": 9}}}

    def test_amend_contract_empty_contribute_commits_nothing(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """An empty outer mapping buffers but never commits — a type appears iff a fact was written."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({})

            hooks.subscribe("contract", "amend_contract", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        assert ContractHooks().amend_contract(cell=_cell()) == {}

    def test_amend_contract_no_subscriptions_returns_empty(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A tool subscribed elsewhere is unobservable — the empty tools area."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"ProjectConfig": {"coverage": 3}})

            hooks.subscribe("schema", "amend_cell", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        assert ContractHooks().amend_contract(cell=_cell()) == {}

    def test_amend_contract_no_tool_packages_returns_empty(self, pin_package_environment) -> None:
        """No tool packages installed — the empty tools area, no hook ever called."""
        pin_package_environment({})

        assert ContractHooks().amend_contract(cell=_cell()) == {}

    def test_amend_contract_builds_registry_once_per_run(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two checkpoints on one surface — the package enumeration runs exactly once."""
        boundary = pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"ProjectConfig": {"coverage": 3}})

            hooks.subscribe("contract", "amend_contract", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        surface = ContractHooks()
        first = surface.amend_contract(cell=_cell(path="goga/config"))
        second = surface.amend_contract(cell=_cell(path="goga/schema"))

        assert boundary.call_count == 1
        assert first == {"ProjectConfig": {"docs": {"coverage": 3}}}
        assert second == {"ProjectConfig": {"docs": {"coverage": 3}}}

    def test_amend_contract_accepts_list_and_tuple_values(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Sequence values pass the structural check — stored verbatim, JSON-serializable as arrays."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute(
                    {"ProjectConfig": {"tags": ["a", 1], "pair": ("x", 1.5, True, None), "mixed": [{"n": 1}]}}
                )

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        result = ContractHooks().amend_contract(cell=_cell())

        # The buffer stores the sequences verbatim — the tuple stays a tuple;
        # json.dumps serializes it as an array at the command's dump step.
        assert result == {
            "ProjectConfig": {"docs": {"tags": ["a", 1], "pair": ("x", 1.5, True, None), "mixed": [{"n": 1}]}}
        }  # type: ignore[comparison-overlap]


# --- Logic tests: the hard failures (real platform) ---


class TestAmendContractFailures:
    def test_amend_contract_crashed_hook_stops_with_clean_error(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A raising hook stops the walk — the byte-stable error naming the hook, tool, action, and cell."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})
        boom = RuntimeError("boom")

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                raise boom

            hooks.subscribe("contract", "amend_contract", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"hook cover of tool docs failed") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert str(excinfo.value) == "hook cover of tool docs failed on contract.amend_contract at goga/config: boom"
        assert excinfo.value.__cause__ is boom

    def test_amend_contract_first_failing_tool_stops_the_walk(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The alphabetically first failing tool stops the delivery — a later tool's hooks never run."""
        pin_package_environment({"goga_tool_alpha": ["alpha-dist"], "goga_tool_beta": ["beta-dist"]})
        invocations: list[str] = []

        def register_alpha(hooks: object) -> None:
            def explode(context: object) -> None:
                invocations.append("alpha")
                raise RuntimeError("kaput")

            hooks.subscribe("contract", "amend_contract", "explode", explode)  # type: ignore[attr-defined]

        def register_beta(hooks: object) -> None:
            def record(context: object) -> None:
                invocations.append("beta")
                context.contribute({"ProjectConfig": {"late": True}})

            hooks.subscribe("contract", "amend_contract", "record", record)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_alpha", register_hooks=register_alpha)
        install_tool_package("goga_tool_beta", register_hooks=register_beta)

        with pytest.raises(
            ValueError,
            match=r"hook explode of tool alpha failed on contract\.amend_contract at goga/config: kaput",
        ):
            ContractHooks().amend_contract(cell=_cell(path="goga/config"))

        assert invocations == ["alpha"]  # beta never ran — no side effects past the first failure

    def test_amend_contract_non_mapping_payload_fails(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A payload of pairs is never coerced into a mapping — the structural failure names it."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute([("ProjectConfig", {"x": 1})])  # type: ignore[arg-type]

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"structurally malformed contribution") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "tool docs failed on contract.amend_contract at goga/config: structurally malformed contribution" in str(
            excinfo.value
        )
        assert "a contribution payload is not a mapping: list" in str(excinfo.value)

    def test_amend_contract_non_string_key_fails(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A non-string type address is rejected at the merge — the message the JSON check would raise."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({42: {"x": 1}})  # type: ignore[arg-type]

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"structurally malformed contribution") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "tool docs failed on contract.amend_contract at goga/config: structurally malformed contribution" in str(
            excinfo.value
        )
        assert "non-string key 42" in str(excinfo.value)

    def test_amend_contract_non_serializable_value_fails(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """An arbitrary object is not a JSON value — the structural failure names its type."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"ProjectConfig": {"stamp": object()}})

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"structurally malformed contribution") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "tool docs failed on contract.amend_contract at goga/config: structurally malformed contribution" in str(
            excinfo.value
        )
        assert "value of type object" in str(excinfo.value)

    def test_amend_contract_empty_nested_mapping_fails(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """An addressed type with an empty fact mapping is not representable — the pinned detail."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"ProjectConfig": {}})

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"empty mapping at the merged contribution") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "empty mapping at the merged contribution.ProjectConfig" in str(excinfo.value)

    def test_amend_contract_non_dict_mapping_value_fails(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A non-dict ``Mapping`` value is not JSON-representable — the hard failure names the tool.

        A ``mappingproxy`` passes no dict check yet reads like a mapping;
        the commit point must reject it with the pinned format instead of
        letting the caller's ``json.dumps`` crash without attribution.
        """
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"ProjectConfig": {"cfg": MappingProxyType({"a": 1})}})

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"value of type mappingproxy") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "value of type mappingproxy at the merged contribution.ProjectConfig.cfg" in str(excinfo.value)

    def test_amend_contract_cyclic_contribution_fails_at_the_commit_point(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A self-referencing payload is the structural hard failure — never a ``RecursionError`` escape."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})
        cyclic: dict[str, object] = {"note": "a cell fact"}
        cyclic["self"] = cyclic

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"ProjectConfig": cyclic})  # type: ignore[arg-type]

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"circular reference at the merged contribution") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "circular reference at the merged contribution.ProjectConfig.self" in str(excinfo.value)

    def test_amend_contract_unknown_address_is_a_clean_error(
        self,
        pin_package_environment,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An undeclared address is a clean error of the emitting side — the pinned message."""
        pin_package_environment({})

        def without_the_contract_record() -> list[object]:
            return [entry for entry in declared_actions() if entry.domain != "contract"]

        monkeypatch.setattr("goga.contract.hooks.events.declared_actions", without_the_contract_record)

        with pytest.raises(ValueError, match=r"unknown hook action: contract\.amend_contract") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert str(excinfo.value) == "unknown hook action: contract.amend_contract"

    def test_amend_contract_undeclared_type_address_fails_naming_type(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A contribution addressing a type the cell does not declare fails — the message names the type."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"NotDeclared": {"x": 1}})

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"contribution addresses undeclared type NotDeclared") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert str(excinfo.value) == (
            "tool docs failed on contract.amend_contract at goga/config: "
            "contribution addresses undeclared type NotDeclared"
        )

    def test_amend_contract_broken_facade_raises_import_error(
        self,
        pin_package_environment,
    ) -> None:
        """A broken package facade at the enumeration is the single fatal case — the ``ImportError`` stands."""
        boundary = pin_package_environment({"goga_tool_broken": ["broken-dist"]})
        boundary.side_effect = ImportError("cannot import goga_tool_broken")

        with pytest.raises(ImportError) as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "cannot import goga_tool_broken" in str(excinfo.value)


# --- Logic tests: the delivery edges (real platform) ---


class TestAmendContractEdges:
    def test_amend_contract_cell_without_types_rejects_any_contribution(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A cell with no declared types still delivers — but any non-empty contribution is a bad address."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"ProjectConfig": {"x": 1}})

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"contribution addresses undeclared type ProjectConfig") as excinfo:
            ContractHooks().amend_contract(cell=CellFacts(path="goga/empty", types=[]))

        assert "contribution addresses undeclared type ProjectConfig" in str(excinfo.value)

    def test_amend_contract_routine_type_receives_tools_area(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A routine type is a first-class address — its tools area lands next to the signature."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"load_project_config": {"calls": 4}})

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        assert ContractHooks().amend_contract(cell=_cell()) == {"load_project_config": {"docs": {"calls": 4}}}

    def test_amend_contract_tool_view_lists_are_not_shared(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Mutual blindness — one tool's in-place list write never reaches another view or the caller."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"], "goga_tool_lint": ["lint-dist"]})

        def register_docs(hooks: object) -> None:
            def mutate(context: object) -> None:
                context.cell.types.append("junk")  # the in-place channel — local to this view

            hooks.subscribe("contract", "amend_contract", "mutating", mutate)  # type: ignore[attr-defined]

        def register_lint(hooks: object) -> None:
            def rules(context: object) -> None:
                context.contribute({"ProjectConfig": {"rules": 7}})

            hooks.subscribe("contract", "amend_contract", "rules", rules)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register_docs)
        install_tool_package("goga_tool_lint", register_hooks=register_lint)

        facts = _cell()
        result = ContractHooks().amend_contract(cell=facts)

        assert list(result) == ["ProjectConfig"]  # only lint contributed — docs wrote no fact
        assert result["ProjectConfig"] == {"lint": {"rules": 7}}
        assert len(facts.types) == 2  # the caller's instance untouched

    def test_construction_enumerates_nothing(self, pin_package_environment) -> None:
        """Cheap construction — the package environment stays unread."""
        boundary = pin_package_environment({"goga_tool_demo": ["demo"]})

        ContractHooks()

        assert boundary.call_count == 0
