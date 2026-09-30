"""Shared fixtures and walk scaffolding of the schema zone tests.

Re-exports the two boundary fixtures of the hooks platform tests
(``pin_package_environment`` / ``install_tool_package``) so the zone suites pin
the same two outside-world points — the ``packages_distributions`` read and the
``sys.modules`` entry of a ``goga_tool_*`` package — with the platform code
under test running for real.

Also carries the CODEMANIFEST-tree scaffolding shared by the walk suites of
this zone and the cross-package integration suite
(``tests/integration/test_schema_walk_gate_integration.py``): the manifest
writer, the two-cell fixture tree, and the fake tool-package installers of the
checkpoint and gate halves.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from tests.hooks.conftest import install_tool_package, pin_package_environment

__all__ = ["install_tool_package", "pin_package_environment"]


def _write_codemanifest(directory: Path, content: str) -> None:
    (directory / "CODEMANIFEST").write_text(content, encoding="utf-8")


WALK_ROOT_WITH_CHILD = """\
Imports:
  - Types:
      - Helper
    From: subpkg

Usages: {}

Annotations: |
  Uses `Helper` here

---
"MyClass()":
  location: myclass.py
  annotations: |
    A test class

---
Author: Test
CreatedAt: 01/01/01
Description: Root cell
"""

WALK_CHILD = """\
Usages: {}

Annotations: ""

---
"Helper()":
  location: helper.py
  annotations: |
    A helper

---
Author: Test
CreatedAt: 01/01/01
Description: Sub package
"""


def _install_docs_tool(
    pin_package_environment,
    install_tool_package,
    hook,
):
    """Pin the environment to one docs tool and install its facade carrying ``hook``.

    Args:
        pin_package_environment: the boundary-pinning fixture factory.
        install_tool_package: the package-installing fixture factory.
        hook: the hook subscribed to the ``schema.amend_cell`` address.

    Returns:
        The boundary mock — the installed-packages read of the run.
    """
    boundary = pin_package_environment({"goga_tool_docs": ["docs-dist"]})

    def register(registrar: object) -> None:
        registrar.subscribe("schema", "amend_cell", "cover", hook)  # type: ignore[attr-defined]

    install_tool_package("goga_tool_docs", register_hooks=register)
    return boundary


def _install_gate_tools(
    pin_package_environment,
    install_tool_package,
    registrars: dict[str, Callable[[Any], None]],
) -> None:
    """Pin the environment and install one fake gate package per registrar entry.

    Args:
        pin_package_environment: the boundary-pinning fixture factory.
        install_tool_package: the package-installing fixture factory.
        registrars: the tool identity of each package mapped to its facade
            ``register_hooks`` callback.
    """
    pin_package_environment({f"goga_tool_{tool}": [f"{tool}-dist"] for tool in registrars})
    for tool, register in registrars.items():
        install_tool_package(f"goga_tool_{tool}", register_hooks=register)


def _write_walk_project(tmp_path: Path) -> None:
    """Write the small two-cell CODEMANIFEST tree the gate tests walk over."""
    _write_codemanifest(tmp_path, WALK_ROOT_WITH_CHILD)
    subpkg = tmp_path / "subpkg"
    subpkg.mkdir()
    _write_codemanifest(subpkg, WALK_CHILD)
