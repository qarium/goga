"""Contract and logic tests for the entities declared in
``goga/hooks/tools/CODEMANIFEST`` with ``location: packages.py``:

- ``ToolPackage(module_name)`` — the identity of one installed tool package
- ``enumerate_tool_packages()`` — the deterministic environment enumeration
- ``call_register_hooks(package, registrar)`` — the facade import with the
  invocation of the single registration callback

The environment boundary is pinned by the shared fixtures of
``tests/hooks/conftest.py`` and by ``mock.patch`` on ``import_module``; the
module under test runs for real.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import typing
from types import ModuleType
from unittest import mock

import pytest
from goga.hooks.tools import packages
from goga.hooks.tools.packages import (
    ToolPackage,
    call_register_hooks,
    enumerate_tool_packages,
)

# --- Contract tests ---


class TestPackagesContract:
    def test_entities_are_importable_from_the_module(self) -> None:
        """The three entities live on ``packages.py`` — the cell's only code here."""
        assert packages.ToolPackage is ToolPackage
        assert packages.enumerate_tool_packages is enumerate_tool_packages
        assert packages.call_register_hooks is call_register_hooks

    def test_module_defines_no_public_entity_beyond_the_three(self) -> None:
        """No extra API, and nothing is pulled in from the catalog cell."""
        module = importlib.import_module("goga.hooks.tools.packages")
        defined = {
            name
            for name, value in vars(module).items()
            if not name.startswith("_") and getattr(value, "__module__", None) == module.__name__
        }
        origin_modules = {str(getattr(value, "__module__", "")) for value in vars(module).values()}

        assert defined == {"ToolPackage", "enumerate_tool_packages", "call_register_hooks"}
        assert not any(origin.startswith("goga.hooks.catalog") for origin in origin_modules)

    def test_tool_package_is_kw_only_frozen_with_computed_properties(self) -> None:
        """``ToolPackage(module_name=...)`` — keyword-only, frozen, one field.

        ``tool`` and ``facade`` are computed properties, not fields: the
        record stores the pip name and derives the identity from it.
        """
        package = ToolPackage(module_name="goga_tool_x")

        assert dataclasses.is_dataclass(ToolPackage)
        assert ToolPackage.__dataclass_params__.frozen
        assert ToolPackage.__dataclass_params__.kw_only
        assert package.module_name == "goga_tool_x"

        assert [field.name for field in dataclasses.fields(ToolPackage)] == ["module_name"]

        with pytest.raises(TypeError):
            ToolPackage("goga_tool_x")  # type: ignore[misc]

        with pytest.raises(dataclasses.FrozenInstanceError):
            package.module_name = "goga_tool_other"  # type: ignore[misc]

    def test_enumerate_tool_packages_signature(self) -> None:
        """``enumerate_tool_packages() -> list[ToolPackage]`` — no parameters."""
        parameters = inspect.signature(enumerate_tool_packages).parameters
        return_hint = typing.get_type_hints(enumerate_tool_packages)["return"]

        assert list(parameters) == []
        assert return_hint == list[ToolPackage]

    def test_call_register_hooks_signature(self) -> None:
        """``call_register_hooks(package, registrar) -> bool`` — two parameters."""
        signature = inspect.signature(call_register_hooks)

        assert list(signature.parameters) == ["package", "registrar"]
        assert signature.return_annotation == "bool"


# --- Logic tests: the identity and the enumeration ---


class TestToolPackageIdentity:
    def test_tool_package_identity_is_canonical_hyphen_form(self) -> None:
        """The prefix is dropped, underscores become hyphens; facade verbatim."""
        package = ToolPackage(module_name="goga_tool_my_tool")

        assert package.tool == "my-tool"
        assert package.facade == "goga_tool_my_tool"

        assert ToolPackage(module_name="goga_tool_mkdocs").tool == "mkdocs"


