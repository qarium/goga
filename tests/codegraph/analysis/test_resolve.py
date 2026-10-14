"""Contract and logic tests for ``resolve_links`` of ``goga/codegraph/analysis``.

Routine under test (declared in ``goga/codegraph/analysis/CODEMANIFEST`` with
``location: resolve.py``):

- ``resolve_links(units, facts, language, root) -> list[CellLink]`` — resolve
  every imported or used name to its exact defining unit and aggregate the
  kept resolutions into one link per unit pair.

Filesystem fixtures live on ``tmp_path`` (the autouse ``_isolate_cwd`` pins
the process CWD there); units and facts are built through the earlier stages
inside the tests — no mocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from goga.codegraph.facts import CellLink


def _write(root: Path, rel: str, content: str) -> Path:
    """Write one fixture source file under ``root`` and return its relative path."""
    target = root / rel

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    return Path(rel)


def _pipeline(files: list[Path], language: str, root: Path) -> tuple[list, list]:
    """Run collect and derive over ``files`` and return (units, facts)."""
    from goga.codegraph.analysis import collect_facts, derive_units

    facts = collect_facts(files, language)
    units = derive_units(facts, language)

    return units, facts


class TestResolveLinks:
    """Facade and call contract of the link resolution stage."""

    def test_resolve_links_importable_from_facade(self) -> None:
        """``resolve_links`` is importable from the analysis cell facade."""
        from goga.codegraph.analysis import resolve_links  # noqa: F401

    def test_resolve_links_returns_cell_link_list(self) -> None:
        """Empty inputs resolve to an empty link list."""
        from goga.codegraph.analysis import resolve_links

        links = resolve_links(units=[], facts=[], language="python", root=Path.cwd())

        assert isinstance(links, list)
        assert all(isinstance(link, CellLink) for link in links)
        assert links == []

    def test_resolve_links_rejects_unknown_language(self) -> None:
        """An unsupported language fails with ValueError naming it."""
        from goga.codegraph.analysis import resolve_links

        with pytest.raises(ValueError, match="rust"):
            resolve_links(units=[], facts=[], language="rust", root=Path.cwd())


class TestResolveLinksPython:
    """Design scenario: python absolute, relative, and plain import resolution."""

    def test_resolve_links_python_absolute_and_relative_and_plain(self, tmp_path: Path) -> None:
        """Absolute, relative, and plain imports resolve through the module index."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, ".goga/config.yml", "language: python\n")
        _write(
            tmp_path,
            "src/alpha/__init__.py",
            "from beta import Tool\n"
            "import gamma.deep\n"
            "from . import local\n"
            "\n"
            "def use():\n"
            "    return gamma.deep.dive()\n",
        )
        _write(tmp_path, "src/beta/__init__.py", '__all__ = ["Tool"]\nfrom .impl import Tool\n')
        _write(tmp_path, "src/beta/impl.py", "class Tool:\n    pass\n")
        _write(tmp_path, "src/gamma/__init__.py", "")
        _write(tmp_path, "src/gamma/deep.py", "def dive():\n    pass\n")

        files = [
            Path("src/alpha/__init__.py"),
            Path("src/beta/__init__.py"),
            Path("src/beta/impl.py"),
            Path("src/gamma/__init__.py"),
            Path("src/gamma/deep.py"),
        ]
        facts = collect_facts(files, "python")
        units = derive_units(facts, "python")

        links = resolve_links(units, facts, "python", root=tmp_path)

        assert links == [CellLink(source=Path("src/alpha"), target=Path("src/beta"), types=["Tool"])]

    def test_resolve_links_python_external_names_silent(self, tmp_path: Path) -> None:
        """External modules and self-imports resolve to no link and no error."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "app/__init__.py", "from .impl import S\n")
        _write(
            tmp_path,
            "app/impl.py",
            "import os.path\n\nfrom collections import OrderedDict\n\n\nclass S:\n    pass\n",
        )

        files = [Path("app/__init__.py"), Path("app/impl.py")]
        facts = collect_facts(files, "python")
        units = derive_units(facts, "python")

        links = resolve_links(units, facts, "python", root=tmp_path)

        assert links == []

    def test_resolve_links_python_star_import_links_used_names(self, tmp_path: Path) -> None:
        """A star import links the actually-used facade names only."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "lib/__init__.py", "class Tool:\n    pass\n")
        _write(tmp_path, "app/__init__.py", "from lib import *\n\n\ndef run():\n    return Tool()\n")

        files = [Path("lib/__init__.py"), Path("app/__init__.py")]
        facts = collect_facts(files, "python")
        units = derive_units(facts, "python")

        links = resolve_links(units, facts, "python", root=tmp_path)

        assert links == [CellLink(source=Path("app"), target=Path("lib"), types=["Tool"])]

    def test_resolve_links_python_plain_import_member_usage(self, tmp_path: Path) -> None:
        """``import lib`` plus ``lib.tool()`` links through the usage expansion."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "lib/__init__.py", "def tool():\n    return 1\n")
        _write(tmp_path, "app/__init__.py", "import lib\n\n\ndef run():\n    return lib.tool()\n")

        files = [Path("lib/__init__.py"), Path("app/__init__.py")]
        facts = collect_facts(files, "python")
        units = derive_units(facts, "python")

        links = resolve_links(units, facts, "python", root=tmp_path)

        assert links == [CellLink(source=Path("app"), target=Path("lib"), types=["tool"])]

    def test_resolve_links_python_relative_level_two(self, tmp_path: Path) -> None:
        """``from ..lib import Tool`` resolves two levels up the tree."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "pkg/lib/__init__.py", "class Tool:\n    pass\n")
        _write(tmp_path, "pkg/app/__init__.py", "from ..lib import Tool\n")

        files = [Path("pkg/lib/__init__.py"), Path("pkg/app/__init__.py")]
        facts = collect_facts(files, "python")
        units = derive_units(facts, "python")

        links = resolve_links(units, facts, "python", root=tmp_path)

        assert links == [CellLink(source=Path("pkg/app"), target=Path("pkg/lib"), types=["Tool"])]

    def test_resolve_links_python_bare_relative_at_root_drops_silently(self, tmp_path: Path) -> None:
        """A relative import past the project root produces no link and no error."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "pkg/__init__.py", "from .. import helper\n")

        files = [Path("pkg/__init__.py")]
        facts = collect_facts(files, "python")
        units = derive_units(facts, "python")

        links = resolve_links(units, facts, "python", root=tmp_path)

        assert links == []

    def test_resolve_links_non_cell_source_no_link(self, tmp_path: Path) -> None:
        """A non-cell importing unit produces no link and no error."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "api/__init__.py", "from .impl import S\n")
        _write(tmp_path, "api/impl.py", "class S:\n    pass\n")
        _write(tmp_path, "tools/__init__.py", "")
        _write(tmp_path, "tools/mod.py", "from api import S\n")

        files = [Path("api/__init__.py"), Path("api/impl.py"), Path("tools/__init__.py"), Path("tools/mod.py")]
        facts = collect_facts(files, "python")
        units = derive_units(facts, "python")

        links = resolve_links(units, facts, "python", root=tmp_path)

        assert links == []


