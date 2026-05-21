"""Contract and behavioral tests for contract() dispatcher."""

import inspect
import sys
from pathlib import Path

import pytest
from goga.contract import contract
from goga.contract.data import EntityContract, RoutineContract

# ── Contract tests ──────────────────────────────────────────


def test_contract_importable_from_facade():
    """contract is importable from goga.contract facade."""
    from goga.contract import contract as c

    assert callable(c)


def test_contract_signature():
    """contract has signature (lang: str, cell_path: str) -> list[EntityContract | RoutineContract]."""
    sig = inspect.signature(contract)
    params = list(sig.parameters.keys())
    assert params == ["lang", "cell_path"]
    assert sig.parameters["lang"].annotation in (str, "str")
    assert sig.parameters["cell_path"].annotation in (str, "str")
    ret = sig.return_annotation
    assert ret == "list[EntityContract | RoutineContract]"


# ── Behavioral tests ────────────────────────────────────────


def test_contract_dispatches_to_python(tmp_path: Path) -> None:
    """Dispatching to python_contract returns correct EntityContract."""
    pkg_dir = tmp_path / "cell"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text(
        "class MyClass:\n"
        "    def my_method(self) -> str:\n"
        "        return ''\n"
        "\n"
        "__all__ = ['MyClass']\n"
    )
    parent = str(tmp_path)
    sys.path.insert(0, parent)
    try:
        result = contract("python", "cell")
        assert len(result) >= 1
        entities = [r for r in result if isinstance(r, EntityContract) and r.name == "MyClass"]
        assert len(entities) == 1
        methods = [m for m in entities[0].methods if m.name == "my_method"]
        assert len(methods) == 1
    finally:
        sys.path.remove(parent)
        sys.modules.pop("cell", None)


def test_contract_dispatches_to_golang(tmp_path: Path) -> None:
    """Dispatching to golang_contract returns correct RoutineContract."""
    pytest.importorskip("tree_sitter_go", reason="tree-sitter-go not installed")
    go_dir = tmp_path / "cell"
    go_dir.mkdir()
    (go_dir / "example.go").write_text(
        'package cell\n\nfunc Hello(name string) string { return "" }\n'
    )
    result = contract("golang", str(go_dir))
    routines = [r for r in result if isinstance(r, RoutineContract) and r.name == "Hello"]
    assert len(routines) >= 1


def test_javascript_contract_importable_from_facade():
    """javascript_contract is importable from goga.contract facade."""
    pytest.importorskip("tree_sitter_javascript", reason="tree-sitter-javascript not installed")
    from goga.contract import javascript_contract as jc

    assert callable(jc)


def test_contract_dispatches_to_javascript(tmp_path: Path) -> None:
    """Dispatching to javascript_contract returns correct RoutineContract."""
    pytest.importorskip("tree_sitter_javascript", reason="tree-sitter-javascript not installed")
    cell_dir = tmp_path / "cell"
    cell_dir.mkdir()
    (cell_dir / "index.js").write_text(
        "export function greet(name) { return name; }\n"
    )
    result = contract("javascript", str(cell_dir))
    routines = [r for r in result if isinstance(r, RoutineContract) and r.name == "greet"]
    assert len(routines) == 1
    assert "(name)" in routines[0].signature


def test_contract_dispatches_to_kotlin(tmp_path: Path) -> None:
    """Dispatching to kotlin_contract returns correct RoutineContract."""
    pytest.importorskip("tree_sitter_kotlin", reason="tree-sitter-kotlin not installed")
    cell_dir = tmp_path / "cell"
    cell_dir.mkdir()
    (cell_dir / "Service.kt").write_text(
        "fun hello(name: String): String = name\n"
    )
    result = contract("kotlin", str(cell_dir))
    routines = [r for r in result if isinstance(r, RoutineContract) and r.name == "hello"]
    assert len(routines) == 1
    assert "name: String" in routines[0].signature


