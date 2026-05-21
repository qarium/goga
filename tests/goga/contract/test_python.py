"""Integration tests for python_contract — verifies signature extraction behaviour."""

import json
import sys
from pathlib import Path

import pytest
from goga.contract import EntityContract, RoutineContract, python_contract


def _write_and_import(tmp_path: Path, source: str) -> list:
    """Write source to tmp_path/__init__.py, register on sys.path, and extract contract."""
    (tmp_path / "__init__.py").write_text(source)
    parent = str(tmp_path.parent)
    module_name = tmp_path.name
    sys.path.insert(0, parent)
    try:
        return python_contract(module_name)
    finally:
        sys.path.remove(parent)
        sys.modules.pop(module_name, None)


class TestClassmethodExcludesCls:
    """inspect.signature on a bound classmethod automatically excludes cls."""

    def test_classmethod_excludes_cls_from_signature(self, tmp_path) -> None:
        source = "\n".join(
            [
                "class MyClass:",
                "    @classmethod",
                "    def create(cls, x: int) -> int:",
                "        return x",
                "",
                "__all__ = ['MyClass']",
            ]
        )
        result = _write_and_import(tmp_path, source)
        assert len(result) == 1
        entity = result[0]
        methods = [m for m in entity.methods if m.name == "create"]
        assert len(methods) == 1
        method = methods[0]
        assert method.signature == "(x: int) -> int"


class TestRegularMethodExcludesSelf:
    """self is removed from regular instance method signatures."""

    def test_regular_method_excludes_self(self, tmp_path) -> None:
        source = "\n".join(
            [
                "class Service:",
                "    def process(self, data: str) -> bool:",
                "        return True",
                "",
                "__all__ = ['Service']",
            ]
        )
        result = _write_and_import(tmp_path, source)
        assert len(result) == 1
        entity = result[0]
        methods = [m for m in entity.methods if m.name == "process"]
        assert len(methods) == 1
        method = methods[0]
        assert method.signature == "(data: str) -> bool"


class TestStaticmethodKeepsAllParams:
    """staticmethod preserves all parameters in the signature."""

    def test_staticmethod_keeps_all_params(self, tmp_path) -> None:
        source = "\n".join(
            [
                "class Calculator:",
                "    @staticmethod",
                "    def add(x: int, y: int) -> int:",
                "        return x + y",
                "",
                "__all__ = ['Calculator']",
            ]
        )
        result = _write_and_import(tmp_path, source)
        assert len(result) == 1
        entity = result[0]
        methods = [m for m in entity.methods if m.name == "add"]
        assert len(methods) == 1
        method = methods[0]
        assert method.signature == "(x: int, y: int) -> int"


class TestClassmethodWithSelfNamedParam:
    """Edge case: self as a regular parameter name in a classmethod."""

    def test_classmethod_with_self_named_param(self, tmp_path) -> None:
        source = "\n".join(
            [
                "class Handler:",
                "    @classmethod",
                "    def method(cls, self: int) -> None:",
                "        pass",
                "",
                "__all__ = ['Handler']",
            ]
        )
        result = _write_and_import(tmp_path, source)
        assert len(result) == 1
        entity = result[0]
        methods = [m for m in entity.methods if m.name == "method"]
        assert len(methods) == 1
        method = methods[0]
        assert method.signature == "(self: int) -> None"


class TestPropertyContractFormatThroughPythonContract:
    """PropertyContract extracted via python_contract uses arrow format."""

    def test_property_contract_format_through_python_contract(self, tmp_path) -> None:
        source = "\n".join(
            [
                "class Container:",
                "    @property",
                "    def items(self) -> list[str]:",
                "        return []",
                "",
                "__all__ = ['Container']",
            ]
        )
        result = _write_and_import(tmp_path, source)
        assert len(result) == 1
        entity = result[0]
        props = [p for p in entity.properties if p.name == "items"]
        assert len(props) == 1
        prop = props[0]
        assert prop.contract == "items -> list[str]"


