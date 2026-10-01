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
from collections.abc import Iterator, Mapping
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


class _NonPairItemsMapping(Mapping):
    """A payload mapping whose ``items`` yields a non-iterable element.

    The commit point unpacks each element of ``items``; this mapping
    must fail the commit as a structural failure, never crash the
    merge with a raw ``TypeError``.
    """

    def items(self) -> Iterator[object]:
        """Yield one non-iterable element — never a key-value pair."""
        return iter([42])

    def __iter__(self) -> Iterator[object]:
        return iter(())

    def __len__(self) -> int:
        return 0

    def __getitem__(self, key: object) -> object:
        raise KeyError(key)


class _UnhashableKeysMapping(Mapping):
    """A fact mapping whose iteration yields an unhashable key.

    ``dict.update`` inserts every key before the JSON check runs, so
    an unhashable key would raise a raw ``TypeError`` the commit
    point must intercept.
    """

    def __iter__(self) -> Iterator[list[str]]:
        return iter([["cfg"]])

    def __len__(self) -> int:
        return 1

    def __getitem__(self, key: object) -> object:
        return 1


class _FailingLookupMapping(Mapping):
    """A fact mapping whose ``__getitem__`` raises ``KeyError``.

    ``dict.update`` reads every key back through ``__getitem__``; a
    lazy mapping whose backing store drops the key between ``keys``
    and the lookup would raise a raw ``KeyError`` — not a
    ``ValueError`` — the commit point must intercept.
    """

    def __iter__(self) -> Iterator[object]:
        return iter(["cfg"])

    def __len__(self) -> int:
        return 1

    def __getitem__(self, key: object) -> object:
        raise KeyError(key)


