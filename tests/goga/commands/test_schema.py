from __future__ import annotations

import json
from pathlib import Path

import click
from click.testing import CliRunner
from goga.cli import app
from goga.commands import schema
from goga.commands.schema import schema as schema_cmd

from tests.conftest import cwd as _cwd


def _run_schema(*args):
    runner = CliRunner()
    return runner.invoke(app, ["schema", *args])


def _write_codemanifest(directory: Path, content: str) -> None:
    (directory / "CODEMANIFEST").write_text(content, encoding="utf-8")


ROOT_WITH_CHILD = """\
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

CHILD = """\
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

STANDALONE = """\
Usages: {}

Annotations: ""

---
"StandaloneEntity()":
  location: entity.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Standalone
"""

ERROR_IMPORTS = """\
Imports: []

Annotations: ""

---
"ErrorEntity()":
  location: entity.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Error test
"""

DEDUP_ROOT = """\
Imports:
  - Types:
      - HelperA
    From: subpkg
  - Types:
      - HelperB
    From: subpkg

Usages: {}

Annotations: |
  Uses `HelperA` and `HelperB` here

---
"MyClass()":
  location: myclass.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Dedup test
"""

DEDUP_CHILD = """\
Usages: {}

Annotations: ""

---
"HelperA()":
  location: helper_a.py
  annotations: ""

"HelperB()":
  location: helper_b.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Sub package
"""

UNICODE = """\
Usages: {}

Annotations: ""

---
"UnicodeEntity()":
  location: entity.py
  annotations: |
    Кирилическое описание

---
Author: Test
CreatedAt: 01/01/01
Description: Тест с кириллицей
"""


# --- Contract tests ---


class TestFacadeAvailability:
    def test_import_schema_from_commands(self) -> None:
        assert schema is not None

    def test_schema_is_click_command(self) -> None:
        assert isinstance(schema_cmd, click.Command)


class TestApiShape:
    def test_schema_has_callback(self) -> None:
        assert schema_cmd.callback is not None

    def test_schema_has_cells_argument(self) -> None:
        param_names = [p.name for p in schema_cmd.params]
        assert "cells" in param_names

    def test_schema_cells_has_nargs_minus_one(self) -> None:
        cells_param = next(p for p in schema_cmd.params if p.name == "cells")
        assert cells_param.nargs == -1

    def test_schema_has_max_depth_option(self) -> None:
        param_names = [p.name for p in schema_cmd.params]
        assert "max_depth" in param_names

    def test_schema_max_depth_type_is_int(self) -> None:
        max_depth_param = next(p for p in schema_cmd.params if p.name == "max_depth")
        assert max_depth_param.type is click.INT

    def test_schema_has_depends_on_option(self) -> None:
        param_names = [p.name for p in schema_cmd.params]
        assert "depends_on" in param_names

    def test_schema_depends_on_is_multiple(self) -> None:
        depends_on_param = next(p for p in schema_cmd.params if p.name == "depends_on")
        assert depends_on_param.multiple is True


# --- Behavioural tests ---


def test_schema_full_tree(tmp_path) -> None:
    _write_codemanifest(tmp_path, ROOT_WITH_CHILD)
    (tmp_path / ".usages").mkdir()
    (tmp_path / ".usages" / "spec.md").write_text("test", encoding="utf-8")

    subpkg = tmp_path / "subpkg"
    subpkg.mkdir()
    _write_codemanifest(subpkg, CHILD)
    (subpkg / ".usages").mkdir()
    (subpkg / ".usages" / "helper.md").write_text("test", encoding="utf-8")

    with _cwd(tmp_path):
        result = _run_schema()

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert data[0]["cell"] == "."
    assert len(data[0]["children"]) == 1
    assert data[0]["children"][0]["cell"] == "subpkg"
    assert "spec.md" in data[0]["usages"]
    assert "subpkg" in data[0]["dependencies"]
    assert data[0]["dependencies"]["subpkg"]["types"] == ["Helper"]
    assert data[0]["dependencies"]["subpkg"]["usages"] == []
    assert data[0]["types"] == ["MyClass"]
    assert "helper.md" in data[0]["children"][0]["usages"]


def test_schema_with_max_depth(tmp_path) -> None:
    _write_codemanifest(tmp_path, ROOT_WITH_CHILD)
    subpkg = tmp_path / "subpkg"
    subpkg.mkdir()
    _write_codemanifest(subpkg, CHILD)

    with _cwd(tmp_path):
        result = _run_schema("--max-depth", "1")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data[0]["children"]) == 1
    assert data[0]["children"][0]["cell"] == "subpkg"
    assert data[0]["children"][0]["children"] == []


