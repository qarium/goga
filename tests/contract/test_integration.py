"""Integration tests for goga.contract package."""

import json
import sys
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.commands.contract import contract
from goga.config.config import BuildConfig, Config, TaskExecutor
from goga.contract import EntityContract, RoutineContract, python_contract

_contract_mod = sys.modules["goga.commands.contract"]


def _make_config(lang: str = "python") -> Config:
    return Config(
        lang=lang,
        build=BuildConfig(task_executor=TaskExecutor(agent="claude")),
    )


class TestSelfReference:
    """python_contract extracts the facade of its own package."""

    def test_self_contract_contains_base_contract(self):
        result = python_contract("goga/contract")
        names = [item.name for item in result]
        assert "BaseContract" in names

    def test_self_contract_contains_python_contract(self):
        result = python_contract("goga/contract")
        names = [item.name for item in result]
        assert "python_contract" in names

    def test_self_contract_base_contract_is_entity(self):
        result = python_contract("goga/contract")
        base = next(item for item in result if item.name == "BaseContract")
        assert isinstance(base, EntityContract)

    def test_self_contract_python_contract_is_routine(self):
        result = python_contract("goga/contract")
        fn = next(item for item in result if item.name == "python_contract")
        assert isinstance(fn, RoutineContract)


class TestRealPackageExtraction:
    """python_contract extracts facade from a real project submodule."""

    def test_ast_factory_has_factory(self):
        result = python_contract("goga/ast/factory")
        assert len(result) > 0
        names = [item.name for item in result]
        assert "Factory" in names

    def test_ast_factory_all_items_have_name_and_signature(self):
        result = python_contract("goga/ast/factory")
        for item in result:
            assert item.name != ""
            assert item.signature != ""

    def test_ast_factory_is_entity_with_members(self):
        result = python_contract("goga/ast/factory")
        factory = next(item for item in result if item.name == "Factory")
        assert isinstance(factory, EntityContract)
        # Factory has at least one method or property
        assert len(factory.methods) > 0 or len(factory.properties) > 0


class TestSignatureFormatMatchesContractFormat:
    """Result is serializable to contract_format: [{"name": "...", "signature": "..."}]."""

    def test_result_serializable_to_json(self):
        result = python_contract("goga/contract")
        data = [{"name": item.name, "signature": item.signature} for item in result]
        serialized = json.dumps(data)
        parsed = json.loads(serialized)
        assert parsed == data

    def test_entity_with_properties_and_methods_serializable(self):
        result = python_contract("goga/ast/factory")
        factory = next(item for item in result if item.name == "Factory")
        # Verify each property has name and signature
        for prop in factory.properties:
            assert prop.name != ""
            assert isinstance(prop.signature, str)
            assert json.dumps({"name": prop.name, "signature": prop.signature})
        # Verify each method has name and signature
        for method in factory.methods:
            assert method.name != ""
            assert isinstance(method.signature, str)
            assert json.dumps({"name": method.name, "signature": method.signature})

    def test_full_entity_serializable_with_members(self):
        result = python_contract("goga/ast/factory")
        factory = next(item for item in result if item.name == "Factory")
        data = {
            "name": factory.name,
            "signature": factory.signature,
            "properties": [{"name": p.name, "signature": p.signature} for p in factory.properties],
            "methods": [{"name": m.name, "signature": m.signature} for m in factory.methods],
        }
        serialized = json.dumps(data)
        parsed = json.loads(serialized)
        assert parsed == data


class TestEndToEndPython:
    """End-to-end: CLI -> contract_logic dispatcher -> python_contract."""

    def test_python_e2e_produces_codemanifest_implementation_pairs(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "cellpy"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "class CellService:\n"
            "    def execute(self) -> str:\n"
            "        return ''\n"
            "\n"
            "__all__ = ['CellService']\n"
        )
        sys.path.insert(0, str(tmp_path))
        try:
            cfg = _make_config("python")
            runner = CliRunner()
            with (
                mock.patch.object(_contract_mod, "load_config", return_value=cfg),
                mock.patch.object(_contract_mod, "AST") as mock_ast_cls,
            ):
                mock_ast = mock.MagicMock()
                mock_ast_cls.return_value = mock_ast
                mock_doc = mock.MagicMock()
                mock_doc.path = "cellpy"
                mock_entity = mock.MagicMock()
                mock_entity.name = "CellService"
                mock_entity.signature = "class CellService"
                mock_entity.properties = []
                mock_method = mock.MagicMock()
                mock_method.name = "execute"
                mock_method.signature = "def execute(self) -> str"
                mock_entity.methods = [mock_method]
                mock_doc.body.entities = [mock_entity]
                mock_doc.body.routines = []
                mock_ast.document.return_value = mock_doc

                result = runner.invoke(contract, ["cellpy"])
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("cellpy", None)

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "cellpy" in output
        svc = output["cellpy"]["CellService"]
        assert "codemanifest" in svc["signature"]
        assert "implementation" in svc["signature"]
        assert "execute" in svc["methods"]
        assert "codemanifest" in svc["methods"]["execute"]
        assert "implementation" in svc["methods"]["execute"]