class TestPythonContractPositive:
    """Positive behavioral tests for python_contract."""

    def test_python_contract_extracts_functions_and_classes(self, tmp_path, monkeypatch):
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
        pkg_init = tmp_path / "testpkg_empty"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text("__all__ = []\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_empty")

        assert result == []

    def test_python_contract_no_all(self, tmp_path, monkeypatch):
        pkg_init = tmp_path / "testpkg_noall"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text("x = 42\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_noall")

        assert result == []


class TestPythonContractNegative:
    """Negative behavioral tests for python_contract."""

    def test_python_contract_module_not_found(self):
        with pytest.raises(ModuleNotFoundError):
            python_contract("nonexistent/module/path")

    def test_python_contract_skips_non_callable_objects(self, tmp_path, monkeypatch):
        pkg_init = tmp_path / "testpkg_skip"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text(
            "CONSTANT = 42\nan_alias = str\ndef foo(): ...\n__all__ = ['CONSTANT', 'an_alias', 'foo']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_skip")

        names = [item.name for item in result]
        assert "CONSTANT" not in names
        assert "an_alias" in names
        assert "foo" in names
        assert len(result) == 2


class TestPythonContractEdgeCases:
    """Edge case tests for python_contract."""

    def test_python_contract_module_in_all_not_included(self, tmp_path, monkeypatch):
        pkg = tmp_path / "testpkg_mod"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("import os\ndef foo() -> None: ...\n__all__ = ['os', 'foo']\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_mod")

        names = [item.name for item in result]
        assert "os" not in names
        assert "foo" in names
        assert len(result) == 1

    def test_python_contract_nested_path(self, tmp_path, monkeypatch):
        nested = tmp_path / "nested_a" / "b" / "c"
        nested.mkdir(parents=True)
        (nested / "__init__.py").write_text("def deep_func() -> int:\n    return 0\n__all__ = ['deep_func']\n")
        (tmp_path / "nested_a" / "__init__.py").write_text("")
        (tmp_path / "nested_a" / "b" / "__init__.py").write_text("")
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("nested_a/b/c")

        assert len(result) == 1
        assert result[0].name == "deep_func"

    def test_python_contract_class_with_args_kwargs(self, tmp_path, monkeypatch):
        pkg_init = tmp_path / "testpkg_args"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text(
            "class Flexible:\n    def __init__(self, *args: int, **kwargs: str): ...\n__all__ = ['Flexible']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_args")

        assert len(result) == 1
        assert "*args" in result[0].signature
        assert "**kwargs" in result[0].signature

    def test_python_contract_preserves_default_values(self, tmp_path, monkeypatch):
        pkg_init = tmp_path / "testpkg_defaults"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text(
            "def func(a: int, b: str = 'hello', c: float = 3.14): ...\n__all__ = ['func']\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_defaults")

        sig = result[0].signature
        assert "a: int" in sig
        assert "'hello'" in sig
        assert "3.14" in sig

    def test_python_contract_preserves_argument_order(self, tmp_path, monkeypatch):
        pkg_init = tmp_path / "testpkg_order"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text("def func(z: int, a: str, m: float): ...\n__all__ = ['func']\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_order")

        sig = result[0].signature
        assert sig.index("z") < sig.index("a") < sig.index("m")

    def test_python_contract_path_with_trailing_slashes(self, tmp_path, monkeypatch):
        pkg_init = tmp_path / "testpkg_slash"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text("def func(): ...\n__all__ = ['func']\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("/testpkg_slash/")

        assert len(result) == 1
        assert result[0].name == "func"

    def test_python_contract_class_without_explicit_init(self, tmp_path, monkeypatch):
        pkg_init = tmp_path / "testpkg_plain"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text("class Plain:\n    pass\n__all__ = ['Plain']\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        result = python_contract("testpkg_plain")

        assert len(result) == 1
        assert result[0].name == "Plain"
        assert "*args" in result[0].signature or result[0].signature == "()"

    def test_python_contract_empty_cell_path_raises(self):
        with pytest.raises(ValueError, match="Empty module name"):
            python_contract("")

    def test_python_contract_all_contains_nonexistent_name_raises(self, tmp_path, monkeypatch):
        pkg_init = tmp_path / "testpkg_stale"
        pkg_init.mkdir()
        (pkg_init / "__init__.py").write_text("__all__ = ['missing_name']\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        with pytest.raises(AttributeError):
            python_contract("testpkg_stale")


class TestEntityContractExtraction:
    """Tests for EntityContract property and method extraction."""

    def test_entity_contract_has_properties_and_methods(self, tmp_path, monkeypatch):
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

    def test_entity_without_public_members(self, tmp_path, monkeypatch):
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

    def test_dataclass_fields_not_treated_as_properties(self, tmp_path, monkeypatch):
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
        assert "x" in entity.signature

    def test_dataclass_with_property_over_field(self, tmp_path, monkeypatch):
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


class TestSelfReference:
    """python_contract extracts the facade of its own package."""

    def test_self_contract_contains_base_contract(self):
        result = python_contract("goga/contract")
        names = [item.name for item in result]
        assert "BaseContract" in names

    def test_self_contract_contains_python_contract(self):
        result = python_contract("goga/contract")
        names = [item.name for item in result]
        assert "python_contract" in names

    def test_self_contract_base_contract_is_entity(self):
        result = python_contract("goga/contract")
        base = next(item for item in result if item.name == "BaseContract")
        assert isinstance(base, EntityContract)

    def test_self_contract_python_contract_is_routine(self):
        result = python_contract("goga/contract")
        fn = next(item for item in result if item.name == "python_contract")
        assert isinstance(fn, RoutineContract)


class TestRealPackageExtraction:
    """python_contract extracts facade from a real project submodule."""

    def test_ast_factory_has_factory(self):
        result = python_contract("goga/ast/factory")
        assert len(result) > 0
        names = [item.name for item in result]
        assert "Factory" in names

    def test_ast_factory_all_items_have_name_and_signature(self):
        result = python_contract("goga/ast/factory")
        for item in result:
            assert item.name != ""
            assert item.signature != ""

    def test_ast_factory_is_entity_with_members(self):
        result = python_contract("goga/ast/factory")
        factory = next(item for item in result if item.name == "Factory")
        assert isinstance(factory, EntityContract)
        assert len(factory.methods) > 0 or len(factory.properties) > 0


class TestSignatureFormatMatchesContractFormat:
    """Result is serializable to contract_format: [{"name": "...", "signature": "..."}]."""

    def test_result_serializable_to_json(self):
        result = python_contract("goga/contract")
        data = [{"name": item.name, "signature": item.signature} for item in result]
        serialized = json.dumps(data)
        parsed = json.loads(serialized)
        assert parsed == data

    def test_entity_with_properties_and_methods_serializable(self):
        result = python_contract("goga/ast/factory")
        factory = next(item for item in result if item.name == "Factory")
        for prop in factory.properties:
            assert prop.name != ""
            assert isinstance(prop.signature, str)
            assert json.dumps({"name": prop.name, "signature": prop.signature})
        for method in factory.methods:
            assert method.name != ""
            assert isinstance(method.signature, str)
            assert json.dumps({"name": method.name, "signature": method.signature})

    def test_full_entity_serializable_with_members(self):
        result = python_contract("goga/ast/factory")
        factory = next(item for item in result if item.name == "Factory")
        data = {
            "name": factory.name,
            "signature": factory.signature,
            "properties": [{"name": p.name, "signature": p.signature} for p in factory.properties],
            "methods": [{"name": m.name, "signature": m.signature} for m in factory.methods],
        }
        serialized = json.dumps(data)
        parsed = json.loads(serialized)
        assert parsed == data
