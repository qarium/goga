from __future__ import annotations

import json
from textwrap import dedent

import click
from click.testing import CliRunner
from goga.commands import contract
from goga.commands.contract import contract as contract_cmd

from tests.conftest import cwd as _cwd


def _run_contract(*args):
    runner = CliRunner()
    return runner.invoke(contract_cmd, list(args))


def _write_codemanifest(directory, content: str) -> None:
    (directory / "CODEMANIFEST").write_text(content, encoding="utf-8")


CELL_WITH_ENTITY_AND_ROUTINE = """\
Usages: {}

Annotations: ""

---
"TestEntity()":
  location: entity.py
  annotations: ""

"test_routine()":
  location: routine.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Test cell
"""

SECOND_CELL = """\
Usages: {}

Annotations: ""

---
"SecondEntity()":
  location: entity.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Second cell
"""


# --- Contract tests ---


class TestFacadeAvailability:
    def test_import_contract_from_commands(self) -> None:
        assert contract is not None

    def test_contract_is_click_command(self) -> None:
        assert isinstance(contract_cmd, click.Command)


# --- Logic tests ---


def test_contract_cli_no_args_returns_valid_json(tmp_path) -> None:
    cell_a = tmp_path / "cell_a"
    cell_a.mkdir()
    _write_codemanifest(cell_a, CELL_WITH_ENTITY_AND_ROUTINE)
    (cell_a / "__init__.py").write_text(
        dedent("""\
            class TestEntity:
                pass

            def test_routine(): ...

            __all__ = ["TestEntity", "test_routine"]
        """),
        encoding="utf-8",
    )
    (cell_a / "entity.py").write_text("", encoding="utf-8")
    (cell_a / "routine.py").write_text("", encoding="utf-8")

    with _cwd(tmp_path):
        result = _run_contract()

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, dict)
    assert len(data) == 1
    cell_data = data["cell_a"]
    assert "codemanifest" in cell_data
    assert "source" in cell_data
    assert "TestEntity" in cell_data["codemanifest"]
    assert "test_routine" in cell_data["codemanifest"]
    assert cell_data["source"] == {}


def test_contract_cli_with_path_filters_output(tmp_path) -> None:
    cell_a = tmp_path / "cell_a"
    cell_a.mkdir()
    _write_codemanifest(cell_a, CELL_WITH_ENTITY_AND_ROUTINE)
    (cell_a / "__init__.py").write_text("", encoding="utf-8")
    (cell_a / "entity.py").write_text("", encoding="utf-8")
    (cell_a / "routine.py").write_text("", encoding="utf-8")

    cell_b = tmp_path / "cell_b"
    cell_b.mkdir()
    _write_codemanifest(cell_b, SECOND_CELL)
    (cell_b / "__init__.py").write_text("", encoding="utf-8")
    (cell_b / "entity.py").write_text("", encoding="utf-8")

    with _cwd(tmp_path):
        result = _run_contract("cell_a")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, dict)
    # Only cell_a should be present
    assert "cell_a" in data
    assert "cell_b" not in data
    assert "TestEntity" in data["cell_a"]["codemanifest"]


def test_contract_cli_exit_code_on_no_errors(tmp_path) -> None:
    cell_a = tmp_path / "cell_a"
    cell_a.mkdir()
    _write_codemanifest(cell_a, CELL_WITH_ENTITY_AND_ROUTINE)
    (cell_a / "__init__.py").write_text("__all__ = []", encoding="utf-8")

    with _cwd(tmp_path):
        result = _run_contract()

    assert result.exit_code == 0


def test_contract_cli_exit_code_on_ast_errors(tmp_path) -> None:
    error_cell = tmp_path / "cell_error"
    error_cell.mkdir()
    (error_cell / "CODEMANIFEST").write_text(
        dedent("""\
            Imports:
              - Types:
                  - NonExistentType
                From: nonexistent_helper
            ---

            "SomeEntity()":
              location: entity.py
              annotations: ""
        """).lstrip("\n"),
        encoding="utf-8",
    )

    with _cwd(tmp_path):
        result = _run_contract()

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert isinstance(data, dict)
