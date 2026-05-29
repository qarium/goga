from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

import click
from click.testing import CliRunner
from goga.cli import app
from goga.commands import contract
from goga.commands.contract import contract as contract_cmd

from tests.conftest import cwd as _cwd


def _run_contract(*args):
    runner = CliRunner()
    return runner.invoke(app, ["contract", *args])


def _write_codemanifest(directory: Path, content: str) -> None:
    (directory / "CODEMANIFEST").write_text(content, encoding="utf-8")


def _write_goga_yml(directory: Path) -> None:
    (directory / ".goga").mkdir(exist_ok=True)
    (directory / ".goga" / "config.yml").write_text("language: python\nbuild:\n  task_executor:\n    agent: claude\n")


@contextmanager
def _sys_path(path: str):
    sys.path.insert(0, path)
    snapshot = set(sys.modules.keys())
    try:
        yield
    finally:
        sys.path.remove(path)
        for key in set(sys.modules.keys()) - snapshot:
            del sys.modules[key]


# --- Contract tests ---


class TestFacadeAvailability:
    def test_import_contract_from_commands(self) -> None:
        assert contract is not None

    def test_contract_is_click_command(self) -> None:
        assert isinstance(contract_cmd, click.Command)

    def test_contract_command_name_is_contract(self) -> None:
        assert contract_cmd.name == "contract"


class TestApiShape:
    def test_contract_has_callback(self) -> None:
        assert contract_cmd.callback is not None

    def test_contract_has_cells_argument(self) -> None:
        param_names = [p.name for p in contract_cmd.params]
        assert "cells" in param_names

    def test_contract_cells_has_nargs_minus_one(self) -> None:
        cells_param = next(p for p in contract_cmd.params if p.name == "cells")
        assert cells_param.nargs == -1

    def test_contract_has_lang_option(self) -> None:
        param_names = [p.name for p in contract_cmd.params]
        assert "lang" in param_names

    def test_contract_lang_default_is_none(self) -> None:
        lang_param = next(p for p in contract_cmd.params if p.name == "lang")
        assert lang_param.default is None


# --- Logic tests ---

ENTITY_CODEMANIFEST = """\
Usages: {}

Annotations: ""

---

"MyClass()":
  location: myclass.py
  annotations: ""
  properties:
    "name -> str": ""
  methods:
    "do_it(x: int) -> str": ""

---

Author: Test
CreatedAt: 01/01/01
Description: Test
"""

ENTITY_IMPL = (
    "class MyClass:\n"
    "    def __init__(self):\n"
    "        pass\n"
    "    @property\n"
    "    def name(self) -> str:\n"
    "        return ''\n"
    "    def do_it(self, x: int) -> str:\n"
    "        return str(x)\n"
    "\n"
    "__all__ = ['MyClass']\n"
)

ROUTINE_CODEMANIFEST = """\
Usages: {}

Annotations: ""

---

"my_func(x: int) -> int": ""

---

Author: Test
CreatedAt: 01/01/01
Description: Test
"""

ROUTINE_IMPL = "def my_func(x: int) -> int:\n    return x\n\n__all__ = ['my_func']\n"

GO_ENTITY_CODEMANIFEST = """\
Usages: {}

Annotations: ""

---

"Hello(name: string) -> string":
  location: service.go
  annotations: ""

---

Author: Test
CreatedAt: 01/01/01
Description: Test
"""


def test_contract_single_cell_entity(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text(ENTITY_IMPL, encoding="utf-8")
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path), _sys_path(str(tmp_path)):
        result = _run_contract("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data
    assert "MyClass" in data["cell_one"]
    assert data["cell_one"]["MyClass"]["signature"]["codemanifest"] == "()"
    assert data["cell_one"]["MyClass"]["signature"]["implementation"] == "()"
    assert "name" in data["cell_one"]["MyClass"]["properties"]
    assert data["cell_one"]["MyClass"]["properties"]["name"]["codemanifest"] == "str"
    assert data["cell_one"]["MyClass"]["properties"]["name"]["implementation"] == "str"
    assert "do_it" in data["cell_one"]["MyClass"]["methods"]
    assert data["cell_one"]["MyClass"]["methods"]["do_it"]["codemanifest"] == "(x: int) -> str"
    assert data["cell_one"]["MyClass"]["methods"]["do_it"]["implementation"] == "(x: int) -> str"


def test_contract_single_cell_routine(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ROUTINE_CODEMANIFEST)
    (cell / "__init__.py").write_text(ROUTINE_IMPL, encoding="utf-8")
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path), _sys_path(str(tmp_path)):
        result = _run_contract("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data
    assert "my_func" in data["cell_one"]
    assert data["cell_one"]["my_func"]["signature"]["codemanifest"] == "(x: int) -> int"
    assert data["cell_one"]["my_func"]["signature"]["implementation"] == "(x: int) -> int"


def test_contract_multiple_cells(tmp_path) -> None:
    cell_a = tmp_path / "cell_a"
    cell_a.mkdir()
    _write_codemanifest(cell_a, ENTITY_CODEMANIFEST)
    (cell_a / "__init__.py").write_text(ENTITY_IMPL, encoding="utf-8")

    cell_b = tmp_path / "cell_b"
    cell_b.mkdir()
    _write_codemanifest(cell_b, ROUTINE_CODEMANIFEST)
    (cell_b / "__init__.py").write_text(ROUTINE_IMPL, encoding="utf-8")
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path), _sys_path(str(tmp_path)):
        result = _run_contract("cell_a", "cell_b")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_a" in data
    assert "cell_b" in data
    assert "MyClass" in data["cell_a"]
    assert "my_func" in data["cell_b"]


