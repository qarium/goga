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
