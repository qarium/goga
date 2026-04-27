from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

import click
from click.testing import CliRunner
from goga.cli import app
from goga.commands import compare
from goga.commands.compare import compare as compare_cmd

from tests.conftest import cwd as _cwd


def _run_compare(*args):
    runner = CliRunner()
    return runner.invoke(app, ["compare", *args])


def _write_codemanifest(directory: Path, content: str) -> None:
    (directory / "CODEMANIFEST").write_text(content, encoding="utf-8")


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
    def test_import_compare_from_commands(self) -> None:
        assert compare is not None

    def test_compare_is_click_command(self) -> None:
        assert isinstance(compare_cmd, click.Command)


class TestApiShape:
    def test_compare_has_callback(self) -> None:
        assert compare_cmd.callback is not None

    def test_compare_has_cells_argument(self) -> None:
        param_names = [p.name for p in compare_cmd.params]
        assert "cells" in param_names

    def test_compare_cells_has_nargs_minus_one(self) -> None:
        cells_param = next(p for p in compare_cmd.params if p.name == "cells")
        assert cells_param.nargs == -1

    def test_compare_has_lang_option(self) -> None:
        param_names = [p.name for p in compare_cmd.params]
        assert "lang" in param_names

    def test_compare_lang_default_is_python(self) -> None:
        lang_param = next(p for p in compare_cmd.params if p.name == "lang")
        assert lang_param.default == "python"


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

ROUTINE_IMPL = (
    "def my_func(x: int) -> int:\n"
    "    return x\n"
    "\n"
    "__all__ = ['my_func']\n"
)


def test_compare_single_cell_entity(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text(ENTITY_IMPL, encoding="utf-8")

    with _cwd(tmp_path):
        with _sys_path(str(tmp_path)):
            result = _run_compare("cell_one")

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


def test_compare_single_cell_routine(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ROUTINE_CODEMANIFEST)
    (cell / "__init__.py").write_text(ROUTINE_IMPL, encoding="utf-8")

    with _cwd(tmp_path):
        with _sys_path(str(tmp_path)):
            result = _run_compare("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data
    assert "my_func" in data["cell_one"]
    assert data["cell_one"]["my_func"]["signature"]["codemanifest"] == "(x: int) -> int"
    assert data["cell_one"]["my_func"]["signature"]["implementation"] == "(x: int) -> int"


def test_compare_multiple_cells(tmp_path) -> None:
    cell_a = tmp_path / "cell_a"
    cell_a.mkdir()
    _write_codemanifest(cell_a, ENTITY_CODEMANIFEST)
    (cell_a / "__init__.py").write_text(ENTITY_IMPL, encoding="utf-8")

    cell_b = tmp_path / "cell_b"
    cell_b.mkdir()
    _write_codemanifest(cell_b, ROUTINE_CODEMANIFEST)
    (cell_b / "__init__.py").write_text(ROUTINE_IMPL, encoding="utf-8")

    with _cwd(tmp_path):
        with _sys_path(str(tmp_path)):
            result = _run_compare("cell_a", "cell_b")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_a" in data
    assert "cell_b" in data
    assert "MyClass" in data["cell_a"]
    assert "my_func" in data["cell_b"]


def test_compare_cell_not_found(tmp_path) -> None:
    with _cwd(tmp_path):
        result = _run_compare("nonexistent/path")

    assert result.exit_code == 1
    assert "document not found" in result.stderr.lower()


def test_compare_package_not_importable(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    # No __init__.py — package not importable

    with _cwd(tmp_path):
        result = _run_compare("cell_one")

    assert result.exit_code == 1
    assert "not importable" in result.stderr.lower()


def test_compare_entity_missing_in_implementation(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text(
        "class OtherClass:\n    pass\n\n__all__ = ['OtherClass']\n", encoding="utf-8"
    )

    with _cwd(tmp_path):
        with _sys_path(str(tmp_path)):
            result = _run_compare("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data
    assert "MyClass" in data["cell_one"]
    assert data["cell_one"]["MyClass"]["signature"]["codemanifest"] == "()"
    assert data["cell_one"]["MyClass"]["signature"]["implementation"] is None
    assert data["cell_one"]["MyClass"]["properties"]["name"]["implementation"] is None
    assert data["cell_one"]["MyClass"]["methods"]["do_it"]["implementation"] is None


def test_compare_property_method_missing_in_implementation(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text(
        "class MyClass:\n    pass\n\n__all__ = ['MyClass']\n", encoding="utf-8"
    )

    with _cwd(tmp_path):
        with _sys_path(str(tmp_path)):
            result = _run_compare("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    my_class = data["cell_one"]["MyClass"]
    assert my_class["properties"]["name"]["codemanifest"] == "str"
    assert my_class["properties"]["name"]["implementation"] is None
    assert my_class["methods"]["do_it"]["codemanifest"] == "(x: int) -> str"
    assert my_class["methods"]["do_it"]["implementation"] is None


def test_compare_extra_in_implementation_ignored(tmp_path) -> None:
    cell = tmp_path / "cell_one"
    cell.mkdir()
    _write_codemanifest(cell, ENTITY_CODEMANIFEST)
    (cell / "__init__.py").write_text(
        ENTITY_IMPL
        + "\n"
        + "class ExtraClass:\n    pass\n\n__all__ = ['MyClass', 'ExtraClass']\n",
        encoding="utf-8",
    )

    with _cwd(tmp_path):
        with _sys_path(str(tmp_path)):
            result = _run_compare("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data
    assert "ExtraClass" not in data["cell_one"]
    assert "MyClass" in data["cell_one"]


def test_compare_empty_cells(tmp_path) -> None:
    with _cwd(tmp_path):
        result = _run_compare()

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == {}


def test_compare_cell_with_empty_body(tmp_path) -> None:
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

    with _cwd(tmp_path):
        with _sys_path(str(tmp_path)):
            result = _run_compare("cell_one")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "cell_one" in data
    assert data["cell_one"] == {}


# --- Integration tests ---


class TestCompareIntegration:
    def test_compare_cli_registered_in_app(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["compare", "--help"])
        assert result.exit_code == 0
        assert "compare" in result.output.lower()
        assert "codemanifest" in result.output.lower()

    def test_compare_output_is_only_json(self, tmp_path) -> None:
        cell = tmp_path / "cell_one"
        cell.mkdir()
        _write_codemanifest(cell, ENTITY_CODEMANIFEST)
        (cell / "__init__.py").write_text(ENTITY_IMPL, encoding="utf-8")

        with _cwd(tmp_path):
            with _sys_path(str(tmp_path)):
                result = _run_compare("cell_one")

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "cell_one" in data

    def test_compare_with_real_project_cwd(self) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        with _cwd(project_root):
            result = _run_compare("goga/contract")

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "goga/contract" in data
