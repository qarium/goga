"""Contract tests for goga.contract package."""

import importlib
import inspect
from dataclasses import fields

import pytest
from goga.contract import (
    BaseContract,
    EntityContract,
    MethodContract,
    PropertyContract,
    RoutineContract,
    python_contract,
)


class TestFacadeAvailability:
    """Contract: entities must be importable from the package facade."""

    def test_base_contract_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "BaseContract")
        assert mod.BaseContract is BaseContract

    def test_python_contract_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "python_contract")
        assert mod.python_contract is python_contract

    def test_base_contract_has_name_field(self):
        assert hasattr(BaseContract, "name")

    def test_base_contract_has_signature_field(self):
        assert hasattr(BaseContract, "signature")

    def test_base_contract_has_contract_field(self):
        item = BaseContract()
        assert hasattr(item, "contract")

    def test_base_contract_fields_are_str(self):
        field_map = {f.name: f.type for f in fields(BaseContract)}
        assert field_map["name"] == "str"
        assert field_map["signature"] == "str"

    def test_base_contract_kw_only(self):
        with pytest.raises(TypeError):
            BaseContract("positional_name", "positional_sig")

    def test_entity_contract_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "EntityContract")
        assert mod.EntityContract is EntityContract

    def test_routine_contract_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "RoutineContract")
        assert mod.RoutineContract is RoutineContract

    def test_property_contract_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "PropertyContract")
        assert mod.PropertyContract is PropertyContract

    def test_method_contract_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "MethodContract")
        assert mod.MethodContract is MethodContract

    def test_python_contract_accepts_cell_path(self):
        sig = inspect.signature(python_contract)
        params = list(sig.parameters.keys())
        assert "cell_path" in params
        assert sig.parameters["cell_path"].annotation == "str"
        # With from __future__ import annotations, return_annotation is a string
        ret = sig.return_annotation
        assert "list" in str(ret)

    def test_python_contract_returns_entity_or_routine(self, tmp_path, monkeypatch):
        """python_contract returns EntityContract for classes and RoutineContract for functions."""
        pkg = tmp_path / "testpkg_types"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "def my_func() -> None: ...\n"
            "class MyClass:\n    def __init__(self) -> None: ...\n"
            "__all__ = ['my_func', 'MyClass']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_types")

        assert isinstance(result[0], RoutineContract)
        assert isinstance(result[1], EntityContract)
        assert not isinstance(result[0], EntityContract)
        assert not isinstance(result[1], RoutineContract)


class TestBaseContractCreation:
    """Behavioral: BaseContract dataclass creation and defaults."""

    def test_base_contract_creation_with_values(self):
        item = BaseContract(name="test", signature="(x: int) -> str")
        assert item.name == "test"
        assert item.signature == "(x: int) -> str"
        assert item.contract == "test(x: int) -> str"

    def test_base_contract_default_values(self):
        item = BaseContract()
        assert item.name == ""
        assert item.signature == ""
        assert item.contract == ""


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

    def test_python_contract_skips_non_callable_objects(self, tmp_path, monkeypatch):
        """Skips non-callable objects, includes functions and callable types."""
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
        assert "an_alias" in names  # str is callable (class)
        assert "foo" in names
        assert len(result) == 2  # an_alias + foo


