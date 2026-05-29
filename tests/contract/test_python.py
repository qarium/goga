"""Tests for python_contract — tree-sitter based public definition extraction."""

import json
from dataclasses import asdict
from pathlib import Path
from textwrap import dedent

from goga.contract import EntityContract, RoutineContract
from goga.contract.python import python_contract


class TestContractFacade:
    """Contract tests: facade import and API signature."""

    def test_facade_importable(self):
        from goga.contract.python import python_contract as fn
        assert callable(fn)

    def test_signature_accepts_str_returns_list(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        result = python_contract(str(pkg))
        assert isinstance(result, list)


class TestPositiveBehavioral:
    """Positive behavioral tests for python_contract."""

    def test_extracts_entity_and_routine(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            class MyClass:
                def __init__(self, name: str):
                    self.name = name

            def my_func(x: int) -> str:
                return str(x)
        """))
        result = python_contract(str(pkg))
        assert len(result) == 2
        entity = next(r for r in result if r.name == "MyClass")
        assert isinstance(entity, EntityContract)
        assert entity.signature == "(name: str)"
        routine = next(r for r in result if r.name == "my_func")
        assert isinstance(routine, RoutineContract)
        assert routine.signature == "(x: int) -> str"

    def test_extracts_properties(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            class Config:
                def __init__(self):
                    self._host = ""
                    self._port = 0

                @property
                def host(self) -> str:
                    return self._host

                @property
                def port(self) -> int:
                    return self._port
        """))
        result = python_contract(str(pkg))
        assert len(result) == 1
        entity = result[0]
        assert len(entity.properties) == 2
        prop_names = {p.name for p in entity.properties}
        assert prop_names == {"host", "port"}
        host_prop = next(p for p in entity.properties if p.name == "host")
        assert host_prop.signature == "str"
        port_prop = next(p for p in entity.properties if p.name == "port")
        assert port_prop.signature == "int"

    def test_handles_default_params(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            def connect(host: str = "localhost", port: int = 8080) -> None:
                pass
        """))
        result = python_contract(str(pkg))
        assert len(result) == 1
        assert result[0].name == "connect"
        assert 'host: str = "localhost"' in result[0].signature
        assert "port: int = 8080" in result[0].signature

    def test_handles_args_kwargs(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            def func(x: int, *args, **kwargs) -> None:
                pass
        """))
        result = python_contract(str(pkg))
        assert len(result) == 1
        sig = result[0].signature
        assert "x: int" in sig
        assert "*args" in sig
        assert "**kwargs" in sig

    def test_extracts_mixed_entity(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            class Service:
                def __init__(self, name: str) -> None:
                    self.name = name

                @property
                def info(self) -> str:
                    return self.name

                def run(self, task: str) -> bool:
                    return True

                def _internal(self) -> None:
                    pass
        """))
        result = python_contract(str(pkg))
        assert len(result) == 1
        entity = result[0]
        assert isinstance(entity, EntityContract)
        assert entity.signature == "(name: str)"
        assert len(entity.properties) == 1
        assert entity.properties[0].name == "info"
        assert entity.properties[0].signature == "str"
        assert len(entity.methods) == 1
        assert entity.methods[0].name == "run"
        assert entity.methods[0].signature == "(task: str) -> bool"

    def test_extracts_public_methods(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            class Worker:
                def __init__(self) -> None:
                    pass

                def process(self, data: str) -> bool:
                    return True

                def execute(self, cmd: str) -> str:
                    return cmd
        """))
        result = python_contract(str(pkg))
        assert len(result) == 1
        entity = result[0]
        method_names = [m.name for m in entity.methods]
        assert method_names == ["execute", "process"]
        for method in entity.methods:
            assert "self" not in method.signature

    def test_extracts_decorated_methods(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            class Calc:
                def __init__(self) -> None:
                    pass

                @staticmethod
                def add(x: int, y: int) -> int:
                    return x + y

                @classmethod
                def create(cls, value: int):
                    return Calc()
        """))
        result = python_contract(str(pkg))
        assert len(result) == 1
        entity = result[0]
        assert len(entity.methods) == 2
        method_names = {m.name for m in entity.methods}
        assert method_names == {"add", "create"}
        add_method = next(m for m in entity.methods if m.name == "add")
        assert add_method.signature == "(x: int, y: int) -> int"
        create_method = next(m for m in entity.methods if m.name == "create")
        assert "cls" in create_method.signature

    def test_returns_sorted(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            class Zebra:
                def __init__(self) -> None:
                    pass

            class Apple:
                def __init__(self) -> None:
                    pass

            def beta_func() -> None:
                pass

            def alpha_func() -> None:
                pass
        """))
        result = python_contract(str(pkg))
        assert len(result) == 4
        assert result[0].name == "Apple"
        assert result[1].name == "Zebra"
        assert result[2].name == "alpha_func"
        assert result[3].name == "beta_func"

    def test_extracts_from_multiple_files(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "models.py").write_text(dedent("""\
            class User:
                def __init__(self, name: str) -> None:
                    pass
        """))
        (pkg / "utils.py").write_text(dedent("""\
            def helper(x: int) -> str:
                return str(x)
        """))
        result = python_contract(str(pkg))
        names = {r.name for r in result}
        assert "User" in names
        assert "helper" in names

    def test_main_py_scanned_like_any_file(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "__main__.py").write_text(dedent("""\
            def main() -> None:
                pass
        """))
        result = python_contract(str(pkg))
        names = [r.name for r in result]
        assert "main" in names
        main_routine = next(r for r in result if r.name == "main")
        assert isinstance(main_routine, RoutineContract)
        assert main_routine.signature == "() -> None"

    def test_extracts_type_annotated_fields_as_properties(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            class CellData:
                name: str
                description: str
                children: list[str]
        """))
        result = python_contract(str(pkg))
        assert len(result) == 1
        entity = result[0]
        assert isinstance(entity, EntityContract)
        prop_names = {p.name for p in entity.properties}
        assert prop_names == {"name", "description", "children"}
        name_prop = next(p for p in entity.properties if p.name == "name")
        assert name_prop.signature == "str"
        children_prop = next(p for p in entity.properties if p.name == "children")
        assert children_prop.signature == "list[str]"

    def test_type_annotated_field_with_default(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            class Config:
                host: str = "localhost"
                port: int = 8080
        """))
        result = python_contract(str(pkg))
        entity = result[0]
        prop_names = {p.name for p in entity.properties}
        assert prop_names == {"host", "port"}
        host_prop = next(p for p in entity.properties if p.name == "host")
        assert host_prop.signature == "str"

    def test_mixed_property_and_annotated_field(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            class Service:
                name: str
                timeout: int = 30

                @property
                def url(self) -> str:
                    return ""

                def run(self) -> bool:
                    return True
        """))
        result = python_contract(str(pkg))
        entity = result[0]
        prop_names = {p.name for p in entity.properties}
        assert prop_names == {"name", "timeout", "url"}
        method_names = {m.name for m in entity.methods}
        assert method_names == {"run"}

    def test_plain_assignment_not_extracted_as_property(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            class Foo:
                name: str
                counter = 0
        """))
        result = python_contract(str(pkg))
        entity = result[0]
        prop_names = {p.name for p in entity.properties}
        assert "name" in prop_names
        assert "counter" not in prop_names


