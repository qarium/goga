"""Integration tests for python_contract — verifies signature extraction behaviour."""

import sys
from pathlib import Path

from goga.contract import python_contract


def _write_and_import(tmp_path: Path, source: str) -> list:
    """Write source to tmp_path/__init__.py, register on sys.path, and extract contract."""
    (tmp_path / "__init__.py").write_text(source)
    sys.path.insert(0, str(tmp_path.parent))
    module_name = tmp_path.name
    return python_contract(module_name)


def _first_param(sig_str: str) -> str | None:
    """Extract the first parameter name from a signature string like '(x: int, y: int) -> str'."""
    inner = sig_str[sig_str.index("(") + 1 : sig_str.index(")")]
    if not inner.strip():
        return None
    return inner.strip().split(":")[0].strip()


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
        assert _first_param(method.signature) != "cls"
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
        assert _first_param(method.signature) != "self"
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
        assert _first_param(method.signature) != "cls"
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