def test_contract_cell_not_found(tmp_path) -> None:
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path):
        result = _run_contract("nonexistent/path")

    assert result.exit_code == 1
    assert "document not found" in result.stderr.lower()


def test_contract_package_not_importable(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    # No __init__.py — tree-sitter returns empty contracts, implementations are null
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path):
        result = _run_contract("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    cell_data = data.get("cell_one", {})
    assert cell_data["MyClass"]["signature"]["implementation"] is None


def test_contract_entity_missing_in_implementation(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text("class OtherClass:\n    pass\n\n__all__ = ['OtherClass']\n", encoding="utf-8")
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path), _sys_path(str(tmp_path)):
        result = _run_contract("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data
    assert "MyClass" in data["cell_one"]
    assert data["cell_one"]["MyClass"]["signature"]["codemanifest"] == "()"
    assert data["cell_one"]["MyClass"]["signature"]["implementation"] is None
    assert data["cell_one"]["MyClass"]["properties"]["name"]["implementation"] is None
    assert data["cell_one"]["MyClass"]["methods"]["do_it"]["implementation"] is None


def test_contract_property_method_missing_in_implementation(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text("class MyClass:\n    pass\n\n__all__ = ['MyClass']\n", encoding="utf-8")
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path), _sys_path(str(tmp_path)):
        result = _run_contract("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    my_class = data["cell_one"]["MyClass"]
    assert my_class["properties"]["name"]["codemanifest"] == "str"
    assert my_class["properties"]["name"]["implementation"] is None
    assert my_class["methods"]["do_it"]["codemanifest"] == "(x: int) -> str"
    assert my_class["methods"]["do_it"]["implementation"] is None


def test_contract_routine_missing_in_implementation(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ROUTINE_CODEMANIFEST)
    (cell / "__init__.py").write_text(
        "def other_func() -> int:\n    return 0\n\n__all__ = ['other_func']\n", encoding="utf-8"
    )
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path), _sys_path(str(tmp_path)):
        result = _run_contract("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data
    assert "my_func" in data["cell_one"]
    assert data["cell_one"]["my_func"]["signature"]["codemanifest"] == "(x: int) -> int"
    assert data["cell_one"]["my_func"]["signature"]["implementation"] is None


def test_contract_signature_mismatch(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text(
        "class MyClass:\n"
        "    def __init__(self, x: int):\n"
        "        self._x = x\n"
        "    @property\n"
        "    def name(self) -> int:\n"
        "        return self._x\n"
        "    def do_it(self) -> str:\n"
        "        return ''\n"
        "\n"
        "__all__ = ['MyClass']\n",
        encoding="utf-8",
    )
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path), _sys_path(str(tmp_path)):
        result = _run_contract("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    my_class = data["cell_one"]["MyClass"]
    # Entity signature mismatch: codemanifest says (), implementation says (x: int)
    assert my_class["signature"]["codemanifest"] == "()"
    assert my_class["signature"]["implementation"] == "(x: int)"
    # Property type mismatch: codemanifest says str, implementation says int
    assert my_class["properties"]["name"]["codemanifest"] == "str"
    assert my_class["properties"]["name"]["implementation"] == "int"
    # Method signature mismatch: codemanifest says (x: int) -> str, implementation says () -> str
    assert my_class["methods"]["do_it"]["codemanifest"] == "(x: int) -> str"
    assert my_class["methods"]["do_it"]["implementation"] == "() -> str"


def test_contract_extra_in_implementation_ignored(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text(
        ENTITY_IMPL + "\n" + "class ExtraClass:\n    pass\n\n__all__ = ['MyClass', 'ExtraClass']\n",
        encoding="utf-8",
    )
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path), _sys_path(str(tmp_path)):
        result = _run_contract("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data
    assert "ExtraClass" not in data["cell_one"]
    assert "MyClass" in data["cell_one"]


def test_contract_empty_cells(tmp_path) -> None:
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path):
        result = _run_contract()

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == {}


def test_contract_cell_with_empty_body(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(
        cell,
        """\
Usages: {}

Annotations: ""

---

---

Author: Test
CreatedAt: 01/01/01
Description: Empty
""",
    )
    (cell / "__init__.py").write_text("", encoding="utf-8")
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path), _sys_path(str(tmp_path)):
        result = _run_contract("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data
    assert data["cell_one"] == {}


def test_contract_lang_from_config(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text(ENTITY_IMPL, encoding="utf-8")
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path), _sys_path(str(tmp_path)):
        result = _run_contract("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data


def test_contract_lang_cli_overrides_config(tmp_path) -> None:
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text("language: go\nbuild:\n  task_executor:\n    agent: claude\n")
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text(ENTITY_IMPL, encoding="utf-8")

    with _cwd(tmp_path), _sys_path(str(tmp_path)):
        result = _run_contract("cell_one", "--lang", "python")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data


def test_contract_config_missing(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text(ENTITY_IMPL, encoding="utf-8")

    with _cwd(tmp_path):
        result = _run_contract("cell_one")

    assert result.exit_code != 0
    assert ".goga/config.yml" in result.output.lower() or ".goga/config.yml" in result.stderr.lower()


def test_contract_config_invalid_language(tmp_path) -> None:
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text('language: ""\nbuild:\n  task_executor:\n    agent: claude\n')
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text(ENTITY_IMPL, encoding="utf-8")

    with _cwd(tmp_path):
        result = _run_contract("cell_one")

    assert result.exit_code != 0
    assert "language" in result.output.lower() or "language" in result.stderr.lower()


# --- Integration tests ---


class TestContractIntegration:
    def test_contract_cli_registered_in_app(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["contract", "--help"])
        assert result.exit_code == 0
        assert "contract" in result.output.lower()
        assert "codemanifest" in result.output.lower()

    def test_contract_output_is_only_json(self, tmp_path) -> None:
        cell = tmp_path / "cell_one"
        cell.mkdir()
        _write_codemanifest(cell, ENTITY_CODEMANIFEST)
        (cell / "__init__.py").write_text(ENTITY_IMPL, encoding="utf-8")
        _write_goga_yml(tmp_path)

        with _cwd(tmp_path), _sys_path(str(tmp_path)):
            result = _run_contract("cell_one")

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "cell_one" in data

    def test_contract_help_describes_output_structure(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["contract", "--help"])
        assert result.exit_code == 0
        output = result.output
        assert "json" in output.lower()
        assert "cells" in output.lower()
        assert "--lang" in output
        assert "exit codes" in output.lower()
        assert "implementation" in output.lower()

    def test_contract_help_mentions_entity_and_routine_format(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["contract", "--help"])
        assert result.exit_code == 0
        output = result.output
        assert "signature" in output.lower()
        assert "properties" in output.lower() or "property" in output.lower()
        assert "methods" in output.lower() or "method" in output.lower()
        assert "codemanifest" in output.lower()
        assert "entity" in output.lower()
        assert "routine" in output.lower()

    def test_contract_with_real_project_cwd(self) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent
        with _cwd(project_root):
            result = _run_contract("goga/contract")

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "goga/contract" in data


def test_contract_unknown_lang(tmp_path) -> None:
    _write_goga_yml(tmp_path)
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text(ENTITY_IMPL, encoding="utf-8")

    with _cwd(tmp_path), _sys_path(str(tmp_path)):
        result = _run_contract("cell_one", "--lang", "rust")

    assert result.exit_code == 1
    assert "unsupported language" in result.stderr.lower()


def test_contract_golang_lang_cli(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, GO_ENTITY_CODEMANIFEST)
    (cell / "service.go").write_text(
        'package cell_one\n\nfunc Hello(name string) string { return "Hello " + name }\n',
        encoding="utf-8",
    )
    _write_goga_yml(tmp_path)

    with _cwd(tmp_path):
        result = _run_contract("cell_one", "--lang", "golang")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data
    assert "Hello" in data["cell_one"]
    assert data["cell_one"]["Hello"]["signature"]["implementation"] == "(name: string) -> string"


def test_contract_default_lang_from_config_golang(tmp_path) -> None:
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text(
        "language: golang\nbuild:\n  task_executor:\n    agent: claude\n",
        encoding="utf-8",
    )
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, GO_ENTITY_CODEMANIFEST)
    (cell / "service.go").write_text(
        'package cell_one\n\nfunc Hello(name string) string { return "Hello " + name }\n',
        encoding="utf-8",
    )

    with _cwd(tmp_path):
        result = _run_contract("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data
    assert "Hello" in data["cell_one"]
    assert data["cell_one"]["Hello"]["signature"]["implementation"] == "(name: string) -> string"