class TestNegativeBehavioral:
    """Negative behavioral tests for python_contract."""

    def test_returns_empty_when_no_py_files(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        result = python_contract(str(pkg))
        assert result == []

    def test_raises_for_nonexistent_directory(self, tmp_path):
        import pytest

        with pytest.raises(FileNotFoundError):
            python_contract(str(tmp_path / "no_such_dir"))


class TestEdgeCases:
    """Edge case tests for python_contract."""

    def test_no_type_annotations(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            def func(x, y):
                pass
        """))
        result = python_contract(str(pkg))
        assert len(result) == 1
        assert result[0].signature == "(x, y)"

    def test_class_without_init(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            class Plain:
                pass
        """))
        result = python_contract(str(pkg))
        assert len(result) == 1
        assert result[0].name == "Plain"
        assert result[0].signature == "()"

    def test_property_without_return_type(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            class Container:
                def __init__(self) -> None:
                    pass

                @property
                def data(self):
                    return None
        """))
        result = python_contract(str(pkg))
        entity = result[0]
        assert len(entity.properties) == 1
        assert entity.properties[0].name == "data"
        assert entity.properties[0].signature == ""

    def test_private_members_excluded(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            class MyClass:
                def __init__(self) -> None:
                    pass

                def _private(self) -> None:
                    pass

                def __repr__(self) -> str:
                    return ""

                @property
                def _hidden(self) -> int:
                    return 0

                def public(self) -> None:
                    pass
        """))
        result = python_contract(str(pkg))
        entity = result[0]
        method_names = [m.name for m in entity.methods]
        assert "_private" not in method_names
        assert "__repr__" not in method_names
        assert "public" in method_names
        prop_names = [p.name for p in entity.properties]
        assert "_hidden" not in prop_names

    def test_private_module_level_excluded(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            def public_func() -> None:
                pass

            def _private_func() -> None:
                pass

            class PublicClass:
                pass

            class _PrivateClass:
                pass
        """))
        result = python_contract(str(pkg))
        names = [r.name for r in result]
        assert "public_func" in names
        assert "PublicClass" in names
        assert "_private_func" not in names
        assert "_PrivateClass" not in names

    def test_last_definition_wins(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            def func(x: int) -> str:
                return str(x)
        """))
        (pkg / "b.py").write_text(dedent("""\
            def func(y: float) -> int:
                return int(y)
        """))
        result = python_contract(str(pkg))
        assert len(result) == 1
        assert "y: float" in result[0].signature

    def test_non_callable_in_definitions(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(dedent("""\
            VALUE = 42

            def foo() -> None:
                pass
        """))
        result = python_contract(str(pkg))
        names = [item.name for item in result]
        assert "VALUE" not in names
        assert "foo" in names
        assert len(result) == 1

    def test_empty_init_returns_empty(self, tmp_path):
        pkg = tmp_path / "testpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        result = python_contract(str(pkg))
        assert result == []


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestIntegration:
    """Integration tests: real project packages and serialization."""

    def test_self_contract_contains_base_contract(self):
        result = python_contract(str(_PROJECT_ROOT / "goga/contract/data"))
        names = [r.name for r in result]
        assert "BaseContract" in names

    def test_self_contract_contains_python_contract(self):
        result = python_contract(str(_PROJECT_ROOT / "goga/contract/python"))
        names = [r.name for r in result]
        assert "python_contract" in names

    def test_self_contract_base_contract_is_entity(self):
        result = python_contract(str(_PROJECT_ROOT / "goga/contract/data"))
        base = next(r for r in result if r.name == "BaseContract")
        assert isinstance(base, EntityContract)

    def test_self_contract_python_contract_is_routine(self):
        result = python_contract(str(_PROJECT_ROOT / "goga/contract/python"))
        func = next(r for r in result if r.name == "python_contract")
        assert isinstance(func, RoutineContract)

    def test_ast_factory_has_factory(self):
        result = python_contract(str(_PROJECT_ROOT / "goga/ast/factory"))
        names = [r.name for r in result]
        assert "Factory" in names

    def test_ast_factory_all_items_have_name_and_signature(self):
        result = python_contract(str(_PROJECT_ROOT / "goga/ast/factory"))
        for item in result:
            assert item.name
            assert item.signature != ""

    def test_ast_factory_is_entity_with_members(self):
        result = python_contract(str(_PROJECT_ROOT / "goga/ast/factory"))
        factory = next(r for r in result if r.name == "Factory")
        assert isinstance(factory, EntityContract)
        assert len(factory.methods) > 0 or len(factory.properties) > 0

    def test_result_serializable_to_json(self):
        result = python_contract(str(_PROJECT_ROOT / "goga/ast/factory"))
        data = [asdict(r) for r in result]
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert len(parsed) == len(result)
        for item in parsed:
            assert "name" in item
            assert "signature" in item

    def test_entity_with_properties_and_methods_serializable(self):
        result = python_contract(str(_PROJECT_ROOT / "goga/ast/factory"))
        factory = next(r for r in result if r.name == "Factory")
        data = asdict(factory)
        assert "properties" in data
        assert "methods" in data
        parsed = json.loads(json.dumps(data))
        assert isinstance(parsed["properties"], list)
        assert isinstance(parsed["methods"], list)

    def test_full_entity_serializable_with_members(self):
        result = python_contract(str(_PROJECT_ROOT / "goga/ast/factory"))
        data = [asdict(r) for r in result]
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert len(parsed) > 0
        factory_data = next(d for d in parsed if d["name"] == "Factory")
        assert "properties" in factory_data
        assert "methods" in factory_data
