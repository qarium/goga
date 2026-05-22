"""Integration tests for swift_contract via CLI, covering all CODEMANIFEST DSL structures."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from goga.cli import app

from tests.conftest import cwd as _cwd

HAS_TREE_SITTER = importlib.util.find_spec("tree_sitter_swift") is not None

requires_tree_sitter = pytest.mark.skipif(
    not HAS_TREE_SITTER,
    reason="tree-sitter-swift not installed",
)


def _run_contract(*args):
    runner = CliRunner()
    return runner.invoke(app, ["contract", *args])


def _write_codemanifest(directory: Path, content: str) -> None:
    (directory / "CODEMANIFEST").write_text(content, encoding="utf-8")


def _write_goga_yml(directory: Path, lang: str = "swift") -> None:
    (directory / ".goga").mkdir(exist_ok=True)
    (directory / ".goga" / "config.yml").write_text(
        f"language: {lang}\nbuild:\n  task_executor:\n    agent: claude\n"
    )


SWIFT_FULL_CODEMANIFEST = """\
Usages: {}

Annotations: ""

---

"Server(host: String, port: Int)":
  location: Server.swift
  annotations: ""
  properties:
    "name -> String": ""
  methods:
    "start() -> Bool": ""
    "stop()": ""

"Point(x: Double, y: Double)":
  location: Point.swift
  annotations: ""
  properties:
    "x -> Double": ""
    "y -> Double": ""

"Worker()":
  location: Worker.swift
  annotations: ""
  methods:
    "process()": ""

"Handler()":
  location: Handler.swift
  annotations: ""
  methods:
    "process(data: String) -> Bool": ""
    "cleanup()": ""

"greet(name: String) -> String":
  location: Utils.swift
  annotations: ""

---

Author: Test
CreatedAt: 01/01/01
Description: Test
"""

SWIFT_FULL_SERVER_SWIFT = """\
public class Server {
    public var name: String = ""
    public init(host: String, port: Int) {}
    public func start() -> Bool { return true }
    public func stop() {}
}
"""

SWIFT_FULL_POINT_SWIFT = """\
public struct Point {
    public var x: Double = 0
    public var y: Double = 0
    public init(x: Double, y: Double) {}
}
"""

SWIFT_FULL_WORKER_SWIFT = """\
public actor Worker {
    public func process() {}
}
"""

SWIFT_FULL_HANDLER_SWIFT = """\
public protocol Handler {
    func process(data: String) -> Bool
    func cleanup()
}
"""

SWIFT_FULL_UTILS_SWIFT = """\
public func greet(name: String) -> String { return name }
"""


@requires_tree_sitter
class TestFullCycleSwiftPackageViaCLI:
    """End-to-end: Swift module with class, struct, actor, protocol, function through CLI.

    Covers CODEMANIFEST DSL structures for Swift:
    - Entity (public class) with init -> signature, properties, methods
    - Entity (public struct) with init -> signature, properties
    - Entity (public actor) with methods
    - Entity (public protocol) with methods only, no properties
    - Routine (public func) with signature
    """

    def test_full_cycle_all_swift_structures(self, tmp_path) -> None:
        cell = tmp_path / "swift_cell"
        cell.mkdir()
        _write_codemanifest(cell, SWIFT_FULL_CODEMANIFEST)
        (cell / "Server.swift").write_text(SWIFT_FULL_SERVER_SWIFT, encoding="utf-8")
        (cell / "Point.swift").write_text(SWIFT_FULL_POINT_SWIFT, encoding="utf-8")
        (cell / "Worker.swift").write_text(SWIFT_FULL_WORKER_SWIFT, encoding="utf-8")
        (cell / "Handler.swift").write_text(SWIFT_FULL_HANDLER_SWIFT, encoding="utf-8")
        (cell / "Utils.swift").write_text(SWIFT_FULL_UTILS_SWIFT, encoding="utf-8")
        _write_goga_yml(tmp_path)

        with _cwd(tmp_path):
            result = _run_contract("swift_cell", "--lang", "swift")

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        data = json.loads(result.output)
        assert "swift_cell" in data

        cell_data = data["swift_cell"]

        # Server — public class with init -> signature, property, methods
        assert "Server" in cell_data
        server = cell_data["Server"]
        assert server["signature"]["codemanifest"] == "(host: String, port: Int)"
        assert server["signature"]["implementation"] == "(host: String, port: Int)"

        assert "name" in server["properties"]
        assert server["properties"]["name"]["codemanifest"] == "String"
        assert server["properties"]["name"]["implementation"] == "String"

        assert "start" in server["methods"]
        assert server["methods"]["start"]["codemanifest"] == "() -> Bool"
        assert server["methods"]["start"]["implementation"] == "() -> Bool"
        assert "stop" in server["methods"]
        assert server["methods"]["stop"]["codemanifest"] == "()"
        assert server["methods"]["stop"]["implementation"] == "()"

        # Point — public struct with init -> signature and properties
        assert "Point" in cell_data
        point = cell_data["Point"]
        assert point["signature"]["codemanifest"] == "(x: Double, y: Double)"
        assert point["signature"]["implementation"] == "(x: Double, y: Double)"

        assert "x" in point["properties"]
        assert point["properties"]["x"]["codemanifest"] == "Double"
        assert point["properties"]["x"]["implementation"] == "Double"
        assert "y" in point["properties"]
        assert point["properties"]["y"]["codemanifest"] == "Double"
        assert point["properties"]["y"]["implementation"] == "Double"

        # Worker — public actor with method
        assert "Worker" in cell_data
        worker = cell_data["Worker"]
        assert worker["signature"]["codemanifest"] == "()"
        assert worker["signature"]["implementation"] == "()"

        assert "process" in worker["methods"]
        assert worker["methods"]["process"]["codemanifest"] == "()"
        assert worker["methods"]["process"]["implementation"] == "()"

        # Handler — public protocol with methods only (no properties)
        assert "Handler" in cell_data
        handler = cell_data["Handler"]
        assert handler["signature"]["codemanifest"] == "()"
        assert handler["signature"]["implementation"] == "()"

        assert "process" in handler["methods"]
        assert handler["methods"]["process"]["codemanifest"] == "(data: String) -> Bool"
        assert handler["methods"]["process"]["implementation"] == "(data: String) -> Bool"
        assert "cleanup" in handler["methods"]
        assert handler["methods"]["cleanup"]["codemanifest"] == "()"
        assert handler["methods"]["cleanup"]["implementation"] == "()"

        # greet — public func (Routine)
        assert "greet" in cell_data
        assert cell_data["greet"]["signature"]["codemanifest"] == "(name: String) -> String"
        assert cell_data["greet"]["signature"]["implementation"] == "(name: String) -> String"
