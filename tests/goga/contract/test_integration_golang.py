"""Integration tests for multi-lang contract: golang_contract + facade + dispatch + CLI."""

from __future__ import annotations

import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from click.testing import CliRunner
from goga.cli import app

from tests.conftest import cwd as _cwd

HAS_TREE_SITTER = importlib.util.find_spec("tree_sitter_go") is not None

requires_tree_sitter = pytest.mark.skipif(
    not HAS_TREE_SITTER,
    reason="tree-sitter not installed",
)


def _run_contract(*args):
    runner = CliRunner()
    return runner.invoke(app, ["contract", *args])


def _write_codemanifest(directory: Path, content: str) -> None:
    (directory / "CODEMANIFEST").write_text(content, encoding="utf-8")


def _write_goga_yml(directory: Path, lang: str = "golang") -> None:
    (directory / ".goga").mkdir(exist_ok=True)
    (directory / ".goga" / "config.yml").write_text(
        f"language: {lang}\nbuild:\n  task_executor:\n    agent: claude\n"
    )


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


GO_FULL_CODEMANIFEST = """\
Usages: {}

Annotations: ""

---

"Server()":
  location: server.go
  annotations: ""
  properties:
    "Name -> string": ""
    "Port -> int": ""
  methods:
    "Start() -> error": ""
    "Stop()": ""

"Handler()":
  location: api.go
  annotations: ""
  methods:
    "Serve(data: string) -> error": ""
    "Close()": ""

"Create(name: string) -> error":
  location: service.go
  annotations: ""

---

Author: Test
CreatedAt: 01/01/01
Description: Test
"""

GO_FULL_SERVER_GO = """\
package cell

type Server struct {
\tName string
\tPort int
}
"""

GO_FULL_METHODS_GO = """\
package cell

func (s *Server) Start() error {
\treturn nil
}

func (s *Server) Stop() {
}
"""

GO_FULL_API_GO = """\
package cell

type Handler interface {
\tServe(data string) error
\tClose()
}
"""

GO_FULL_SERVICE_GO = """\
package cell

func Create(name string) error {
\treturn nil
}
"""


@requires_tree_sitter
class TestFullCycleGoPackageViaCLI:
    """End-to-end: Go package with struct, interface, function through CLI."""

    def test_full_cycle_struct_interface_function(self, tmp_path) -> None:
        cell = tmp_path / "cell_one"
        cell.mkdir()
        _write_codemanifest(cell, GO_FULL_CODEMANIFEST)
        (cell / "server.go").write_text(GO_FULL_SERVER_GO, encoding="utf-8")
        (cell / "methods.go").write_text(GO_FULL_METHODS_GO, encoding="utf-8")
        (cell / "api.go").write_text(GO_FULL_API_GO, encoding="utf-8")
        (cell / "service.go").write_text(GO_FULL_SERVICE_GO, encoding="utf-8")
        _write_goga_yml(tmp_path)

        with _cwd(tmp_path):
            result = _run_contract("cell_one", "--lang", "golang")

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        data = json.loads(result.output)
        assert "cell_one" in data

        cell_data = data["cell_one"]

        assert "Server" in cell_data
        server = cell_data["Server"]
        assert server["signature"]["codemanifest"] == "()"
        assert server["signature"]["implementation"] == ""
        assert "Name" in server["properties"]
        assert server["properties"]["Name"]["codemanifest"] == "string"
        assert server["properties"]["Name"]["implementation"] == "string"
        assert "Port" in server["properties"]
        assert server["properties"]["Port"]["codemanifest"] == "int"
        assert server["properties"]["Port"]["implementation"] == "int"
        assert "Start" in server["methods"]
        assert server["methods"]["Start"]["codemanifest"] == "() -> error"
        assert server["methods"]["Start"]["implementation"] == "() -> error"
        assert "Stop" in server["methods"]
        assert server["methods"]["Stop"]["codemanifest"] == "()"
        assert server["methods"]["Stop"]["implementation"] == "()"

        assert "Handler" in cell_data
        handler = cell_data["Handler"]
        assert handler["signature"]["codemanifest"] == "()"
        assert handler["signature"]["implementation"] == ""
        assert "Serve" in handler["methods"]
        assert handler["methods"]["Serve"]["codemanifest"] == "(data: string) -> error"
        assert handler["methods"]["Serve"]["implementation"] == "(data: string) -> error"
        assert "Close" in handler["methods"]
        assert handler["methods"]["Close"]["codemanifest"] == "()"
        assert handler["methods"]["Close"]["implementation"] == "()"

        assert "Create" in cell_data
        assert cell_data["Create"]["signature"]["codemanifest"] == "(name: string) -> error"
        assert cell_data["Create"]["signature"]["implementation"] == "(name: string) -> error"


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


@requires_tree_sitter
class TestMixedPythonAndGoProject:
    """Mixed project: Python and Go cells processed with different --lang flags."""

    def test_go_cell_with_golang_and_python_cell_with_python(self, tmp_path) -> None:
        go_cell = tmp_path / "go_cell"
        go_cell.mkdir()
        _write_codemanifest(
            go_cell,
            GO_FULL_CODEMANIFEST,
        )
        (go_cell / "server.go").write_text(GO_FULL_SERVER_GO, encoding="utf-8")
        (go_cell / "methods.go").write_text(GO_FULL_METHODS_GO, encoding="utf-8")
        (go_cell / "api.go").write_text(GO_FULL_API_GO, encoding="utf-8")
        (go_cell / "service.go").write_text(GO_FULL_SERVICE_GO, encoding="utf-8")

        py_cell = tmp_path / "py_cell"
        py_cell.mkdir()
        _write_codemanifest(py_cell, ENTITY_CODEMANIFEST)
        (py_cell / "__init__.py").write_text(ENTITY_IMPL, encoding="utf-8")

        _write_goga_yml(tmp_path, lang="golang")

        with _cwd(tmp_path):
            go_result = _run_contract("go_cell", "--lang", "golang")
        assert go_result.exit_code == 0
        go_data = json.loads(go_result.output)
        assert "go_cell" in go_data
        assert "Server" in go_data["go_cell"]
        assert "Handler" in go_data["go_cell"]
        assert "Create" in go_data["go_cell"]

        _write_goga_yml(tmp_path, lang="python")
        with _cwd(tmp_path), _sys_path(str(tmp_path)):
            py_result = _run_contract("py_cell", "--lang", "python")
        assert py_result.exit_code == 0
        py_data = json.loads(py_result.output)
        assert "py_cell" in py_data
        assert "MyClass" in py_data["py_cell"]
