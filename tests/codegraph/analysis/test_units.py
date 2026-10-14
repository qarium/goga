"""Contract and logic tests for ``derive_units`` of ``goga/codegraph/analysis``.

Routine under test (declared in ``goga/codegraph/analysis/CODEMANIFEST`` with
``location: units.py``):

- ``derive_units(facts, language) -> list[Unit]`` — pure grouping of the
  collected file facts into language units with their facade types; reads no
  files.

Filesystem fixtures live on ``tmp_path`` (the autouse ``_isolate_cwd`` pins
the process CWD there); grouping itself is pure logic — no mocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from goga.codegraph.facts import Unit


def _write(root: Path, rel: str, content: str) -> Path:
    """Write one fixture source file under ``root`` and return its relative path."""
    target = root / rel

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    return Path(rel)


class TestDeriveUnits:
    """Facade and call contract of the unit derivation stage."""

    def test_derive_units_importable_from_facade(self) -> None:
        """``derive_units`` is importable from the analysis cell facade."""
        from goga.codegraph.analysis import derive_units  # noqa: F401

    def test_derive_units_returns_unit_list(self) -> None:
        """Empty facts derive no units."""
        from goga.codegraph.analysis import derive_units

        units = derive_units(facts=[], language="python")

        assert isinstance(units, list)
        assert all(isinstance(unit, Unit) for unit in units)
        assert units == []

    def test_derive_units_rejects_unknown_language(self) -> None:
        """An unsupported language fails with ValueError naming it."""
        from goga.codegraph.analysis import derive_units

        with pytest.raises(ValueError, match="rust"):
            derive_units(facts=[], language="rust")


class TestDeriveUnitsPython:
    """Design scenarios: python package rule and facade derivation."""

    def test_derive_units_python_package_rule_and_facade(self, tmp_path: Path) -> None:
        """__all__ wins as the facade; only package directories become units."""
        from goga.codegraph.analysis import collect_facts, derive_units

        _write(tmp_path, "app/__init__.py", '__all__ = ["Service", "run"]\n')
        _write(tmp_path, "app/core.py", "class Service:\n    pass\n\n\ndef run():\n    pass\n")
        _write(tmp_path, "app/sub/__init__.py", "")
        _write(tmp_path, "app/sub/deep.py", "def helper():\n    pass\n")
        _write(tmp_path, "loose/mod.py", "def anything():\n    pass\n")

        files = [
            Path("app/__init__.py"),
            Path("app/core.py"),
            Path("app/sub/__init__.py"),
            Path("app/sub/deep.py"),
            Path("loose/mod.py"),
        ]
        facts = collect_facts(files, "python")
        units = derive_units(facts, "python")

        assert [unit.path for unit in units] == [Path("app"), Path("app/sub")]

        app_unit = units[0]

        assert app_unit.facade == ["Service", "run"]
        assert app_unit.is_cell is True
        assert app_unit.files == [Path("app/__init__.py"), Path("app/core.py")]

        sub = units[1]

        assert sub.is_cell is False
        assert sub.facade == []
        assert not any(unit.path == Path("loose") for unit in units)

    def test_derive_units_python_facade_fallback_bindings(self, tmp_path: Path) -> None:
        """Without __all__ the facade falls back to public __init__ bindings."""
        from goga.codegraph.analysis import collect_facts, derive_units

        _write(
            tmp_path,
            "app/__init__.py",
            "from .core import Engine\n\nVERSION = 2\n\n\ndef boot():\n    pass\n\n_priv = 1\n",
        )

        facts = collect_facts([Path("app/__init__.py")], "python")
        units = derive_units(facts, "python")

        app_unit = units[0]

        assert app_unit.facade == ["Engine", "VERSION", "boot"]
        assert app_unit.is_cell is True


class TestDeriveUnitsLanguages:
    """Unit and facade rules of the non-python languages."""

    def test_derive_units_golang_directory_rule_and_exported_union(self, tmp_path: Path) -> None:
        """Every directory with sources is a unit; the facade unions exported names."""
        from goga.codegraph.analysis import collect_facts, derive_units

        _write(tmp_path, "main.go", "package main\n\nfunc Run() {}\n")
        _write(
            tmp_path,
            "store/user.go",
            "package store\n\nfunc NewUser() *User { return nil }\n\ntype User struct{}\n\nfunc internal() {}\n",
        )

        facts = collect_facts([Path("main.go"), Path("store/user.go")], "golang")
        units = derive_units(facts, "golang")

        assert [unit.path for unit in units] == [Path(), Path("store")]
        assert units[0].facade == ["Run"]
        assert units[0].is_cell is True
        assert units[1].facade == ["NewUser", "User"]
        assert units[1].files == [Path("store/user.go")]

    def test_derive_units_javascript_index_rule_and_export_union(self, tmp_path: Path) -> None:
        """Only directories with index.js are units; the facade unions public names and exports."""
        from goga.codegraph.analysis import collect_facts, derive_units

        _write(tmp_path, "db/index.js", "export function query() {}\n\nexport default function conn() {}\n")
        _write(tmp_path, "svc/a.js", "export function run() {}\n")

        facts = collect_facts([Path("db/index.js"), Path("svc/a.js")], "javascript")
        units = derive_units(facts, "javascript")

        assert [unit.path for unit in units] == [Path("db")]
        assert units[0].facade == ["conn", "query"]
        assert units[0].is_cell is True
        assert units[0].files == [Path("db/index.js")]

    def test_derive_units_kotlin_public_declarations_union(self, tmp_path: Path) -> None:
        """The kotlin facade unions the public declarations of the unit files."""
        from goga.codegraph.analysis import collect_facts, derive_units

        _write(
            tmp_path,
            "com/example/tool.kt",
            "package com.example\n\npublic class Tool\n\ninternal class Hidden\n\nfun helper() {}\n",
        )

        facts = collect_facts([Path("com/example/tool.kt")], "kotlin")
        units = derive_units(facts, "kotlin")

        assert [unit.path for unit in units] == [Path("com/example")]
        assert units[0].facade == ["Tool", "helper"]
        assert units[0].is_cell is True

    def test_derive_units_swift_public_and_open_only(self, tmp_path: Path) -> None:
        """The swift facade keeps only public and open declarations."""
        from goga.codegraph.analysis import collect_facts, derive_units

        _write(
            tmp_path,
            "App/main.swift",
            "public struct Client {}\n\nopen class Base {}\n\ninternal struct Hidden {}\n",
        )

        facts = collect_facts([Path("App/main.swift")], "swift")
        units = derive_units(facts, "swift")

        assert [unit.path for unit in units] == [Path("App")]
        assert units[0].facade == ["Base", "Client"]
        assert units[0].is_cell is True