class _FailingItemsMapping(Mapping):
    """A payload mapping whose ``items`` raises while enumerated.

    A mapping view over a live source can fail mid-enumeration; the
    raw exception — here a ``RuntimeError`` — must not escape the
    commit point.
    """

    def items(self) -> Iterator[object]:
        raise RuntimeError("items failed")

    def __iter__(self) -> Iterator[object]:
        return iter(())

    def __len__(self) -> int:
        return 0

    def __getitem__(self, key: object) -> object:
        raise KeyError(key)


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

    def test_amend_contract_two_hooks_of_one_tool_merge(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two hooks of one tool share one view and buffer — their payloads merge into one contribution.

        Pins the tool-granular commit against a per-hook commit: the
        buffered facts of both hooks land under the single tool identity.
        """
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"ProjectConfig": {"coverage": 3}})

            def tests(context: object) -> None:
                context.contribute({"ProjectConfig": {"tests": 12}})

            hooks.subscribe("contract", "amend_contract", "cover", cover)  # type: ignore[attr-defined]
            hooks.subscribe("contract", "amend_contract", "tests", tests)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        assert ContractHooks().amend_contract(cell=_cell()) == {"ProjectConfig": {"docs": {"coverage": 3, "tests": 12}}}

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

    def test_amend_contract_second_hook_failure_discards_tool_contribution(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The commit granularity is the tool — a failing hook discards the tool's whole buffer.

        The first hook of the tool contributes; the second raises. The
        walk stops at the second hook with the hook failure — the error
        is not a commit error, so the tool's buffered payload never
        reached the structural check, let alone the tools area.
        """
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})
        invocations: list[str] = []
        kaput = RuntimeError("kaput")

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                invocations.append("cover")
                context.contribute({"ProjectConfig": {"coverage": 3}})

            def explode(context: object) -> None:
                invocations.append("explode")
                raise kaput

            hooks.subscribe("contract", "amend_contract", "cover", cover)  # type: ignore[attr-defined]
            hooks.subscribe("contract", "amend_contract", "explode", explode)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(
            ValueError,
            match=r"hook explode of tool docs failed on contract\.amend_contract at goga/config: kaput",
        ) as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert invocations == ["cover", "explode"]  # both hooks of the tool ran — the commit never did
        assert excinfo.value.__cause__ is kaput

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

    def test_amend_contract_non_mapping_type_contribution_fails(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A type address carrying a non-mapping value is never coerced — the structural failure names it.

        Without the guard the merge would hit ``dict.update`` with an
        ``int`` and escape the commit wrapper as a raw ``TypeError``.
        """
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"ProjectConfig": 42})  # type: ignore[arg-type]

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"structurally malformed contribution") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "tool docs failed on contract.amend_contract at goga/config: structurally malformed contribution" in str(
            excinfo.value
        )
        assert "a type contribution is not a mapping: int" in str(excinfo.value)

    def test_amend_contract_non_pair_items_mapping_fails(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A payload mapping whose ``items`` yields a non-pair.

        Unpacking such an element would raise a raw ``TypeError`` —
        the commit intercepts it as the structural failure, per the
        never-a-raw-``TypeError`` guarantee of the merge.
        """

        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute(_NonPairItemsMapping())  # type: ignore[arg-type]

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"structurally malformed contribution") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "tool docs failed on contract.amend_contract at goga/config: structurally malformed contribution" in str(
            excinfo.value
        )
        assert "cannot unpack non-iterable int object" in str(excinfo.value)

    def test_amend_contract_unhashable_fact_key_fails(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A fact mapping yielding an unhashable key.

        ``dict.update`` inserts the key before the JSON check runs and
        would raise a raw ``TypeError`` — the commit intercepts it as
        the structural failure.
        """

        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"ProjectConfig": _UnhashableKeysMapping()})  # type: ignore[arg-type]

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"structurally malformed contribution") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "tool docs failed on contract.amend_contract at goga/config: structurally malformed contribution" in str(
            excinfo.value
        )
        assert "unhashable type: 'list'" in str(excinfo.value)

    def test_amend_contract_failing_lookup_mapping_fails(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A fact mapping whose ``__getitem__`` raises ``KeyError``.

        ``dict.update`` reads every key back through ``__getitem__``
        during the merge; a lazy mapping failing the lookup would
        raise a raw ``KeyError`` — not a ``ValueError``, so neither
        the commit wrapper nor the command's except clause would
        catch it. The commit intercepts it as the structural failure.
        """

        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"ProjectConfig": _FailingLookupMapping()})  # type: ignore[arg-type]

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"structurally malformed contribution") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "tool docs failed on contract.amend_contract at goga/config: structurally malformed contribution" in str(
            excinfo.value
        )
        assert "'cfg'" in str(excinfo.value)

    def test_amend_contract_failing_items_mapping_fails(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A payload mapping whose ``items`` raises while enumerated.

        The merge walk enumerates ``items`` of every payload; a
        mapping view failing mid-enumeration would raise a raw
        ``RuntimeError`` the commit point must intercept as the
        structural failure.
        """

        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute(_FailingItemsMapping())  # type: ignore[arg-type]

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"structurally malformed contribution") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "tool docs failed on contract.amend_contract at goga/config: structurally malformed contribution" in str(
            excinfo.value
        )
        assert "items failed" in str(excinfo.value)

    def test_amend_contract_non_finite_float_fails(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A non-finite float is not a JSON value — ``dumps`` would emit it as a literal; the validator rejects it."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"ProjectConfig": {"score": float("nan")}})

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"structurally malformed contribution") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "non-finite float at the merged contribution.ProjectConfig.score" in str(excinfo.value)

    def test_amend_contract_nested_non_string_key_fails(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A non-string key nested inside a fact value — ``dumps`` would coerce it; the validator rejects it."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"ProjectConfig": {"cfg": {42: "x"}}})  # type: ignore[arg-type]

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"structurally malformed contribution") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "non-string key 42 at the merged contribution.ProjectConfig.cfg" in str(excinfo.value)

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

    def test_amend_contract_too_deep_contribution_fails(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A nesting past the validator's depth limit is the structural failure — never a serializer crash.

        A buffer deep enough to pass the validator but starve the JSON
        encoder would crash the caller's ``json.dumps`` with a raw
        ``RecursionError``; the depth limit rejects it at the commit
        point, naming the tool like any other malformed contribution.
        """
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})
        deep: object = 1
        for _ in range(200):
            deep = {"a": deep}

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"ProjectConfig": {"deep": deep}})

            hooks.subscribe("contract", "amend_contract", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(ValueError, match=r"structurally malformed contribution") as excinfo:
            ContractHooks().amend_contract(cell=_cell())

        assert "tool docs failed on contract.amend_contract at goga/config: structurally malformed contribution" in str(
            excinfo.value
        )
        assert "nesting too deep at the merged contribution.ProjectConfig.deep" in str(excinfo.value)

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

    def test_amend_contract_committed_area_is_owned(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Ownership of the commit — a retained container mutated at a later cell never reaches a committed area.

        The tool's context survives the checkpoint (one instance per
        tool per run) and the merge shares nested containers with the
        tool's buffer: without the commit-point copy, the later cell's
        in-place append would write into the first cell's
        already-validated area.
        """
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})
        held: dict[str, list[str]] = {}

        def register(hooks: object) -> None:
            def retain(context: object, self: object) -> None:
                if "log" not in held:
                    held["log"] = ["start"]
                    context.contribute({"ProjectConfig": {"log": held["log"]}})
                    return

                held["log"].append("mutated-at-the-later-cell")
                context.contribute({"load_project_config": {"calls": 4}})

            hooks.subscribe("contract", "amend_contract", "retain", retain)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        surface = ContractHooks()
        first = surface.amend_contract(cell=_cell(path="goga/config"))
        second = surface.amend_contract(cell=_cell(path="goga/schema"))

        assert second == {"load_project_config": {"docs": {"calls": 4}}}
        assert first == {"ProjectConfig": {"docs": {"log": ["start"]}}}  # unchanged by the later mutation
        assert first["ProjectConfig"]["docs"]["log"] is not held["log"]  # the committed area is owned, not aliased

    def test_construction_enumerates_nothing(self, pin_package_environment) -> None:
        """Cheap construction — the package environment stays unread."""
        boundary = pin_package_environment({"goga_tool_demo": ["demo"]})

        ContractHooks()

        assert boundary.call_count == 0
