"""Integration tests for kotlin_contract via CLI, covering all CODEMANIFEST DSL structures."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from goga.cli import app

from tests.conftest import cwd as _cwd

HAS_TREE_SITTER = importlib.util.find_spec("tree_sitter_kotlin") is not None

requires_tree_sitter = pytest.mark.skipif(
    not HAS_TREE_SITTER,
    reason="tree-sitter-kotlin not installed",
)


def _run_contract(*args):
    runner = CliRunner()
    return runner.invoke(app, ["contract", *args])


def _write_codemanifest(directory: Path, content: str) -> None:
    (directory / "CODEMANIFEST").write_text(content, encoding="utf-8")


def _write_goga_yml(directory: Path, lang: str = "kotlin") -> None:
    (directory / ".goga").mkdir(exist_ok=True)
    (directory / ".goga" / "config.yml").write_text(
        f"language: {lang}\nbuild:\n  task_executor:\n    agent: claude\npipeline:\n  agent: claude\n"
    )


KT_FULL_CODEMANIFEST = """\
Usages: {}

Annotations: ""

---

"UserService(name: String)":
  location: UserService.kt
  annotations: ""
  methods:
    "greet() -> String": ""

"Repository()":
  location: Repository.kt
  annotations: ""
  methods:
    "save(data: String)": ""
    "load(id: String) -> String?": ""

"Config()":
  location: Config.kt
  annotations: ""
  properties:
    "host -> String": ""
  methods:
    "load() -> Config": ""

"formatName(firstName: String, lastName: String) -> String":
  location: Utils.kt
  annotations: ""

---

Author: Test
CreatedAt: 01/01/01
Description: Test
"""

KT_FULL_USER_SERVICE_KT = """\
class UserService(val name: String) {
    fun greet(): String = "Hello $name"
}
"""

KT_FULL_REPOSITORY_KT = """\
interface Repository {
    fun save(data: String)
    fun load(id: String): String?
}
"""

KT_FULL_CONFIG_KT = """\
object Config {
    val host: String = "localhost"
    fun load(): Config = this
}
"""

KT_FULL_UTILS_KT = """\
fun formatName(firstName: String, lastName: String): String = "$firstName $lastName"
"""


@requires_tree_sitter
class TestFullCycleKotlinPackageViaCLI:
    """End-to-end: Kotlin package with class, interface, object, function through CLI.

    Covers CODEMANIFEST DSL structures for Kotlin:
    - Entity (class) with constructor params -> signature + methods
    - Entity (interface) with methods only
    - Entity (object) with properties + methods
    - Routine (top-level function) with signature
    """

    def test_full_cycle_all_kotlin_structures(self, tmp_path) -> None:
        cell = tmp_path / "kt_cell"
        cell.mkdir()
        _write_codemanifest(cell, KT_FULL_CODEMANIFEST)
        (cell / "UserService.kt").write_text(KT_FULL_USER_SERVICE_KT, encoding="utf-8")
        (cell / "Repository.kt").write_text(KT_FULL_REPOSITORY_KT, encoding="utf-8")
        (cell / "Config.kt").write_text(KT_FULL_CONFIG_KT, encoding="utf-8")
        (cell / "Utils.kt").write_text(KT_FULL_UTILS_KT, encoding="utf-8")
        _write_goga_yml(tmp_path)

        with _cwd(tmp_path):
            result = _run_contract("kt_cell", "--lang", "kotlin")

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        data = json.loads(result.output)
        assert "kt_cell" in data

        cell_data = data["kt_cell"]

        # UserService — class with constructor params -> signature and method
        assert "UserService" in cell_data
        user_svc = cell_data["UserService"]
        assert user_svc["signature"]["codemanifest"] == "(name: String)"
        assert user_svc["signature"]["implementation"] == "(name: String)"
        assert "greet" in user_svc["methods"]
        assert user_svc["methods"]["greet"]["codemanifest"] == "() -> String"
        assert user_svc["methods"]["greet"]["implementation"] == "() -> String"

        # Repository — interface with methods
        assert "Repository" in cell_data
        repo = cell_data["Repository"]
        assert repo["signature"]["codemanifest"] == "()"
        assert repo["signature"]["implementation"] == "()"
        assert "save" in repo["methods"]
        assert repo["methods"]["save"]["codemanifest"] == "(data: String)"
        assert repo["methods"]["save"]["implementation"] == "(data: String)"
        assert "load" in repo["methods"]
        assert repo["methods"]["load"]["codemanifest"] == "(id: String) -> String?"
        assert repo["methods"]["load"]["implementation"] == "(id: String) -> String?"

        # Config — object declaration with properties and methods
        assert "Config" in cell_data
        config = cell_data["Config"]
        assert config["signature"]["codemanifest"] == "()"
        assert config["signature"]["implementation"] == "()"
        assert "host" in config["properties"]
        assert config["properties"]["host"]["codemanifest"] == "String"
        assert config["properties"]["host"]["implementation"] == "String"
        assert "load" in config["methods"]
        assert config["methods"]["load"]["codemanifest"] == "() -> Config"
        assert config["methods"]["load"]["implementation"] == "() -> Config"

        # formatName — top-level function (Routine)
        assert "formatName" in cell_data
        assert cell_data["formatName"]["signature"]["codemanifest"] == "(firstName: String, lastName: String) -> String"
        assert (
            cell_data["formatName"]["signature"]["implementation"] == "(firstName: String, lastName: String) -> String"
        )