class TestResolveLinksGolang:
    """Design scenario: golang module-mode resolution through go.mod."""

    def test_resolve_links_golang_module_mode(self, tmp_path: Path) -> None:
        """Imports under the go.mod module path resolve; external ones drop."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "go.mod", "module example.com/app\n")
        _write(
            tmp_path,
            "store/user.go",
            "package store\n\nfunc NewUser() *User { return nil }\n\ntype User struct{}\n",
        )
        _write(
            tmp_path,
            "main.go",
            'package main\n\nimport "example.com/app/store"\nimport "fmt"\n\nfunc Run() { store.NewUser() }\n',
        )

        files = [Path("main.go"), Path("store/user.go")]
        facts = collect_facts(files, "golang")
        units = derive_units(facts, "golang")

        links = resolve_links(units, facts, "golang", root=tmp_path)

        assert len(links) == 1
        assert links[0].target == Path("store")
        assert links[0].types == ["NewUser"]

    def test_resolve_links_golang_grouped_var_declaration_links(self, tmp_path: Path) -> None:
        """A grouped ``var ( ... )`` export resolves like a single var."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "go.mod", "module example.com/app\n")
        _write(tmp_path, "store/config.go", 'package store\n\nvar (\n\tName = "x"\n)\n')
        _write(
            tmp_path,
            "cmd/main.go",
            'package main\n\nimport "example.com/app/store"\n\nfunc Run() { _ = store.Name }\n',
        )

        files = [Path("cmd/main.go"), Path("store/config.go")]
        facts = collect_facts(files, "golang")
        units = derive_units(facts, "golang")

        links = resolve_links(units, facts, "golang", root=tmp_path)

        assert links == [CellLink(source=Path("cmd"), target=Path("store"), types=["Name"])]

    def test_resolve_links_golang_without_go_mod_drops_silently(self, tmp_path: Path) -> None:
        """Without go.mod every import is external — no link and no error."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "store/user.go", "package store\n\nfunc NewUser() {}\n")
        _write(
            tmp_path,
            "main.go",
            'package main\n\nimport "example.com/app/store"\n\nfunc Run() { store.NewUser() }\n',
        )

        files = [Path("main.go"), Path("store/user.go")]
        facts = collect_facts(files, "golang")
        units = derive_units(facts, "golang")

        links = resolve_links(units, facts, "golang", root=tmp_path)

        assert links == []

    def test_resolve_links_golang_aliased_import_no_link(self, tmp_path: Path) -> None:
        """An aliased import records no usage ref and links nowhere (v1 limitation)."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "go.mod", "module example.com/app\n")
        _write(tmp_path, "store/user.go", "package store\n\nfunc NewUser() {}\n")
        _write(
            tmp_path,
            "main.go",
            'package main\n\nimport store2 "example.com/app/store"\n\nfunc Run() { store2.NewUser() }\n',
        )

        files = [Path("main.go"), Path("store/user.go")]
        facts = collect_facts(files, "golang")
        units = derive_units(facts, "golang")

        links = resolve_links(units, facts, "golang", root=tmp_path)

        assert links == []