class TestPythonContractEdgeCases:
    """Edge case tests for python_contract."""

    def test_python_contract_module_in_all_not_included(self, tmp_path, monkeypatch):
        """Module listed in __all__ is not included in contract."""
        pkg = tmp_path / "testpkg_mod"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "import os\n"
            "def foo() -> None: ...\n"
            "__all__ = ['os', 'foo']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_mod")

        names = [item.name for item in result]
        assert "os" not in names  # module — not callable
        assert "foo" in names
        assert len(result) == 1
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

    def test_python_contract_class_without_explicit_init(self, tmp_path, monkeypatch):
        """Class with no explicit __init__ gets object.__init__ signature."""
        pkg_init = tmp_path / "testpkg_plain"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text(
            "class Plain:\n    pass\n"
            "__all__ = ['Plain']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_plain")

        assert len(result) == 1
        assert result[0].name == "Plain"
        assert "*args" in result[0].signature or result[0].signature == "()"

    def test_python_contract_empty_cell_path_raises(self):
        """Empty string cell_path raises an exception."""
        with pytest.raises(ValueError, match="Empty module name"):
            python_contract("")

    def test_python_contract_all_contains_nonexistent_name_raises(self, tmp_path, monkeypatch):
        """AttributeError when __all__ references a name not on the module."""
        pkg_init = tmp_path / "testpkg_stale"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text("__all__ = ['missing_name']\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        with pytest.raises(AttributeError):
            python_contract("testpkg_stale")


class TestEntityContractExtraction:
    """Tests for EntityContract property and method extraction."""

    def test_entity_contract_has_properties_and_methods(self, tmp_path, monkeypatch):
        """EntityContract extracts public properties, methods, and staticmethods; skips private."""
        pkg = tmp_path / "testpkg_entity"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "class Service:\n"
            "    def __init__(self) -> None: ...\n"
            "    @property\n"
            "    def name(self) -> str:\n"
            "        return ''\n"
            "    @property\n"
            "    def _hidden(self) -> str:\n"
            "        return ''\n"
            "    def run(self) -> None: ...\n"
            "    @staticmethod\n"
            "    def helper() -> int:\n"
            "        return 0\n"
            "__all__ = ['Service']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_entity")

        assert len(result) == 1
        entity = result[0]
        assert isinstance(entity, EntityContract)
        assert len(entity.properties) == 1
        assert entity.properties[0].name == "name"
        assert entity.properties[0].signature == "str"
        assert len(entity.methods) == 2
        method_names = [m.name for m in entity.methods]
        assert "run" in method_names
        assert "helper" in method_names
        assert "_hidden" not in [p.name for p in entity.properties]

    def test_entity_contract_classmethod(self, tmp_path, monkeypatch):
        """classmethod has cls removed from signature."""
        pkg = tmp_path / "testpkg_clsmethod"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "class Builder:\n"
            "    def __init__(self) -> None: ...\n"
            "    @classmethod\n"
            "    def create(cls, value: int) -> 'Builder':\n"
            "        return cls()\n"
            "__all__ = ['Builder']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_clsmethod")

        entity = result[0]
        method = entity.methods[0]
        assert method.name == "create"
        assert "cls" not in method.signature
        assert "value: int" in method.signature

    def test_entity_without_public_members(self, tmp_path, monkeypatch):
        """Class with only _private members has empty properties and methods."""
        pkg = tmp_path / "testpkg_private"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "class Secret:\n"
            "    def __init__(self) -> None: ...\n"
            "    def _internal(self) -> None: ...\n"
            "    @property\n"
            "    def _val(self) -> int:\n"
            "        return 0\n"
            "__all__ = ['Secret']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_private")

        entity = result[0]
        assert len(entity.properties) == 0
        assert len(entity.methods) == 0

    def test_property_without_return_annotation(self, tmp_path, monkeypatch):
        """@property without return type annotation has empty signature."""
        pkg = tmp_path / "testpkg_propannot"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "class Lazy:\n"
            "    def __init__(self) -> None: ...\n"
            "    @property\n"
            "    def data(self):\n"
            "        return None\n"
            "__all__ = ['Lazy']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_propannot")

        entity = result[0]
        assert len(entity.properties) == 1
        assert entity.properties[0].name == "data"
        assert entity.properties[0].signature == ""

    def test_entity_contract_inherits_base_contract(self):
        """EntityContract is an instance of BaseContract."""
        entity = EntityContract(name="Test", signature="()")
        assert isinstance(entity, BaseContract)

    def test_dataclass_fields_not_treated_as_properties(self, tmp_path, monkeypatch):
        """@dataclass class fields are not extracted as PropertyContract."""
        pkg = tmp_path / "testpkg_dcfields"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "from dataclasses import dataclass\n"
            "\n"
            "@dataclass\n"
            "class Record:\n"
            "    x: int\n"
            "    y: str = ''\n"
            "__all__ = ['Record']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_dcfields")

        entity = result[0]
        assert isinstance(entity, EntityContract)
        assert len(entity.properties) == 0
        # __init__ from dataclass should be the entity signature
        assert "x" in entity.signature

    def test_dataclass_with_property_over_field(self, tmp_path, monkeypatch):
        """@dataclass class with @property extracts the property into PropertyContract."""
        pkg = tmp_path / "testpkg_dcprop"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "from dataclasses import dataclass\n"
            "\n"
            "@dataclass\n"
            "class Config:\n"
            "    name: str = ''\n"
            "    @property\n"
            "    def display_name(self) -> str:\n"
            "        return self.name.upper()\n"
            "__all__ = ['Config']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_dcprop")

        entity = result[0]
        assert len(entity.properties) == 1
        assert entity.properties[0].name == "display_name"
        assert entity.properties[0].signature == "str"

    def test_entity_contract_inherited_methods_and_properties(self, tmp_path, monkeypatch):
        """Inherited public methods and properties are included via MRO walk."""
        pkg = tmp_path / "testpkg_inherit"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "class Base:\n"
            "    def __init__(self) -> None: ...\n"
            "    def base_method(self) -> None: ...\n"
            "    @property\n"
            "    def base_prop(self) -> int:\n"
            "        return 0\n"
            "\n"
            "class Child(Base):\n"
            "    def child_method(self) -> str:\n"
            "        return ''\n"
            "__all__ = ['Child']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_inherit")

        entity = result[0]
        method_names = [m.name for m in entity.methods]
        assert "base_method" in method_names
        assert "child_method" in method_names
        prop_names = [p.name for p in entity.properties]
        assert "base_prop" in prop_names