def test_schema_with_cells_filter(tmp_path) -> None:
    pkg_a = tmp_path / "pkg_a"
    pkg_a.mkdir()
    _write_codemanifest(pkg_a, STANDALONE)

    pkg_b = tmp_path / "pkg_b"
    pkg_b.mkdir()
    _write_codemanifest(pkg_b, STANDALONE.replace("StandaloneEntity", "OtherEntity"))

    with _cwd(tmp_path):
        result = _run_schema("pkg_a")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["cell"] == "pkg_a"


def test_schema_with_cells_filter_nested(tmp_path) -> None:
    _write_codemanifest(
        tmp_path,
        """\
Usages: {}

Annotations: ""

---
"RootEntity()":
  location: root.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Root
""",
    )
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    _write_codemanifest(
        pkg,
        """\
Imports:
  - Types:
      - Helper
    From: pkg/sub

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
Description: Pkg root
""",
    )
    sub = pkg / "sub"
    sub.mkdir()
    _write_codemanifest(sub, CHILD)

    with _cwd(tmp_path):
        result = _run_schema("pkg/sub")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["cell"] == "."
    # pkg is child of ".", pkg/sub is child of pkg
    pkg = data[0]["children"][0]
    assert pkg["cell"] == "pkg"
    child_cells = {c["cell"] for c in pkg["children"]}
    assert "pkg/sub" in child_cells


def test_schema_with_cells_filter_prunes_siblings(tmp_path) -> None:
    """Filtering for one cell must not include sibling cells at the same level."""
    _write_codemanifest(
        tmp_path,
        """\
Usages: {}

Annotations: ""

---
"RootEntity()":
  location: root.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Root
""",
    )
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    _write_codemanifest(pkg, STANDALONE)

    sub_a = pkg / "sub_a"
    sub_a.mkdir()
    _write_codemanifest(sub_a, CHILD)

    sub_b = pkg / "sub_b"
    sub_b.mkdir()
    _write_codemanifest(sub_b, CHILD)

    with _cwd(tmp_path):
        result = _run_schema("pkg/sub_a")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["cell"] == "."
    pkg_node = data[0]["children"][0]
    assert pkg_node["cell"] == "pkg"
    child_cells = [c["cell"] for c in pkg_node["children"]]
    assert child_cells == ["pkg/sub_a"]


def test_schema_empty_tree(tmp_path) -> None:
    with _cwd(tmp_path):
        result = _run_schema()

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == []


def test_schema_output_is_only_json(tmp_path) -> None:
    _write_codemanifest(tmp_path, STANDALONE)

    with _cwd(tmp_path):
        result = _run_schema()

    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert set(data[0].keys()) == {"cell", "children", "dependencies", "description", "types", "usages"}


def test_schema_multiple_roots(tmp_path) -> None:
    pkg_a = tmp_path / "pkg_a"
    pkg_a.mkdir()
    _write_codemanifest(pkg_a, STANDALONE)

    pkg_b = tmp_path / "pkg_b"
    pkg_b.mkdir()
    _write_codemanifest(pkg_b, STANDALONE.replace("StandaloneEntity", "OtherEntity"))

    with _cwd(tmp_path):
        result = _run_schema()

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 2
    cells = {item["cell"] for item in data}
    assert "pkg_a" in cells
    assert "pkg_b" in cells


def test_schema_with_ast_errors_exits_1(tmp_path) -> None:
    _write_codemanifest(tmp_path, ERROR_IMPORTS)

    with _cwd(tmp_path):
        result = _run_schema()

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert "cell" in data[0]


def test_schema_no_usages_dir(tmp_path) -> None:
    _write_codemanifest(tmp_path, STANDALONE)

    with _cwd(tmp_path):
        result = _run_schema()

    data = json.loads(result.output)
    assert data[0]["usages"] == []


def test_schema_max_depth_zero(tmp_path) -> None:
    _write_codemanifest(tmp_path, ROOT_WITH_CHILD)
    subpkg = tmp_path / "subpkg"
    subpkg.mkdir()
    _write_codemanifest(subpkg, CHILD)

    with _cwd(tmp_path):
        result = _run_schema("--max-depth", "0")

    data = json.loads(result.output)
    assert data[0]["children"] == []


def test_schema_unicode_in_description(tmp_path) -> None:
    _write_codemanifest(tmp_path, UNICODE)

    with _cwd(tmp_path):
        result = _run_schema()

    data = json.loads(result.output)
    assert "кириллиц" in data[0]["description"]
    assert "\\u" not in result.output


