"""Integration: the contract command delivering to goga.hooks tool packages.

Covers two packages through the real registry, the real comparison, and the
real CLI dispatch: the ``contract`` command and the hooks tool-package
platform. Only the installed-packages boundary and the fake ``sys.modules``
entry are pinned (``pin_package_environment`` / ``install_tool_package``).
The shared scaffolding (the entity-cell writer, the runners) stays with the
command suite and is imported from it.
"""

from __future__ import annotations

import json

from goga.contract.hooks import CellFacts, FormFacts, MemberFacts, TypeFacts

from tests.commands.conftest import write_codemanifest as _write_codemanifest
from tests.commands.contract.test_contract import (
    ENTITY_CODEMANIFEST,
    ENTITY_IMPL,
    ROUTINE_CODEMANIFEST,
    ROUTINE_IMPL,
    _run_contract,
    _sys_path,
    _write_entity_cell,
    _write_goga_yml,
)
from tests.conftest import cwd as _cwd


class TestContractCheckpointIntegration:
    def test_contract_command_places_tools_area_on_type_node(
        self,
        tmp_path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The composed tools area lands on the type node of the JSON output.

        A fake docs tool subscribes the amendment checkpoint and contributes
        one fact for ``MyClass``: the returned area appears under the
        ``tools`` key of that type's node, and the comparison the output
        already carried stays byte-identical.
        """
        _write_entity_cell(tmp_path)
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks) -> None:
            def cover(context) -> None:
                context.contribute({"MyClass": {"coverage": 3}})

            hooks.subscribe("contract", "amend_contract", "cover", cover)

        install_tool_package("goga_tool_docs", register_hooks=register)

        with _cwd(tmp_path), _sys_path(str(tmp_path)):
            result = _run_contract("cell_one")

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["cell_one"]["MyClass"]["tools"] == {"docs": {"coverage": 3}}
        assert data["cell_one"]["MyClass"]["signature"]["codemanifest"] == "()"

    def test_contract_command_checkpoint_failure_is_clean_cli_error(
        self,
        tmp_path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A raising amendment hook stops the command: exit 1, clean error, no partial JSON.

        The hard action wraps the crash into the clean user-facing error —
        the message names the hook, the tool, and the action — and stdout
        stays empty: the dump happens after the delivery loop, so no
        partial JSON ever reaches it.
        """
        _write_entity_cell(tmp_path)
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks) -> None:
            def cover(context) -> None:
                raise RuntimeError("boom")

            hooks.subscribe("contract", "amend_contract", "cover", cover)

        install_tool_package("goga_tool_docs", register_hooks=register)

        with _cwd(tmp_path), _sys_path(str(tmp_path)):
            result = _run_contract("cell_one")

        assert result.exit_code == 1
        assert "Error: hook cover of tool docs failed on contract.amend_contract" in result.output
        assert result.stdout == ""

    def test_contract_command_duplicate_path_delivered_once(
        self,
        tmp_path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A path spelled two ways in one invocation is delivered once.

        The hook counts its invocations on the tool's isolated ``self``
        context — shared by every checkpoint of the run — and contributes
        the counter itself: a duplicate delivery would surface as a
        contribution of 2.
        """
        _write_entity_cell(tmp_path)
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks) -> None:
            def count(context, self) -> None:
                self.calls = getattr(self, "calls", 0) + 1
                context.contribute({"MyClass": {"calls": self.calls}})

            hooks.subscribe("contract", "amend_contract", "count", count)

        install_tool_package("goga_tool_docs", register_hooks=register)

        with _cwd(tmp_path), _sys_path(str(tmp_path)):
            result = _run_contract("cell_one", "./cell_one")

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["cell_one"]["MyClass"]["tools"] == {"docs": {"calls": 1}}

    def test_contract_command_existing_failure_precedes_hooks(
        self,
        tmp_path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A not-found document exits before the checkpoint — the hook never runs.

        The failure channels of the comparison loop all fire before any
        hook does: requesting a nonexistent cell exits 1 with the
        document-not-found error and the subscribed hook leaves its flag
        untouched.
        """
        _write_entity_cell(tmp_path)
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})
        ran = {"hook": False}

        def register(hooks) -> None:
            def cover(context) -> None:
                ran["hook"] = True
                context.contribute({"MyClass": {"coverage": 3}})

            hooks.subscribe("contract", "amend_contract", "cover", cover)

        install_tool_package("goga_tool_docs", register_hooks=register)

        with _cwd(tmp_path), _sys_path(str(tmp_path)):
            result = _run_contract("no/such/cell")

        assert result.exit_code == 1
        assert "Error: document not found: no/such/cell" in result.output
        assert ran["hook"] is False

    def test_contract_command_delivered_facts_mirror_the_comparison(
        self,
        tmp_path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The checkpoint reads the command's own comparison — every facts field mirrors it.

        Pins the delivered ``CellFacts`` of an entity cell and a routine
        cell against the authored CODEMANIFEST and implementation: the
        normalized path, each type name, the compared signature pair,
        and the compared member lists — empty for a routine. A silent
        misprojection in ``_build_cell_facts`` would deliver wrong facts
        to every subscribed tool while the output stays green.
        """
        entity = tmp_path / "cell_one"
        entity.mkdir()
        _write_codemanifest(entity, ENTITY_CODEMANIFEST)
        (entity / "__init__.py").write_text(ENTITY_IMPL, encoding="utf-8")
        routine = tmp_path / "cell_two"
        routine.mkdir()
        _write_codemanifest(routine, ROUTINE_CODEMANIFEST)
        (routine / "__init__.py").write_text(ROUTINE_IMPL, encoding="utf-8")
        _write_goga_yml(tmp_path)

        pin_package_environment({"goga_tool_docs": ["docs-dist"]})
        recorded: dict[str, CellFacts] = {}

        def register(hooks) -> None:
            def read(context) -> None:
                recorded[context.cell.path] = context.cell

            hooks.subscribe("contract", "amend_contract", "reading", read)

        install_tool_package("goga_tool_docs", register_hooks=register)

        with _cwd(tmp_path), _sys_path(str(tmp_path)):
            result = _run_contract("cell_one", "cell_two")

        assert result.exit_code == 0
        assert recorded == {
            "cell_one": CellFacts(
                path="cell_one",
                types=[
                    TypeFacts(
                        name="MyClass",
                        signature=FormFacts(codemanifest="()", implementation="()"),
                        properties=[MemberFacts(name="name", form=FormFacts(codemanifest="str", implementation="str"))],
                        methods=[
                            MemberFacts(
                                name="do_it",
                                form=FormFacts(codemanifest="(x: int) -> str", implementation="(x: int) -> str"),
                            )
                        ],
                    )
                ],
            ),
            "cell_two": CellFacts(
                path="cell_two",
                types=[
                    TypeFacts(
                        name="my_func",
                        signature=FormFacts(codemanifest="(x: int) -> int", implementation="(x: int) -> int"),
                        properties=[],
                        methods=[],
                    )
                ],
            ),
        }
