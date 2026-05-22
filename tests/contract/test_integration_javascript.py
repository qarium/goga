"""Integration tests for javascript_contract via dispatcher, covering multi-feature scenarios."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from goga.cli import app
from goga.contract import EntityContract, RoutineContract
from goga.contract.dispatcher import contract

from tests.conftest import cwd as _cwd

HAS_TREE_SITTER = importlib.util.find_spec("tree_sitter_javascript") is not None

requires_tree_sitter = pytest.mark.skipif(
    not HAS_TREE_SITTER,
    reason="tree-sitter-javascript not installed",
)


@requires_tree_sitter
class TestFullCycleDispatcher:
    """End-to-end: contract('javascript', path) with class + function through dispatcher."""

    def test_full_cycle_class_and_function(self, tmp_path) -> None:
        (tmp_path / "index.js").write_text(
            "/**\n"
            " * @param {string} host\n"
            " * @returns {void}\n"
            " */\n"
            "export function start(host) {}\n"
            "\n"
            "/**\n"
            " * @param {number} code\n"
            " * @returns {boolean}\n"
            " */\n"
            "export function stop(code) {}\n"
            "\n"
            "export class App {\n"
            "  constructor(name) {}\n"
            "  /**\n"
            "   * @param {string} route\n"
            "   * @returns {number}\n"
            "   */\n"
            "  handle(route) {}\n"
            "  shutdown() {}\n"
            "}\n",
            encoding="utf-8",
        )

        result = contract("javascript", str(tmp_path))

        # Result is sorted by name: App (entity) before start/stop (routines)
        assert len(result) == 3
        names = [r.name for r in result]
        assert names == ["App", "start", "stop"]

        # App entity
        app = next(r for r in result if r.name == "App")
        assert isinstance(app, EntityContract)
        assert app.signature == "()"
        assert len(app.methods) == 3
        method_names = [m.name for m in app.methods]
        assert "constructor" in method_names
        assert "handle" in method_names
        assert "shutdown" in method_names
        handle = next(m for m in app.methods if m.name == "handle")
        assert "route: string" in handle.signature
        assert "-> number" in handle.signature

        # start routine
        start = next(r for r in result if r.name == "start")
        assert isinstance(start, RoutineContract)
        assert "host: string" in start.signature
        assert "-> void" in start.signature

        # stop routine
        stop = next(r for r in result if r.name == "stop")
        assert isinstance(stop, RoutineContract)
        assert "code: number" in stop.signature
        assert "-> boolean" in stop.signature


@requires_tree_sitter
class TestMixedEsmAndCommonjs:
    """Mixed ESM + CommonJS module: ESM exports extracted, indirect CommonJS skipped."""

    def test_esm_exported_commonjs_fallback_skipped(self, tmp_path) -> None:
        (tmp_path / "index.js").write_text(
            "export function main() {}\n"
            "export function helper() {}\n"
            "module.exports.fallback = function() {};\n",
            encoding="utf-8",
        )

        result = contract("javascript", str(tmp_path))

        names = [r.name for r in result]
        assert "main" in names
        assert "helper" in names
        assert "fallback" not in names
        assert len(result) == 2

    def test_commonjs_object_export_with_esm(self, tmp_path) -> None:
        (tmp_path / "index.js").write_text(
            "export function namedFn() {}\n"
            "module.exports = {\n"
            "  create(name) {},\n"
            "  destroy() {},\n"
            "};\n",
            encoding="utf-8",
        )

        result = contract("javascript", str(tmp_path))

        names = [r.name for r in result]
        assert "namedFn" in names
        assert "create" in names
        assert "destroy" in names
        assert len(result) == 3


@requires_tree_sitter
class TestClassWithFieldsAndMethodsAndJsdoc:
    """Class with fields, methods, and JSDoc annotations → full EntityContract."""

    def test_class_with_all_features(self, tmp_path) -> None:
        (tmp_path / "index.js").write_text(
            "/**\n"
            " * Database connection wrapper.\n"
            " */\n"
            "export class Database {\n"
            "  /** @type {string} */\n"
            "  host;\n"
            "\n"
            "  /** @type {number} */\n"
            "  port;\n"
            "\n"
            "  /** @type {boolean} */\n"
            "  connected;\n"
            "\n"
            "  constructor(host, port) {}\n"
            "\n"
            "  /**\n"
            "   * @param {string} query\n"
            "   * @returns {Array} rows\n"
            "   */\n"
            "  query(query) {}\n"
            "\n"
            "  /**\n"
            "   * @returns {void}\n"
            "   */\n"
            "  close() {}\n"
            "}\n",
            encoding="utf-8",
        )

        result = contract("javascript", str(tmp_path))
        assert len(result) == 1
        entity = result[0]
        assert isinstance(entity, EntityContract)
        assert entity.name == "Database"
        assert entity.signature == "()"

        # Properties from field definitions
        assert len(entity.properties) == 3
        prop_map = {p.name: p.signature for p in entity.properties}
        assert prop_map["host"] == "string"
        assert prop_map["port"] == "number"
        assert prop_map["connected"] == "boolean"

        # Methods
        method_names = [m.name for m in entity.methods]
        assert "constructor" in method_names
        assert "query" in method_names
        assert "close" in method_names

        query = next(m for m in entity.methods if m.name == "query")
        assert "query: string" in query.signature
        assert "-> Array" in query.signature

        close = next(m for m in entity.methods if m.name == "close")
        assert "-> void" in close.signature


@requires_tree_sitter
class TestMultipleClassesAndFunctions:
    """Multiple classes and functions — stable sorted order and completeness."""

    def test_multiple_exports_sorted_and_complete(self, tmp_path) -> None:
        (tmp_path / "index.js").write_text(
            "export function zeta() {}\n"
            "export class Alpha {\n"
            "  run() {}\n"
            "}\n"
            "export function beta() {}\n"
            "export class Gamma {\n"
            "  process() {}\n"
            "  finalize() {}\n"
            "}\n"
            "export function delta() {}\n",
            encoding="utf-8",
        )

        result = contract("javascript", str(tmp_path))

        # All 5 exports present
        assert len(result) == 5

        # Entities sorted first, then routines sorted: Alpha, Gamma, beta, delta, zeta
        names = [r.name for r in result]
        assert names == ["Alpha", "Gamma", "beta", "delta", "zeta"]

        # Alpha entity
        alpha = result[0]
        assert isinstance(alpha, EntityContract)
        assert len(alpha.methods) == 1
        assert alpha.methods[0].name == "run"

        # Gamma entity
        gamma = result[1]
        assert isinstance(gamma, EntityContract)
        assert len(gamma.methods) == 2
        gamma_method_names = [m.name for m in gamma.methods]
        assert "process" in gamma_method_names
        assert "finalize" in gamma_method_names

        # Routines
        beta = result[2]
        assert isinstance(beta, RoutineContract)
        assert beta.name == "beta"

        delta = result[3]
        assert isinstance(delta, RoutineContract)

        zeta = result[4]
        assert isinstance(zeta, RoutineContract)

        # Call twice — stable order
        result2 = contract("javascript", str(tmp_path))
        names2 = [r.name for r in result2]
        assert names == names2


@requires_tree_sitter
class TestExportDefaultAndNamedExports:
    """export default + named exports in one file — both extracted correctly."""

    def test_default_class_with_named_exports(self, tmp_path) -> None:
        (tmp_path / "index.js").write_text(
            "export function utility() {}\n"
            "export default class {\n"
            "  constructor(config) {}\n"
            "  init() {}\n"
            "}\n"
            "export function helper(x) {}\n",
            encoding="utf-8",
        )

        result = contract("javascript", str(tmp_path))

        # Sorted: default (entity), helper (routine), utility (routine)
        assert len(result) == 3
        names = [r.name for r in result]
        assert names == ["default", "helper", "utility"]

        # default entity
        default = result[0]
        assert isinstance(default, EntityContract)
        assert default.name == "default"
        assert default.signature == "()"
        method_names = [m.name for m in default.methods]
        assert "constructor" in method_names
        assert "init" in method_names

        # named routines
        helper = next(r for r in result if r.name == "helper")
        assert isinstance(helper, RoutineContract)
        assert "x" in helper.signature

        utility = next(r for r in result if r.name == "utility")
        assert isinstance(utility, RoutineContract)

    def test_default_function_with_named_exports(self, tmp_path) -> None:
        (tmp_path / "index.js").write_text(
            "export default function() {}\n"
            "export function namedOne(a) {}\n"
            "export function namedTwo(b, c) {}\n",
            encoding="utf-8",
        )

        result = contract("javascript", str(tmp_path))

        assert len(result) == 3
        names = [r.name for r in result]
        assert names == ["default", "namedOne", "namedTwo"]

        default = result[0]
        assert isinstance(default, RoutineContract)
        assert default.name == "default"

        named_one = next(r for r in result if r.name == "namedOne")
        assert isinstance(named_one, RoutineContract)
        assert "a" in named_one.signature


# === CLI-based integration tests ===


def _run_contract(*args):
    runner = CliRunner()
    return runner.invoke(app, ["contract", *args])


def _write_codemanifest(directory: Path, content: str) -> None:
    (directory / "CODEMANIFEST").write_text(content, encoding="utf-8")


def _write_goga_yml(directory: Path, lang: str = "javascript") -> None:
    (directory / ".goga").mkdir(exist_ok=True)
    (directory / ".goga" / "config.yml").write_text(
        f"language: {lang}\nbuild:\n  task_executor:\n    agent: claude\n"
    )


JS_FULL_CODEMANIFEST = """\
Usages: {}

