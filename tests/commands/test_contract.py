"""Contract and behavioral tests for contract CLI command."""

import json
import sys
from pathlib import Path
from unittest import mock

import click
from click.testing import CliRunner
from goga.commands.contract import contract
from goga.config.config import BuildConfig, Config, TaskExecutor


def _make_config(lang: str = "python") -> Config:
    return Config(
        lang=lang,
        build=BuildConfig(task_executor=TaskExecutor(agent="claude")),
    )


# ── Contract tests ──────────────────────────────────────────


class TestContract:
    """Contract-level tests for contract command."""

    def test_contract_importable_from_facade(self) -> None:
        from goga.commands import contract as facade_contract

        assert facade_contract is contract

    def test_contract_is_click_command(self) -> None:
        assert isinstance(contract, click.Command)

    def test_contract_accepts_variadic_cells_and_lang(self) -> None:
        runner = CliRunner()
        result = runner.invoke(contract, ["--help"])
        assert result.exit_code == 0
        assert "CELLS" in result.output or "cells" in result.output
        assert "--lang" in result.output


# ── Behavioral tests ────────────────────────────────────────


class TestBehavioral:
    """Behavioral tests for contract command."""

    def test_command_contract_with_dispatcher(self, tmp_path: Path) -> None:
        """CLI delegates through contract_logic for python."""
        # Create a minimal Python package
        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "class MyService:\n"
            "    def run(self) -> str:\n"
            "        return ''\n"
            "\n"
            "__all__ = ['MyService']\n"
        )
        sys.path.insert(0, str(tmp_path))
        try:
            cfg = _make_config("python")
            runner = CliRunner()
            with (
                mock.patch("goga.commands.contract.load_config", return_value=cfg),
                mock.patch("goga.commands.contract.AST") as mock_ast_cls,
            ):
                # Setup AST mock
                mock_ast = mock.MagicMock()
                mock_ast_cls.return_value = mock_ast
                mock_doc = mock.MagicMock()
                mock_doc.path = "mypkg"
                mock_entity = mock.MagicMock()
                mock_entity.name = "MyService"
                mock_entity.signature = "class MyService"
                mock_entity.properties = []
                mock_method = mock.MagicMock()
                mock_method.name = "run"
                mock_method.signature = "def run(self) -> str"
                mock_entity.methods = [mock_method]
                mock_doc.body.entities = [mock_entity]
                mock_doc.body.routines = []
                mock_ast.document.return_value = mock_doc

                result = runner.invoke(contract, ["mypkg"])
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("mypkg", None)

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "mypkg" in output
        assert "MyService" in output["mypkg"]

    def test_command_contract_unsupported_language(self, tmp_path: Path) -> None:
        """Unsupported language triggers stderr and exit 1."""
        cfg = _make_config("rust")
        runner = CliRunner()
        with (
            mock.patch("goga.commands.contract.load_config", return_value=cfg),
            mock.patch("goga.commands.contract.AST") as mock_ast_cls,
        ):
            mock_ast = mock.MagicMock()
            mock_ast_cls.return_value = mock_ast
            mock_doc = mock.MagicMock()
            mock_doc.path = "goga/cell"
            mock_doc.body.entities = []
            mock_doc.body.routines = []
            mock_ast.document.return_value = mock_doc

            result = runner.invoke(contract, ["--lang", "rust", "goga/cell"])

        assert result.exit_code == 1
        assert "unsupported language" in result.output

    def test_command_contract_empty_cells_tuple(self, tmp_path: Path) -> None:
        """Empty cells tuple produces empty JSON object."""
        cfg = _make_config("python")
        runner = CliRunner()
        with (
            mock.patch("goga.commands.contract.load_config", return_value=cfg),
            mock.patch("goga.commands.contract.AST") as mock_ast_cls,
        ):
            mock_ast = mock.MagicMock()
            mock_ast_cls.return_value = mock_ast
            mock_ast.load.return_value = None

            result = runner.invoke(contract, [])

        assert result.exit_code == 0
        assert json.loads(result.output) == {}

    def test_command_contract_module_not_found(self, tmp_path: Path) -> None:
        """Missing cell module produces exit 1 and error message."""
        cfg = _make_config("python")
        runner = CliRunner()
        with (
            mock.patch("goga.commands.contract.load_config", return_value=cfg),
            mock.patch("goga.commands.contract.AST") as mock_ast_cls,
        ):
            mock_ast = mock.MagicMock()
            mock_ast_cls.return_value = mock_ast
            mock_doc = mock.MagicMock()
            mock_doc.path = "nonexistent"
            mock_entity = mock.MagicMock()
            mock_entity.name = "Foo"
            mock_entity.signature = "class Foo"
            mock_entity.properties = []
            mock_entity.methods = []
            mock_doc.body.entities = [mock_entity]
            mock_doc.body.routines = []
            mock_ast.document.return_value = mock_doc

            result = runner.invoke(contract, ["nonexistent"])

        assert result.exit_code == 1
        assert "package not importable" in result.output

    def test_command_contract_document_not_found(self, tmp_path: Path) -> None:
        """DocumentNotFoundError from AST produces exit 1 and error message."""
        from goga.ast.errors import DocumentNotFoundError

        cfg = _make_config("python")
        runner = CliRunner()
        with (
            mock.patch("goga.commands.contract.load_config", return_value=cfg),
            mock.patch("goga.commands.contract.AST") as mock_ast_cls,
        ):
            mock_ast = mock.MagicMock()
            mock_ast_cls.return_value = mock_ast
            mock_ast.document.side_effect = DocumentNotFoundError("missing_cell")

            result = runner.invoke(contract, ["missing_cell"])

        assert result.exit_code == 1
        assert "document not found" in result.output