def _golang_available() -> bool:
    try:
        import tree_sitter_go  # noqa: F401

        return True
    except ImportError:
        return False


class TestEndToEndGolang:
    """End-to-end: CLI -> contract_logic dispatcher -> golang_contract."""

    @pytest.mark.skipif(
        not _golang_available(),
        reason="tree-sitter-go not installed",
    )
    def test_golang_e2e_produces_routine_contract(self, tmp_path: Path) -> None:
        go_dir = tmp_path / "cellgo"
        go_dir.mkdir()
        (go_dir / "example.go").write_text(
            'package cellgo\n\nfunc Hello(name string) string { return "" }\n'
        )
        cfg = _make_config("golang")
        runner = CliRunner()
        with (
            mock.patch.object(_contract_mod, "load_config", return_value=cfg),
            mock.patch.object(_contract_mod, "AST") as mock_ast_cls,
        ):
            mock_ast = mock.MagicMock()
            mock_ast_cls.return_value = mock_ast
            mock_doc = mock.MagicMock()
            mock_doc.path = "cellgo"
            mock_routine = mock.MagicMock()
            mock_routine.name = "Hello"
            mock_routine.signature = "func Hello(name string) string"
            mock_doc.body.entities = []
            mock_doc.body.routines = [mock_routine]
            mock_ast.document.return_value = mock_doc

            result = runner.invoke(contract, ["--lang", "golang", str(go_dir)])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "cellgo" in output
        assert "Hello" in output["cellgo"]
        assert "codemanifest" in output["cellgo"]["Hello"]["signature"]
        assert "implementation" in output["cellgo"]["Hello"]["signature"]


class TestMultipleCells:
    """Multiple cell paths in a single CLI invocation."""

    def test_multiple_cells_produces_entries_for_each(self, tmp_path: Path) -> None:
        pkg_a = tmp_path / "cell_a"
        pkg_a.mkdir()
        (pkg_a / "__init__.py").write_text(
            "class ServiceA:\n    pass\n\n__all__ = ['ServiceA']\n"
        )
        pkg_b = tmp_path / "cell_b"
        pkg_b.mkdir()
        (pkg_b / "__init__.py").write_text(
            "class ServiceB:\n    pass\n\n__all__ = ['ServiceB']\n"
        )
        sys.path.insert(0, str(tmp_path))
        try:
            cfg = _make_config("python")
            runner = CliRunner()
            with (
                mock.patch.object(_contract_mod, "load_config", return_value=cfg),
                mock.patch.object(_contract_mod, "AST") as mock_ast_cls,
            ):
                mock_ast = mock.MagicMock()
                mock_ast_cls.return_value = mock_ast

                def make_doc(name: str) -> mock.MagicMock:
                    doc = mock.MagicMock()
                    doc.path = name
                    entity = mock.MagicMock()
                    entity.name = name.replace("_", "").title() + "Service"
                    entity.signature = f"class {entity.name}"
                    entity.properties = []
                    entity.methods = []
                    doc.body.entities = [entity]
                    doc.body.routines = []
                    return doc

                mock_ast.document.side_effect = make_doc

                result = runner.invoke(contract, ["cell_a", "cell_b"])
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("cell_a", None)
            sys.modules.pop("cell_b", None)

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "cell_a" in output
        assert "cell_b" in output


class TestErrorPropagation:
    """Errors propagate correctly through the full chain: dispatcher -> CLI."""

    def test_unsupported_language_stderr_exit1(self) -> None:
        cfg = _make_config("rust")
        runner = CliRunner()
        with (
            mock.patch.object(_contract_mod, "load_config", return_value=cfg),
            mock.patch.object(_contract_mod, "AST") as mock_ast_cls,
        ):
            mock_ast = mock.MagicMock()
            mock_ast_cls.return_value = mock_ast
            mock_doc = mock.MagicMock()
            mock_doc.path = "some_cell"
            mock_doc.body.entities = []
            mock_doc.body.routines = []
            mock_ast.document.return_value = mock_doc

            result = runner.invoke(contract, ["--lang", "rust", "some_cell"])

        assert result.exit_code == 1
        assert "unsupported language" in result.output

    def test_module_not_found_stderr_exit1(self) -> None:
        cfg = _make_config("python")
        runner = CliRunner()
        with (
            mock.patch.object(_contract_mod, "load_config", return_value=cfg),
            mock.patch.object(_contract_mod, "AST") as mock_ast_cls,
        ):
            mock_ast = mock.MagicMock()
            mock_ast_cls.return_value = mock_ast
            mock_doc = mock.MagicMock()
            mock_doc.path = "nonexistent_pkg"
            mock_entity = mock.MagicMock()
            mock_entity.name = "Ghost"
            mock_entity.signature = "class Ghost"
            mock_entity.properties = []
            mock_entity.methods = []
            mock_doc.body.entities = [mock_entity]
            mock_doc.body.routines = []
            mock_ast.document.return_value = mock_doc

            result = runner.invoke(contract, ["nonexistent_pkg"])

        assert result.exit_code == 1
        assert "package not importable" in result.output
