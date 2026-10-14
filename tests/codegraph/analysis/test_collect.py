"""Contract and logic tests for ``collect_facts`` of ``goga/codegraph/analysis``.

Routine under test (declared in ``goga/codegraph/analysis/CODEMANIFEST`` with
``location: collect.py``):

- ``collect_facts(files, language) -> list[FileFacts]`` — parse every source
  file once with the tree-sitter grammar of the language and collect its
  declarations, imports, exports, and module declaration.

Filesystem fixtures live on ``tmp_path`` (the autouse ``_isolate_cwd`` pins
the process CWD there); parsing itself is real — no mocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from goga.codegraph.facts import FileFacts


def _write(root: Path, rel: str, content: str) -> Path:
    """Write one fixture source file under ``root`` and return its relative path."""
    target = root / rel

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    return Path(rel)


class TestCollectFacts:
    """Facade and call contract of the single-pass fact collector."""

    def test_collect_facts_importable_from_facade(self) -> None:
        """``collect_facts`` is importable from the analysis cell facade."""
        from goga.codegraph.analysis import collect_facts  # noqa: F401

    def test_collect_facts_returns_file_facts_list(self, tmp_path: Path) -> None:
        """A minimal python file collects into one FileFacts record."""
        from goga.codegraph.analysis import collect_facts

        _write(tmp_path, "m.py", "def f():\n    return 1\n")

        facts = collect_facts(files=[Path("m.py")], language="python")

        assert isinstance(facts, list)
        assert all(isinstance(fact, FileFacts) for fact in facts)


class TestCollectFactsPython:
    """Design scenario: python declarations, imports, and __init__ bindings."""

    def test_collect_facts_python_declarations_imports_and_init_bindings(self, tmp_path: Path) -> None:
        """A package __init__ records definitions plus every top-level bound name."""
        from goga.codegraph.analysis import collect_facts

        _write(
            tmp_path,
            "pkg/__init__.py",
            "from .core import Engine\n"
            "from ..util import helper as util_helper\n"
            "import os\n"
            "import json.path\n"
            "\n"
            'VERSION = "1.0"\n'
            '_NAME = "hidden"\n'
            "\n"
            "\n"
            "def run(task: str) -> int:\n"
            "    return 0\n",
        )

        facts = collect_facts([Path("pkg/__init__.py")], "python")

        assert len(facts) == 1
        assert facts[0].path == Path("pkg/__init__.py")

        names = {declaration.name: declaration.is_public for declaration in facts[0].declarations}

        assert names["run"] is True
        assert names["_NAME"] is False
        assert names["VERSION"] is True

        imports = {(ref.specifier, tuple(ref.names), ref.is_relative, ref.is_wildcard) for ref in facts[0].imports}

        assert ("..util", ("helper",), True, False) in imports
        assert ("os", (), False, False) in imports
        assert ("json.path", (), False, False) in imports

        assert facts[0].exports == []
        assert facts[0].module == ""


class TestCollectFactsGolang:
    """Design scenario: golang exported package-scope declarations only."""

    def test_collect_facts_golang_exported_package_scope_only(self, tmp_path: Path) -> None:
        """Methods are receiver-scoped and never recorded as declarations."""
        from goga.codegraph.analysis import collect_facts

        _write(
            tmp_path,
            "store/user.go",
            "package store\n"
            "\n"
            "type User struct{ Name string }\n"
            "\n"
            "func NewUser() *User { return nil }\n"
            "\n"
            "func (u *User) Rename() {}\n"
            "\n"
            "var Default = 1\n"
            "\n"
            "const Limit = 9\n"
            "\n"
            "func internal() {}\n",
        )

        facts = collect_facts([Path("store/user.go")], "golang")

        public_names = {declaration.name for declaration in facts[0].declarations if declaration.is_public}

        assert public_names == {"User", "NewUser", "Default", "Limit"}

        all_names = {declaration.name for declaration in facts[0].declarations}

        assert "Rename" not in all_names
        assert any(
            declaration.name == "internal" and declaration.is_public is False for declaration in facts[0].declarations
        )


class TestCollectFactsGolangGrouped:
    """Design scenario: grouped var and const declaration blocks."""

    def test_collect_facts_golang_grouped_var_and_const(self, tmp_path: Path) -> None:
        """A ``var ( ... )`` block records every grouped spec, list wrapper unwrapped."""
        from goga.codegraph.analysis import collect_facts

        _write(
            tmp_path,
            "config/config.go",
            "package config\n"
            "\n"
            "var (\n"
            '\tName = "x"\n'
            "\tErrNotFound = 1\n"
            "\thidden = 2\n"
            ")\n"
            "\n"
            "const (\n"
            "\tLimit = 9\n"
            ")\n",
        )

        facts = collect_facts([Path("config/config.go")], "golang")

        names = {declaration.name: declaration.is_public for declaration in facts[0].declarations}

        assert names["Name"] is True
        assert names["ErrNotFound"] is True
        assert names["Limit"] is True
        assert names["hidden"] is False


class TestCollectFactsPythonWildcard:
    """Design scenario: python star imports record a base and a usage ref."""

    def test_collect_facts_python_wildcard_base_and_usage_refs(self, tmp_path: Path) -> None:
        """``from lib import *`` records a nameless base ref plus a usage ref."""
        from goga.codegraph.analysis import collect_facts

        _write(
            tmp_path,
            "app/main.py",
            "from lib import *\n"
            "\n"
            "def run():\n"
            "    return Tool()\n",
        )

        facts = collect_facts([Path("app/main.py")], "python")

        refs = [ref for ref in facts[0].imports if ref.specifier == "lib"]

        assert any(ref.names == [] and ref.is_wildcard and not ref.is_relative for ref in refs)
        assert any("Tool" in ref.names and ref.is_wildcard for ref in refs)


class TestCollectFactsPythonAliasedAndDecorated:
    """Design scenarios: aliased plain imports and decorated definitions."""

    def test_collect_facts_python_aliased_plain_import(self, tmp_path: Path) -> None:
        """``import json.path as j`` records the base specifier and no names."""
        from goga.codegraph.analysis import collect_facts

        _write(tmp_path, "app/main.py", "import json.path as j\n")

        facts = collect_facts([Path("app/main.py")], "python")

        ref = next(ref for ref in facts[0].imports if ref.specifier == "json.path")

        assert ref.names == []
        assert ref.is_wildcard is False

    def test_collect_facts_python_decorated_definition_and_tuple_targets(self, tmp_path: Path) -> None:
        """A decorated definition records its name; tuple targets bind in __init__."""
        from goga.codegraph.analysis import collect_facts

        _write(
            tmp_path,
            "pkg/__init__.py",
            "import os\n"
            "\n"
            "\n"
            "def deco(fn):\n"
            "    return fn\n"
            "\n"
            "\n"
            "@deco\n"
            "def run():\n"
            "    return 0\n"
            "\n"
            "\n"
            "a, b = 1, 2\n",
        )

        facts = collect_facts([Path("pkg/__init__.py")], "python")

        names = {declaration.name: declaration.is_public for declaration in facts[0].declarations}

        assert names["run"] is True
        assert names["a"] is True
        assert names["b"] is True


class TestCollectFactsJavascript:
    """Design scenario: javascript default pseudo-name and clause exports."""

    def test_collect_facts_javascript_default_pseudo_and_clause_exports(self, tmp_path: Path) -> None:
        """Default imports carry the literal ``default``; clause names export first."""
        from goga.codegraph.analysis import collect_facts

        _write(
            tmp_path,
            "api/index.js",
            'import render, { query as q, mutate } from "../db/index.js";\n'
            'import * as util from "./util.js";\n'
            "\n"
            "export function list() {}\n"
            "export default function render2() {}\n"
            "export { hidden as public2 };\n",
        )

        facts = collect_facts([Path("api/index.js")], "javascript")

        default_import = next(ref for ref in facts[0].imports if ref.names and ref.names[0] == "default")

        assert default_import.is_relative is True
        assert "mutate" in default_import.names

        namespace = next(ref for ref in facts[0].imports if ref.is_wildcard)

        assert namespace.names == []
        assert namespace.specifier == "./util.js"

        assert facts[0].exports == ["public2", "render2"]
        assert {declaration.name for declaration in facts[0].declarations if declaration.is_public} == {
            "list",
            "render2",
        }


class TestCollectFactsKotlin:
    """Design scenario: kotlin package module and visibility modifiers."""

    def test_collect_facts_kotlin_package_and_visibility(self, tmp_path: Path) -> None:
        """Implicit public stays public; internal is not; wildcards record no names."""
        from goga.codegraph.analysis import collect_facts

        _write(
            tmp_path,
            "com/example/tool.kt",
            "package com.example\n"
            "\n"
            "import com.other.Thing\n"
            "import com.other.*\n"
            "\n"
            "public class Tool\n"
            "internal class Hidden\n"
            "fun helper() {}\n",
        )

        facts = collect_facts([Path("com/example/tool.kt")], "kotlin")

        assert facts[0].module == "com.example"
        assert {declaration.name for declaration in facts[0].declarations if declaration.is_public} == {
            "Tool",
            "helper",
        }
        assert "Hidden" in {declaration.name for declaration in facts[0].declarations if not declaration.is_public}
        assert any(ref.specifier == "com.other.Thing" and ref.names == ["Thing"] for ref in facts[0].imports)
        assert any(ref.specifier == "com.other" and ref.is_wildcard for ref in facts[0].imports)


class TestCollectFactsSwift:
    """Design scenario: swift public/open declarations and used type names."""

    def test_collect_facts_swift_public_open_only_and_used_names(self, tmp_path: Path) -> None:
        """Only public and open declarations are public; usages collect type names."""
        from goga.codegraph.analysis import collect_facts

        _write(
            tmp_path,
            "App/main.swift",
            "import Foundation\n"
            "\n"
            "public struct Client {}\n"
            "open class Base {}\n"
            "internal struct Hidden {}\n"
            "struct ImplicitInternal {}\n"
            "\n"
            "func use(_ c: Client, _ b: Base) {}\n",
        )

        facts = collect_facts([Path("App/main.swift")], "swift")

        assert {declaration.name for declaration in facts[0].declarations if declaration.is_public} == {
            "Client",
            "Base",
        }

        module_ref = next(ref for ref in facts[0].imports if ref.specifier == "Foundation")

        assert module_ref.names == []

        usage = next(ref for ref in facts[0].imports if ref.specifier == "")

        assert set(usage.names) >= {"Client", "Base"}


class TestCollectFactsOrderAndErrors:
    """Design scenarios: input order preservation and the fail-closed parse."""

    def test_collect_facts_preserves_input_order(self, tmp_path: Path) -> None:
        """The facts order follows the files order, not the walk order."""
        from goga.codegraph.analysis import collect_facts

        for name in ("b.py", "a.py", "c.py"):
            _write(tmp_path, name, "def x():\n    pass\n")

        facts = collect_facts([Path("b.py"), Path("a.py"), Path("c.py")], "python")

        assert [fact.path for fact in facts] == [Path("b.py"), Path("a.py"), Path("c.py")]

    def test_collect_facts_unparseable_file_fails_closed(self, tmp_path: Path) -> None:
        """A syntax error raises ValueError naming the file."""
        from goga.codegraph.analysis import collect_facts

        _write(tmp_path, "broken.py", "def f(:")

        with pytest.raises(ValueError, match=r"broken\.py"):
            collect_facts([Path("broken.py")], "python")

    def test_collect_facts_rejects_unknown_language(self) -> None:
        """An unsupported language fails with ValueError naming it."""
        from goga.codegraph.analysis import collect_facts

        with pytest.raises(ValueError, match="rust"):
            collect_facts([], "rust")