Annotations: ""

---

"Database()":
  location: index.js
  annotations: ""
  properties:
    "host -> string": ""
    "port -> number": ""
  methods:
    "constructor(host: string, port: number)": ""
    "query(sql: string) -> Array": ""
    "close() -> void": ""

"App()":
  location: index.js
  annotations: ""
  methods:
    "constructor(name)": ""
    "handle(route: string) -> number": ""
    "shutdown()": ""

"start(host: string) -> void":
  location: index.js
  annotations: ""

---

Author: Test
CreatedAt: 01/01/01
Description: Test
"""

JS_FULL_INDEX_JS = """\
/**
 * @param {string} host
 * @returns {void}
 */
export function start(host) {}

export class Database {
  /** @type {string} */
  host;

  /** @type {number} */
  port;

  /**
   * @param {string} host
   * @param {number} port
   */
  constructor(host, port) {}

  /**
   * @param {string} sql
   * @returns {Array} rows
   */
  query(sql) {}

  /**
   * @returns {void}
   */
  close() {}
}

export class App {
  constructor(name) {}

  /**
   * @param {string} route
   * @returns {number}
   */
  handle(route) {}

  shutdown() {}
}
"""


@requires_tree_sitter
class TestFullCycleJsPackageViaCLI:
    """End-to-end: JS module with class (properties + methods) + function through CLI."""

    def test_full_cycle_entity_properties_methods_and_routine(self, tmp_path) -> None:
        cell = tmp_path / "js_cell"
        cell.mkdir()
        _write_codemanifest(cell, JS_FULL_CODEMANIFEST)
        (cell / "index.js").write_text(JS_FULL_INDEX_JS, encoding="utf-8")
        _write_goga_yml(tmp_path)

        with _cwd(tmp_path):
            result = _run_contract("js_cell", "--lang", "javascript")

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        data = json.loads(result.output)
        assert "js_cell" in data

        cell_data = data["js_cell"]

        # Database — Entity with properties and methods
        assert "Database" in cell_data
        db = cell_data["Database"]
        assert db["signature"]["codemanifest"] == "()"
        assert db["signature"]["implementation"] == "()"

        assert "host" in db["properties"]
        assert db["properties"]["host"]["codemanifest"] == "string"
        assert db["properties"]["host"]["implementation"] == "string"
        assert "port" in db["properties"]
        assert db["properties"]["port"]["codemanifest"] == "number"
        assert db["properties"]["port"]["implementation"] == "number"

        assert "constructor" in db["methods"]
        assert db["methods"]["constructor"]["codemanifest"] == "(host: string, port: number)"
        assert db["methods"]["constructor"]["implementation"] == "(host: string, port: number)"
        assert "query" in db["methods"]
        assert db["methods"]["query"]["codemanifest"] == "(sql: string) -> Array"
        assert db["methods"]["query"]["implementation"] == "(sql: string) -> Array"
        assert "close" in db["methods"]
        assert db["methods"]["close"]["codemanifest"] == "() -> void"
        assert db["methods"]["close"]["implementation"] == "() -> void"

        # App — Entity with methods only (no JSDoc on constructor)
        assert "App" in cell_data
        app_data = cell_data["App"]
        assert app_data["signature"]["codemanifest"] == "()"
        assert app_data["signature"]["implementation"] == "()"

        assert "constructor" in app_data["methods"]
        assert app_data["methods"]["constructor"]["codemanifest"] == "(name)"
        assert app_data["methods"]["constructor"]["implementation"] == "(name)"
        assert "handle" in app_data["methods"]
        assert app_data["methods"]["handle"]["codemanifest"] == "(route: string) -> number"
        assert app_data["methods"]["handle"]["implementation"] == "(route: string) -> number"
        assert "shutdown" in app_data["methods"]
        assert app_data["methods"]["shutdown"]["codemanifest"] == "()"
        assert app_data["methods"]["shutdown"]["implementation"] == "()"

        # start — Routine
        assert "start" in cell_data
        assert cell_data["start"]["signature"]["codemanifest"] == "(host: string) -> void"
        assert cell_data["start"]["signature"]["implementation"] == "(host: string) -> void"
