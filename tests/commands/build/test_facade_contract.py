"""Facade contract lock of the ``goga.commands.build`` package.

The cell's CODEMANIFEST declares the CLI command and the three host-side
runtime-directory helpers: the persistent ralphex runtime directory
resolution (``resolve_build_runtime_dir``), its total wipe
(``clean_build_runtime_dir``), and the project-directory ``.ralphex/``
cleanup (``_cleanup_ralphex_in_project``) backing the build constraint
that ``.ralphex/`` never stays in the project directory.
"""

from __future__ import annotations

import importlib
import sys

import click

CONTRACT_FACADE_NAMES = [
    "_cleanup_ralphex_in_project",
    "build",
    "clean_build_runtime_dir",
    "resolve_build_runtime_dir",
]


def _build_command_package():
    """Return the goga.commands.build package, whose name is shadowed on goga.commands.

    Returns:
        The goga.commands.build module object.
    """
    return importlib.import_module("goga.commands.build")


class TestCommandsBuildFacade:
    def test_facade_all_is_exact_contract_set(self) -> None:
        """__all__ carries exactly the CODEMANIFEST-declared names."""
        package = _build_command_package()

        assert package.__all__ == CONTRACT_FACADE_NAMES

    def test_facade_all_is_alphabetical(self) -> None:
        """__all__ keeps the alphabetical ordering convention (underscore first)."""
        package = _build_command_package()

        assert package.__all__ == sorted(package.__all__)

    def test_build_is_a_click_command(self) -> None:
        """The build facade member is a click.Command (not a group)."""
        package = _build_command_package()

        assert isinstance(package.build, click.Command)
        assert not isinstance(package.build, click.Group)

    def test_helpers_are_callable(self) -> None:
        """The three runtime-directory helpers export callables."""
        package = _build_command_package()

        for name in ("_cleanup_ralphex_in_project", "clean_build_runtime_dir", "resolve_build_runtime_dir"):
            assert callable(getattr(package, name)), f"{name} is not callable"

    def test_helpers_match_their_module_objects(self) -> None:
        """The facade re-exports the build.py module objects themselves."""
        build_module = sys.modules["goga.commands.build.build"]
        package = _build_command_package()

        assert package.resolve_build_runtime_dir is build_module.resolve_build_runtime_dir
        assert package.clean_build_runtime_dir is build_module.clean_build_runtime_dir
        assert package._cleanup_ralphex_in_project is build_module._cleanup_ralphex_in_project