def test_schema_dependencies_deduplicated(tmp_path) -> None:
    _write_codemanifest(tmp_path, DEDUP_ROOT)
    subpkg = tmp_path / "subpkg"
    subpkg.mkdir()
    _write_codemanifest(subpkg, DEDUP_CHILD)

    with _cwd(tmp_path):
        result = _run_schema()

    assert result.exit_code == 0
    data = json.loads(result.output)
    deps = data[0]["dependencies"]
    assert "subpkg" in deps
    assert len(deps) == 1
    assert set(deps["subpkg"]["types"]) == {"HelperA", "HelperB"}


WITH_USAGE_IMPORT = """\
Imports:
  - Types:
      - Foo
    From: lib
  - Usages:
      - bar
    From: lib

Usages: {}

Annotations: |
  Uses `Foo` and `bar` here

---
"Entity()":
  location: entity.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Cell with type and usage imports
"""

LIB_WITH_FOO = """\
Usages: {}

Annotations: ""

---
"Foo()":
  location: foo.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Lib with Foo
"""

NO_IMPORTS = """\
Usages: {}

Annotations: ""

---
"Plain()":
  location: plain.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: No imports
"""

MULTI_IMPORTS = """\
Imports:
  - Types:
      - Alpha
    From: lib_a
  - Types:
      - Beta
    From: lib_b

Usages: {}

Annotations: ""

---
"Entity()":
  location: entity.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Multiple import sources
"""


def test_schema_dependencies_basic(tmp_path) -> None:
    _write_codemanifest(tmp_path, ROOT_WITH_CHILD)
    subpkg = tmp_path / "subpkg"
    subpkg.mkdir()
    _write_codemanifest(subpkg, CHILD)

    with _cwd(tmp_path):
        result = _run_schema()

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "subpkg" in data[0]["dependencies"]
    assert data[0]["dependencies"]["subpkg"]["types"] == ["Helper"]
    assert data[0]["dependencies"]["subpkg"]["usages"] == []


def test_schema_dependencies_with_types_and_usages(tmp_path) -> None:
    _write_codemanifest(tmp_path, WITH_USAGE_IMPORT)
    lib = tmp_path / "lib"
    lib.mkdir()
    _write_codemanifest(lib, LIB_WITH_FOO)
    (lib / ".usages").mkdir()
    (lib / ".usages" / "bar.md").write_text("test", encoding="utf-8")

    with _cwd(tmp_path):
        result = _run_schema()

    assert result.exit_code == 0
    data = json.loads(result.output)
    deps = data[0]["dependencies"]
    assert "lib" in deps
    assert deps["lib"]["types"] == ["Foo"]
    assert deps["lib"]["usages"] == ["bar"]


def test_schema_dependencies_empty_imports(tmp_path) -> None:
    _write_codemanifest(tmp_path, NO_IMPORTS)

    with _cwd(tmp_path):
        result = _run_schema()

    data = json.loads(result.output)
    assert data[0]["dependencies"] == {}


def test_schema_types_field_entities_and_routines(tmp_path) -> None:
    _write_codemanifest(tmp_path, ROOT_WITH_CHILD)

    with _cwd(tmp_path):
        result = _run_schema()

    data = json.loads(result.output)
    assert data[0]["types"] == ["MyClass"]


def test_schema_types_field_single_entity(tmp_path) -> None:
    _write_codemanifest(tmp_path, NO_IMPORTS)

    with _cwd(tmp_path):
        result = _run_schema()

    data = json.loads(result.output)
    assert data[0]["types"] == ["Plain"]


def test_schema_types_field_routine(tmp_path) -> None:
    _write_codemanifest(tmp_path, CHILD)

    with _cwd(tmp_path):
        result = _run_schema()

    data = json.loads(result.output)
    assert data[0]["types"] == ["Helper"]


def test_schema_usages_basename(tmp_path) -> None:
    _write_codemanifest(tmp_path, STANDALONE)
    (tmp_path / ".usages").mkdir()
    (tmp_path / ".usages" / "click.md").write_text("test", encoding="utf-8")

    with _cwd(tmp_path):
        result = _run_schema()

    data = json.loads(result.output)
    assert data[0]["usages"] == ["click.md"]


def test_schema_dependencies_multiple_from_paths(tmp_path) -> None:
    _write_codemanifest(tmp_path, MULTI_IMPORTS)

    with _cwd(tmp_path):
        result = _run_schema()

    data = json.loads(result.output)
    deps = data[0]["dependencies"]
    assert len(deps) == 2
    dep_keys = list(deps.keys())
    assert dep_keys == sorted(dep_keys)
    assert deps["lib_a"]["types"] == ["Alpha"]
    assert deps["lib_b"]["types"] == ["Beta"]