class TestEnumerateToolPackages:
    def test_enumerate_tool_packages_filters_prefix_and_sorts(self, pin_package_environment) -> None:
        """Only ``goga_tool_*`` names, alphabetically — and no import happens."""
        pin_package_environment(
            {
                "other_pkg": ["other-pkg"],
                "goga_tool_b": ["goga-tool-b"],
                "goga_tool_a": ["goga-tool-a"],
            }
        )

        with mock.patch.object(packages, "import_module") as import_mock:
            result = enumerate_tool_packages()

            import_mock.assert_not_called()

        assert [package.module_name for package in result] == ["goga_tool_a", "goga_tool_b"]

    def test_enumerate_tool_packages_empty_environment(self, pin_package_environment) -> None:
        """An environment without tool packages yields an empty list, not an error."""
        pin_package_environment({})

        assert enumerate_tool_packages() == []

    def test_enumerate_tool_packages_reads_the_boundary_once_per_call(
        self,
        pin_package_environment,
    ) -> None:
        """One environment read per call — the enumeration is a single pass."""
        boundary = pin_package_environment({"goga_tool_a": ["goga-tool-a"]})

        first = enumerate_tool_packages()
        second = enumerate_tool_packages()

        assert first == second
        assert boundary.call_count == 2


# --- Logic tests: the facade callback invocation ---


class TestCallRegisterHooks:
    def test_call_register_hooks_invokes_callback_with_single_registrar(
        self,
        install_tool_package,
    ) -> None:
        """The callback runs with the registrar as its single argument."""
        captured: list[object] = []
        install_tool_package("goga_tool_demo", register_hooks=captured.append)

        registrar = object()

        assert call_register_hooks(ToolPackage(module_name="goga_tool_demo"), registrar) is True
        assert captured == [registrar]

    def test_call_register_hooks_missing_package_is_quiet_skip(self, capsys) -> None:
        """The metadata names a package whose module is absent — a silent False."""
        absent = ToolPackage(module_name="goga_tool_absent_from_the_env")

        assert call_register_hooks(absent, object()) is False
        assert capsys.readouterr().err == ""

    def test_call_register_hooks_missing_callback_is_quiet_skip(
        self,
        install_tool_package,
        capsys,
    ) -> None:
        """A facade without ``register_hooks`` is a normal condition — no noise."""
        install_tool_package("goga_tool_silent")

        package = ToolPackage(module_name="goga_tool_silent")

        assert call_register_hooks(package, object()) is False
        assert capsys.readouterr().err == ""

    def test_call_register_hooks_non_callable_callback_is_quiet_skip(
        self,
        install_tool_package,
        capsys,
    ) -> None:
        """A ``register_hooks`` attribute that is not callable — a silent False."""
        install_tool_package("goga_tool_broken_promise", register_hooks=None)
        package = ToolPackage(module_name="goga_tool_broken_promise")

        assert call_register_hooks(package, object()) is False
        assert capsys.readouterr().err == ""

    def test_call_register_hooks_broken_import_raises_clean_error_naming_package(self) -> None:
        """A foreign, transitive import failure — the single fatal case."""
        package = ToolPackage(module_name="goga_tool_demo")
        failure = ModuleNotFoundError("No module named 'dep'", name="dep")

        with (
            mock.patch.object(packages, "import_module", side_effect=failure),
            pytest.raises(ImportError, match=r"package goga_tool_demo failed to import") as info,
        ):
            call_register_hooks(package, object())

        assert info.value.__cause__ is failure

    def test_call_register_hooks_syntax_error_raises_clean_error_naming_package(self) -> None:
        """A package that fails to parse — wrapped the same clean way."""
        package = ToolPackage(module_name="goga_tool_demo")
        failure = SyntaxError("invalid syntax (goga_tool_demo/__init__.py, line 1)")

        with (
            mock.patch.object(packages, "import_module", side_effect=failure),
            pytest.raises(ImportError, match=r"package goga_tool_demo failed to import"),
        ):
            call_register_hooks(package, object())

    def test_call_register_hooks_callback_exception_propagates_unchanged(self) -> None:
        """A callback crash is not wrapped and not swallowed — the caller decides."""
        failure = ValueError("boom")

        def callback(hooks: object) -> None:
            raise failure

        module = ModuleType("goga_tool_demo")
        module.register_hooks = callback

        with (
            mock.patch.object(packages, "import_module", return_value=module),
            pytest.raises(ValueError, match="boom") as info,
        ):
            call_register_hooks(ToolPackage(module_name="goga_tool_demo"), object())

        assert info.value is failure
