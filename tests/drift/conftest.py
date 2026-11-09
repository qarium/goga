"""Shared fixtures and planted-project scaffolding of the drift zone tests.

Every test of this zone pins the package environment empty (the autouse
``_empty_package_environment`` pattern of ``tests/schema/test_schema.py``) —
the schema producer delivers its checkpoints through the real registry, so
an unpinned environment would make the declared view depend on the
machine's installed ``goga_tool_*`` packages.

The planted projects mirror the design's layouts: the four-kinds project
(every discrepancy direction exactly once), the healthy-plus project (the
``depends_on`` asymmetry between manifest-declared and code-resolved
dependencies), the nested-depth project (the ``max_depth`` scope), the
stale-importer project (a real discrepancy on a cell surviving the
``depends_on`` filter), and the root-manifest project (the ``.`` root cell
of a root CODEMANIFEST). The projects live in ``tmp_path`` — the process
CWD the shared ``_isolate_cwd`` fixture pins — and carry ``.goga/config.yml``
with ``language: python``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

_MANIFEST_TEMPLATE = """\
Usages: {{}}

Annotations: ""

---
{body}
---
Author: Test
CreatedAt: 01/01/01
Description: {description}
"""

_LOCATIONLESS_MANIFEST = """\
Usages: {}

Annotations: ""

---
"thing()":
  annotations: |
    A routine without a location

---
Author: Test
CreatedAt: 01/01/01
Description: bad
"""


@pytest.fixture(autouse=True)
def _empty_package_environment(pin_package_environment) -> None:
    """Pin the package environment empty for every test of this zone.

    Every non-empty tree the schema producer builds delivers the checkpoint
    through the real registry, so an unpinned environment would make the
    declared view depend on the machine's installed ``goga_tool_*``
    packages.
    """
    pin_package_environment({})


def _write_codemanifest(directory: Path, declarations: list[str]) -> None:
    """Write a minimal routine-declaring CODEMANIFEST into ``directory``."""
    body = "\n".join(f'"{name}()":\n  location: impl.py\n  annotations: |\n    A test routine' for name in declarations)
    manifest = _MANIFEST_TEMPLATE.format(body=body, description=directory.name)
    (directory / "CODEMANIFEST").write_text(manifest, encoding="utf-8")


def _write_package(root: Path, name: str, definitions: str, declarations: list[str] | None = None) -> None:
    """Write one python package — an ``__init__.py`` and an optional manifest."""
    package = root / name
    package.mkdir()
    (package / "__init__.py").write_text(definitions, encoding="utf-8")

    if declarations is not None:
        _write_codemanifest(package, declarations)


def _write_config(root: Path, language: str = "python", lint_ignore: list[str] | None = None) -> None:
    """Write a minimal ``.goga/config.yml`` — the language plus an optional lint ignore list."""
    goga_dir = root / ".goga"
    goga_dir.mkdir(exist_ok=True)
    lint = ""
    if lint_ignore is not None:
        listed = "".join(f"    - {entry}\n" for entry in lint_ignore)
        lint = f"lint:\n  ignore:\n{listed}"
    (goga_dir / "config.yml").write_text(f"language: {language}\n{lint}", encoding="utf-8")


def _plant_four_kinds(root: Path) -> None:
    """Plant the four-kinds project — every discrepancy direction exactly once."""
    _write_config(root)

    _write_package(root, "lib", "def thing() -> None:\n    return\n", ["thing"])

    _write_package(
        root,
        "mix",
        "def run() -> None:\n    return\n\n\ndef helper2() -> None:\n    return\n",
        ["run", "stale"],
    )

    _write_package(root, "extra", "def helper() -> None:\n    return\n")

    ghost = root / "ghost"
    ghost.mkdir()
    _write_codemanifest(ghost, ["phantom"])


def _plant_healthy_plus(root: Path) -> None:
    """Plant the healthy-plus project — agreeing views with an import-only dependency."""
    _write_config(root)

    _write_package(root, "lib", "def thing() -> None:\n    return\n", ["thing"])

    mix = root / "mix"
    mix.mkdir()
    (mix / "__init__.py").write_text("def run() -> None:\n    return\n", encoding="utf-8")
    (mix / "impl.py").write_text(
        "from lib import thing\n\n\ndef use() -> None:\n    thing()\n",
        encoding="utf-8",
    )
    _write_codemanifest(mix, ["run"])


def _plant_stale_importer(root: Path) -> None:
    """Plant the stale-importer project — a type-level drift on a cell importing the filter target."""
    _write_config(root)

    _write_package(root, "lib", "def thing() -> None:\n    return\n", ["thing"])

    mix = root / "mix"
    mix.mkdir()
    (mix / "__init__.py").write_text("def run() -> None:\n    return\n", encoding="utf-8")
    (mix / "impl.py").write_text(
        "from lib import thing\n\n\ndef use() -> None:\n    thing()\n",
        encoding="utf-8",
    )
    _write_codemanifest(mix, ["run", "stale"])


def _plant_root_manifest(root: Path) -> None:
    """Plant the root-manifest project — a root CODEMANIFEST beside a manifest-less package."""
    _write_config(root)

    _write_codemanifest(root, ["root"])
    _write_package(root, "pkg", "def helper() -> None:\n    return\n")


def _plant_nested_depth(root: Path) -> None:
    """Plant the nested-depth project — one type-level drift on the nested ``a/b`` cell."""
    _write_config(root)

    outer = root / "a"
    outer.mkdir()
    (outer / "__init__.py").write_text("def root() -> None:\n    return\n", encoding="utf-8")
    _write_codemanifest(outer, ["root"])

    inner = outer / "b"
    inner.mkdir()
    (inner / "__init__.py").write_text("def run() -> None:\n    return\n", encoding="utf-8")
    _write_codemanifest(inner, ["run", "stale"])


def _plant_locationless(root: Path) -> None:
    """Plant the rule-violating project — one routine declared without a location."""
    _write_config(root)

    bad = root / "bad"
    bad.mkdir()
    (bad / "CODEMANIFEST").write_text(_LOCATIONLESS_MANIFEST, encoding="utf-8")


def _plant_ignored_dirty_tree(root: Path) -> None:
    """Plant a healthy project whose ``vendor/`` tree carries a rule-violating manifest.

    The config's lint ignore list excludes ``vendor/`` — the dirty tree
    must contribute no cells, no errors, and no entries to either view.
    """
    _write_config(root, lint_ignore=["vendor/"])

    _write_package(root, "pkg", "def run() -> None:\n    return\n", ["run"])

    vendor = root / "vendor"
    vendor.mkdir()
    (vendor / "CODEMANIFEST").write_text(_LOCATIONLESS_MANIFEST, encoding="utf-8")


def _plant_ignored_agreeing_vendor(root: Path) -> None:
    """Plant a healthy project plus a valid manifest-and-code ``vendor/`` tree under lint ignore.

    Both views exclude ``vendor/`` — the agreeing tree must surface as
    no phantom schema_only entry.
    """
    _write_config(root, lint_ignore=["vendor/"])

    _write_package(root, "pkg", "def run() -> None:\n    return\n", ["run"])
    _write_package(root, "vendor", "def vend() -> None:\n    return\n", ["vend"])


def _snapshot_tree(root: Path) -> dict[str, str]:
    """Snapshot the project tree — relative file paths to content hashes."""
    snapshot: dict[str, str] = {}

    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot[path.relative_to(root).as_posix()] = digest

    return snapshot