CELL_A = """\
Imports:
  - Types:
      - BType
    From: B

Usages: {}

Annotations: |
  Uses `BType` here

---
"AType()":
  location: a.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Cell A depends on B
"""

CELL_B = """\
Imports:
  - Types:
      - CType
    From: C

Usages: {}

Annotations: |
  Uses `CType` here

---
"BType()":
  location: b.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Cell B depends on C
"""

CELL_C = """\
Usages: {}

Annotations: ""

---
"CType()":
  location: c.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Cell C no deps
"""


def test_schema_depends_on_filter_basic(tmp_path) -> None:
    cell_a = tmp_path / "A"
    cell_a.mkdir()
    _write_codemanifest(cell_a, CELL_A)

    cell_b = tmp_path / "B"
    cell_b.mkdir()
    _write_codemanifest(cell_b, CELL_B)

    cell_c = tmp_path / "C"
    cell_c.mkdir()
    _write_codemanifest(cell_c, CELL_C)

    with _cwd(tmp_path):
        result = _run_schema("--depends-on", "C")

    assert result.exit_code == 0
    data = json.loads(result.output)
    # B depends on C directly, so B is kept
    # A depends on B but B is a sibling (not a child), so A is not kept
    # C has no dependency on C, so C is excluded
    cells = [d["cell"] for d in data]
    assert cells == ["B"]


def test_schema_depends_on_no_match(tmp_path) -> None:
    cell_a = tmp_path / "A"
    cell_a.mkdir()
    _write_codemanifest(cell_a, CELL_A)
    cell_b = tmp_path / "B"
    cell_b.mkdir()
    _write_codemanifest(cell_b, CELL_B)
    cell_c = tmp_path / "C"
    cell_c.mkdir()
    _write_codemanifest(cell_c, CELL_C)

    with _cwd(tmp_path):
        result = _run_schema("--depends-on", "nonexistent")

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == []


def test_schema_depends_on_recursive(tmp_path) -> None:
    _write_codemanifest(tmp_path, ROOT_WITH_CHILD)
    subpkg = tmp_path / "subpkg"
    subpkg.mkdir()
    _write_codemanifest(subpkg, CHILD)

    with _cwd(tmp_path):
        result = _run_schema("--depends-on", "subpkg")

    assert result.exit_code == 0
    data = json.loads(result.output)
    # root depends on subpkg (has subpkg in dependencies), so root is kept
    assert len(data) == 1
    assert data[0]["cell"] == "."
    assert "subpkg" in data[0]["dependencies"]


def test_schema_cells_and_depends_on_combined(tmp_path) -> None:
    cell_a = tmp_path / "A"
    cell_a.mkdir()
    _write_codemanifest(cell_a, CELL_A)

    cell_b = tmp_path / "B"
    cell_b.mkdir()
    _write_codemanifest(cell_b, CELL_B)

    cell_c = tmp_path / "C"
    cell_c.mkdir()
    _write_codemanifest(cell_c, CELL_C)

    with _cwd(tmp_path):
        result = _run_schema("A", "--depends-on", "B")

    assert result.exit_code == 0
    data = json.loads(result.output)
    # cells filter picks only A, depends_on keeps A (A depends on B)
    assert len(data) == 1
    assert data[0]["cell"] == "A"


def test_schema_depends_on_with_non_normalized_path(tmp_path) -> None:
    _write_codemanifest(tmp_path, ROOT_WITH_CHILD)
    subpkg = tmp_path / "subpkg"
    subpkg.mkdir()
    _write_codemanifest(subpkg, CHILD)

    with _cwd(tmp_path):
        result = _run_schema("--depends-on", "./subpkg")

    assert result.exit_code == 0
    data = json.loads(result.output)
    # ./subpkg normalizes to subpkg, root depends on subpkg
    assert len(data) == 1
    assert data[0]["cell"] == "."


def test_schema_depends_on_multiple_values(tmp_path) -> None:
    cell_a = tmp_path / "A"
    cell_a.mkdir()
    _write_codemanifest(cell_a, CELL_A)

    cell_b = tmp_path / "B"
    cell_b.mkdir()
    _write_codemanifest(cell_b, CELL_B)

    cell_c = tmp_path / "C"
    cell_c.mkdir()
    _write_codemanifest(cell_c, CELL_C)

    with _cwd(tmp_path):
        result = _run_schema("--depends-on", "B", "--depends-on", "C")

    assert result.exit_code == 0
    data = json.loads(result.output)
    # A depends on B (match), B depends on C (match), C has no deps
    cells = [d["cell"] for d in data]
    assert "A" in cells
    assert "B" in cells