class TestResolveLinksJavascript:
    """Design scenario: javascript relative specifiers and the default pseudo-name."""

    def test_resolve_links_javascript_relative_default_and_directory(self, tmp_path: Path) -> None:
        """A mixed default-and-named import links both mapped names."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "db/index.js", "export function query() {}\n\nexport default function conn() {}\n")
        _write(tmp_path, "svc/index.js", 'export { run } from "./a.js";\n')
        _write(
            tmp_path,
            "svc/a.js",
            'import c, { query } from "../db/index.js";\n\nexport function run() {\n    c();\n    query();\n}\n',
        )

        files = [Path("db/index.js"), Path("svc/index.js"), Path("svc/a.js")]
        facts = collect_facts(files, "javascript")
        units = derive_units(facts, "javascript")

        links = resolve_links(units, facts, "javascript", root=tmp_path)

        assert links == [CellLink(source=Path("svc"), target=Path("db"), types=["conn", "query"])]

    def test_resolve_links_javascript_extensionless_and_directory_forms(self, tmp_path: Path) -> None:
        """``../db`` resolves to ``db/index.js`` and ``../db/conn`` to ``db/conn.js``."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "db/index.js", 'export function query() {}\nexport { connect } from "./conn.js";\n')
        _write(tmp_path, "db/conn.js", "export function connect() {}\n")
        _write(
            tmp_path,
            "svc/index.js",
            'import { query } from "../db";\n'
            'import { connect } from "../db/conn";\n'
            "\n"
            "export function run() {\n"
            "    query();\n"
            "    connect();\n"
            "}\n",
        )

        files = [Path("db/index.js"), Path("db/conn.js"), Path("svc/index.js")]
        facts = collect_facts(files, "javascript")
        units = derive_units(facts, "javascript")

        links = resolve_links(units, facts, "javascript", root=tmp_path)

        assert links == [CellLink(source=Path("svc"), target=Path("db"), types=["connect", "query"])]

    def test_resolve_links_javascript_directory_form_prefers_index(self, tmp_path: Path) -> None:
        """A trailing-slash specifier resolves to ``index.js``, never the sibling file."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "lib.js", "export function stray() {}\n")
        _write(tmp_path, "lib/index.js", "export function used() {}\n")
        _write(
            tmp_path,
            "svc/index.js",
            'import { used } from "../lib/";\n\nexport function run() {\n    used();\n}\n',
        )

        files = [Path("lib.js"), Path("lib/index.js"), Path("svc/index.js")]
        facts = collect_facts(files, "javascript")
        units = derive_units(facts, "javascript")

        links = resolve_links(units, facts, "javascript", root=tmp_path)

        assert links == [CellLink(source=Path("svc"), target=Path("lib"), types=["used"])]

    def test_resolve_links_javascript_root_form_specifiers_link_root_unit(self, tmp_path: Path) -> None:
        """``..`` and ``.`` normalizing to the root resolve to its ``index.js``, never crash."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "index.js", "export function helper() {}\n")
        _write(
            tmp_path,
            "svc/index.js",
            'import { helper } from "..";\n\nexport function run() {\n    helper();\n}\n',
        )

        files = [Path("index.js"), Path("svc/index.js")]
        facts = collect_facts(files, "javascript")
        units = derive_units(facts, "javascript")

        links = resolve_links(units, facts, "javascript", root=tmp_path)

        assert links == [CellLink(source=Path("svc"), target=Path(), types=["helper"])]

    def test_resolve_links_javascript_namespace_member_usage(self, tmp_path: Path) -> None:
        """``import * as util`` plus ``util.ping()`` links the accessed member."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(tmp_path, "util/index.js", "export function ping() {}\n")
        _write(
            tmp_path,
            "svc/index.js",
            'import * as util from "../util/index.js";\n\nexport function run() {\n    util.ping();\n}\n',
        )

        files = [Path("util/index.js"), Path("svc/index.js")]
        facts = collect_facts(files, "javascript")
        units = derive_units(facts, "javascript")

        links = resolve_links(units, facts, "javascript", root=tmp_path)

        assert links == [CellLink(source=Path("svc"), target=Path("util"), types=["ping"])]


class TestResolveLinksKotlin:
    """Kotlin package-map resolution for named and wildcard imports."""

    def test_resolve_links_kotlin_package_map_named_and_wildcard(self, tmp_path: Path) -> None:
        """Named imports resolve by package and facade; wildcards expand by usage."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(
            tmp_path,
            "com/example/tool.kt",
            "package com.example\n\nimport com.other.Thing\nimport com.other.*\n\nfun make(): Thing {\n"
            "    return Thing()\n}\n",
        )
        _write(
            tmp_path,
            "com/other/lib.kt",
            "package com.other\n\npublic class Thing\n\ninternal class Hidden\n",
        )

        files = [Path("com/example/tool.kt"), Path("com/other/lib.kt")]
        facts = collect_facts(files, "kotlin")
        units = derive_units(facts, "kotlin")

        links = resolve_links(units, facts, "kotlin", root=tmp_path)

        assert links == [CellLink(source=Path("com/example"), target=Path("com/other"), types=["Thing"])]

    def test_resolve_links_kotlin_wildcard_only_import(self, tmp_path: Path) -> None:
        """A wildcard import alone expands by usage and links the used type."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(
            tmp_path,
            "com/example/tool.kt",
            "package com.example\n\nimport com.other.*\n\nfun make(): Thing {\n    return Thing()\n}\n",
        )
        _write(tmp_path, "com/other/lib.kt", "package com.other\n\npublic class Thing\n")

        files = [Path("com/example/tool.kt"), Path("com/other/lib.kt")]
        facts = collect_facts(files, "kotlin")
        units = derive_units(facts, "kotlin")

        links = resolve_links(units, facts, "kotlin", root=tmp_path)

        assert links == [CellLink(source=Path("com/example"), target=Path("com/other"), types=["Thing"])]


class TestResolveLinksSwift:
    """Design scenario: swift type-name uniqueness resolution."""

    def test_resolve_links_swift_unique_name_links(self, tmp_path: Path) -> None:
        """A type name unique in the project resolves to its defining unit."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(
            tmp_path,
            "ui/main.swift",
            "import Foundation\n\npublic struct App {}\n\nfunc build() -> Client {\n    return Client()\n}\n",
        )
        _write(tmp_path, "core/main.swift", "public struct Client {}\n")

        files = [Path("ui/main.swift"), Path("core/main.swift")]
        facts = collect_facts(files, "swift")
        units = derive_units(facts, "swift")

        links = resolve_links(units, facts, "swift", root=tmp_path)

        assert links == [CellLink(source=Path("ui"), target=Path("core"), types=["Client"])]

    def test_resolve_links_swift_ambiguous_name_no_link(self, tmp_path: Path) -> None:
        """A type name defined by two units is ambiguous and links nowhere."""
        from goga.codegraph.analysis import collect_facts, derive_units, resolve_links

        _write(
            tmp_path,
            "ui/main.swift",
            "import Foundation\n\npublic struct App {}\n\nfunc build() -> Client {\n    return Client()\n}\n",
        )
        _write(tmp_path, "core1/main.swift", "public struct Client {}\n")
        _write(tmp_path, "core2/main.swift", "public struct Client {}\n")

        files = [Path("ui/main.swift"), Path("core1/main.swift"), Path("core2/main.swift")]
        facts = collect_facts(files, "swift")
        units = derive_units(facts, "swift")

        links = resolve_links(units, facts, "swift", root=tmp_path)

        assert links == []