def test_contract_dispatches_to_swift(tmp_path: Path) -> None:
    """Dispatching to swift_contract returns correct RoutineContract."""
    pytest.importorskip("tree_sitter_swift", reason="tree-sitter-swift not installed")
    cell_dir = tmp_path / "cell"
    cell_dir.mkdir()
    (cell_dir / "Utils.swift").write_text(
        "public func greet(name: String) -> String { return name }\n"
    )
    result = contract("swift", str(cell_dir))
    routines = [r for r in result if isinstance(r, RoutineContract) and r.name == "greet"]
    assert len(routines) == 1
    assert "name: String" in routines[0].signature


def test_contract_unsupported_language() -> None:
    """Unknown language raises ValueError."""
    with pytest.raises(ValueError, match="unsupported language"):
        contract("rust", "some/path")


def test_contract_empty_language() -> None:
    """Empty language string raises ValueError."""
    with pytest.raises(ValueError, match="unsupported language"):
        contract("", "some/path")


def test_contract_nonexistent_package_python(tmp_path: Path) -> None:
    """Dispatching python with a directory that has no __init__.py returns empty list."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    parent = str(tmp_path)
    sys.path.insert(0, parent)
    try:
        result = contract("python", "empty")
        assert result == []
    finally:
        sys.path.remove(parent)
        sys.modules.pop("empty", None)


# ── Integration tests ─────────────────────────────────────────


def test_dispatcher_kotlin_mixed_declarations(tmp_path: Path) -> None:
    """Dispatcher routes kotlin with mixed entities+routines in one file."""
    pytest.importorskip("tree_sitter_kotlin", reason="tree-sitter-kotlin not installed")
    cell_dir = tmp_path / "cell"
    cell_dir.mkdir()
    (cell_dir / "App.kt").write_text(
        "class UserService(val name: String) {\n"
        "    fun greet(): String = \"Hello\"\n"
        "}\n\n"
        "fun formatName(first: String, last: String): String = \"$first $last\"\n"
    )
    result = contract("kotlin", str(cell_dir))
    entities = [r for r in result if isinstance(r, EntityContract)]
    routines = [r for r in result if isinstance(r, RoutineContract)]
    assert len(entities) >= 1
    assert len(routines) >= 1
    entity_names = {e.name for e in entities}
    assert "UserService" in entity_names
    routine_names = {r.name for r in routines}
    assert "formatName" in routine_names


def test_dispatcher_swift_mixed_declarations(tmp_path: Path) -> None:
    """Dispatcher routes swift with mixed entities+routines in one file."""
    pytest.importorskip("tree_sitter_swift", reason="tree-sitter-swift not installed")
    cell_dir = tmp_path / "cell"
    cell_dir.mkdir()
    (cell_dir / "App.swift").write_text(
        "public class Server {\n"
        "    public init(host: String) {}\n"
        "    public func start() -> Bool { return true }\n"
        "}\n\n"
        "public func greet(name: String) -> String { return name }\n"
    )
    result = contract("swift", str(cell_dir))
    entities = [r for r in result if isinstance(r, EntityContract)]
    routines = [r for r in result if isinstance(r, RoutineContract)]
    assert len(entities) >= 1
    assert len(routines) >= 1
    entity_names = {e.name for e in entities}
    assert "Server" in entity_names
    routine_names = {r.name for r in routines}
    assert "greet" in routine_names


def test_facade_imports_all_symbols() -> None:
    """All key symbols are importable from goga.contract facade."""
    from goga.contract import (
        EntityContract,
        MethodContract,
        PropertyContract,
        RoutineContract,
        contract,
        kotlin_contract,
        swift_contract,
    )

    assert callable(contract)
    assert callable(kotlin_contract)
    assert callable(swift_contract)
    assert EntityContract.__name__ == "EntityContract"
    assert RoutineContract.__name__ == "RoutineContract"
    assert MethodContract.__name__ == "MethodContract"
    assert PropertyContract.__name__ == "PropertyContract"