def test_schema_depends_on_deep_recursive(tmp_path) -> None:
    root_manifest = """\
Usages: {}

Annotations: ""

---

"RootEntity()":
  location: root.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Root
"""
    mid_manifest = """\
Usages: {}

Annotations: ""

---
"MidEntity()":
  location: mid.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Mid
"""
    leaf_manifest = """\
Imports:
  - Types:
      - HelperType
    From: mid/lib

Usages: {}

Annotations: |
  Uses `HelperType` here

---
"LeafEntity()":
  location: leaf.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Leaf with dep
"""
    lib_manifest = """\
Usages: {}

Annotations: ""

---
"HelperType()":
  location: helper.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Lib
"""

    _write_codemanifest(tmp_path, root_manifest)
    mid = tmp_path / "mid"
    mid.mkdir()
    _write_codemanifest(mid, mid_manifest)
    leaf = mid / "leaf"
    leaf.mkdir()
    _write_codemanifest(leaf, leaf_manifest)
    lib = mid / "lib"
    lib.mkdir()
    _write_codemanifest(lib, lib_manifest)

    with _cwd(tmp_path):
        result = _run_schema("--depends-on", "mid/lib")

    assert result.exit_code == 0
    data = json.loads(result.output)
    # root has child mid, mid has child leaf, leaf depends on mid/lib
    # root passes because descendant leaf depends on mid/lib
    assert len(data) == 1
    assert data[0]["cell"] == "."


def test_schema_cells_and_depends_on_no_match(tmp_path) -> None:
    cell_a = tmp_path / "A"
    cell_a.mkdir()
    _write_codemanifest(cell_a, CELL_A)

    cell_b = tmp_path / "B"
    cell_b.mkdir()
    _write_codemanifest(cell_b, CELL_B)

    cell_c = tmp_path / "C"
    cell_c.mkdir()
    _write_codemanifest(cell_c, CELL_C)

    with _cwd(tmp_path):
        result = _run_schema("A", "--depends-on", "C")

    assert result.exit_code == 0
    data = json.loads(result.output)
    # A depends on B, not C — result should be empty
    assert data == []


def test_schema_types_field_entities_and_routines_combined(tmp_path) -> None:
    combined = """\
Usages: {}

Annotations: ""

---
"MyEntity()":
  location: entity.py
  annotations: ""

"my_routine()":
  location: routine.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Combined
"""
    _write_codemanifest(tmp_path, combined)

    with _cwd(tmp_path):
        result = _run_schema()

    data = json.loads(result.output)
    assert data[0]["types"] == ["MyEntity", "my_routine"]


def test_schema_depends_on_with_max_depth(tmp_path) -> None:
    """--depends-on must find transitive deps beyond --max-depth limit."""
    root_manifest = """\
Usages: {}

Annotations: ""

---
"RootEntity()":
  location: root.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Root
"""
    mid_manifest = """\
Usages: {}

Annotations: ""

---
"MidEntity()":
  location: mid.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Mid
"""
    leaf_manifest = """\
Imports:
  - Types:
      - HelperType
    From: mid/lib

Usages: {}

Annotations: |
  Uses `HelperType` here

---
"LeafEntity()":
  location: leaf.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Leaf with dep
"""
    lib_manifest = """\
Usages: {}

Annotations: ""

---
"HelperType()":
  location: helper.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Lib
"""

    _write_codemanifest(tmp_path, root_manifest)
    mid = tmp_path / "mid"
    mid.mkdir()
    _write_codemanifest(mid, mid_manifest)
    leaf = mid / "leaf"
    leaf.mkdir()
    _write_codemanifest(leaf, leaf_manifest)
    lib = mid / "lib"
    lib.mkdir()
    _write_codemanifest(lib, lib_manifest)

    with _cwd(tmp_path):
        result = _run_schema("--depends-on", "mid/lib", "--max-depth", "1")

    assert result.exit_code == 0
    data = json.loads(result.output)
    # root passes because descendant leaf depends on mid/lib, even though
    # --max-depth 1 prunes leaf from the output tree
    assert len(data) == 1
    assert data[0]["cell"] == "."
    # mid is at depth 1, so it's included but leaf (depth 2) is pruned
    assert len(data[0]["children"]) == 1
    assert data[0]["children"][0]["cell"] == "mid"
    assert data[0]["children"][0]["children"] == []
