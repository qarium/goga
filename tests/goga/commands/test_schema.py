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
    assert ".usages/spec.md" in data[0]["usages"]
    assert "subpkg" in data[0]["relations"]
    assert "subpkg/.usages/helper.md" in data[0]["children"][0]["usages"]


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
    assert set(data[0].keys()) == {"cell", "children", "description", "relations", "usages"}


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


def test_schema_relations_deduplicated(tmp_path) -> None:
    _write_codemanifest(tmp_path, DEDUP_ROOT)
    subpkg = tmp_path / "subpkg"
    subpkg.mkdir()
    _write_codemanifest(subpkg, DEDUP_CHILD)

    with _cwd(tmp_path):
        result = _run_schema()

    assert result.exit_code == 0
    data = json.loads(result.output)
    relations = data[0]["relations"]
    assert len(relations) == len(set(relations))
