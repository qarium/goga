"""Contract tests for goga.contract package."""

import dataclasses
import importlib
import inspect
from dataclasses import fields

import pytest
from goga.contract import ContractItem, python_contract


class TestFacadeAvailability:
    """Contract: entities must be importable from the package facade."""

    def test_contract_item_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "ContractItem")
        assert mod.ContractItem is ContractItem

    def test_python_contract_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "python_contract")
        assert mod.python_contract is python_contract

    def test_contract_item_has_name_field(self):
        assert hasattr(ContractItem, "name")

    def test_contract_item_has_signature_field(self):
        assert hasattr(ContractItem, "signature")

    def test_contract_item_fields_are_str(self):
        field_map = {f.name: f.type for f in fields(ContractItem)}
        assert field_map["name"] is str
        assert field_map["signature"] is str

    def test_contract_item_kw_only(self):
        assert dataclasses.fields(ContractItem)
        with pytest.raises(TypeError):
            ContractItem("positional_name", "positional_sig")

    def test_python_contract_accepts_cell_path(self):
        sig = inspect.signature(python_contract)
        params = list(sig.parameters.keys())
        assert "cell_path" in params
        assert sig.return_annotation is not inspect.Parameter.empty


class TestContractItemCreation:
    """Behavioral: ContractItem dataclass creation and defaults."""

    def test_contract_item_creation_with_values(self):
        item = ContractItem(name="test", signature="(x: int) -> str")
        assert item.name == "test"
        assert item.signature == "(x: int) -> str"

    def test_contract_item_default_values(self):
        item = ContractItem()
        assert item.name == ""
        assert item.signature == ""


class TestPythonContractPositive:
    """Positive behavioral tests for python_contract."""

    def test_python_contract_extracts_functions_and_classes(self, tmp_path, monkeypatch):
        """Extracts both functions and classes from __all__."""
        pkg_init = tmp_path / "testpkg_extract"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text(
            "def foo(x: int) -> str:\n    return str(x)\n"
            "\n"
            "class Bar:\n    def __init__(self, name: str = 'default'): ...\n"
            "\n"
            "__all__ = ['foo', 'Bar']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_extract")

        assert len(result) == 2
        assert result[0].name == "foo"
        assert "x: int" in result[0].signature
        assert result[1].name == "Bar"
        assert "name: str" in result[1].signature

    def test_python_contract_empty_all(self, tmp_path, monkeypatch):
        """Empty __all__ returns empty list."""
        pkg_init = tmp_path / "testpkg_empty"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text("__all__ = []\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_empty")

        assert result == []

    def test_python_contract_no_all(self, tmp_path, monkeypatch):
        """Module without __all__ returns empty list."""
        pkg_init = tmp_path / "testpkg_noall"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text("x = 42\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_noall")

        assert result == []


class TestPythonContractNegative:
    """Negative behavioral tests for python_contract."""

    def test_python_contract_module_not_found(self):
        """Raises ModuleNotFoundError for nonexistent module."""
        with pytest.raises(ModuleNotFoundError):
            python_contract("nonexistent/module/path")

    def test_python_contract_skips_non_function_class_objects(self, tmp_path, monkeypatch):
        """Skips constants and type aliases, includes functions and builtin-type aliases."""
        pkg_init = tmp_path / "testpkg_skip"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text(
            "CONSTANT = 42\n"
            "an_alias = str\n"
            "def foo(): ...\n"
            "__all__ = ['CONSTANT', 'an_alias', 'foo']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_skip")

        names = [item.name for item in result]
        assert "CONSTANT" not in names
        assert "foo" in names
        assert len(result) == 2


class TestPythonContractEdgeCases:
    """Edge case tests for python_contract."""

    def test_python_contract_nested_path(self, tmp_path, monkeypatch):
        """Handles nested package paths like a/b/c."""
        nested = tmp_path / "nested_a" / "b" / "c"
        nested.mkdir(parents=True)
        (nested / "__init__.py").write_text(
            "def deep_func() -> int:\n    return 0\n"
            "__all__ = ['deep_func']\n"
        )
        (tmp_path / "nested_a" / "__init__.py").write_text("")
        (tmp_path / "nested_a" / "b" / "__init__.py").write_text("")
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("nested_a/b/c")

        assert len(result) == 1
        assert result[0].name == "deep_func"

    def test_python_contract_class_with_args_kwargs(self, tmp_path, monkeypatch):
        """Preserves *args and **kwargs in class __init__ signature."""
        pkg_init = tmp_path / "testpkg_args"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text(
            "class Flexible:\n"
            "    def __init__(self, *args: int, **kwargs: str): ...\n"
            "__all__ = ['Flexible']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_args")

        assert len(result) == 1
        assert "*args" in result[0].signature
        assert "**kwargs" in result[0].signature

    def test_python_contract_preserves_default_values(self, tmp_path, monkeypatch):
        """Preserves default values in function signature."""
        pkg_init = tmp_path / "testpkg_defaults"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text(
            "def func(a: int, b: str = 'hello', c: float = 3.14): ...\n"
            "__all__ = ['func']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_defaults")

        sig = result[0].signature
        assert "a: int" in sig
        assert "'hello'" in sig
        assert "3.14" in sig

    def test_python_contract_preserves_argument_order(self, tmp_path, monkeypatch):
        """Preserves argument order in signature."""
        pkg_init = tmp_path / "testpkg_order"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text(
            "def func(z: int, a: str, m: float): ...\n"
            "__all__ = ['func']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_order")

        sig = result[0].signature
        assert sig.index("z") < sig.index("a") < sig.index("m")

    def test_python_contract_path_with_trailing_slashes(self, tmp_path, monkeypatch):
        """Handles paths with leading/trailing slashes."""
        pkg_init = tmp_path / "testpkg_slash"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text(
            "def func(): ...\n"
            "__all__ = ['func']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("/testpkg_slash/")

        assert len(result) == 1
        assert result[0].name == "func"
