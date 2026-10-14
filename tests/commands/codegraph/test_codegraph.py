"""Contract and logic tests for the ``codegraph`` CLI command of ``goga/commands/codegraph``.

Command under test (declared in ``goga/commands/codegraph/CODEMANIFEST`` with
``location: codegraph.py``):

- ``codegraph(cells, max_depth, depends_on)`` — click wrapper delegating to
  ``codegraph_logic`` of ``goga/codegraph``; JSON on stdout, failures as
  clean stderr messages with exit 1.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
import pytest
from click.testing import CliRunner
from goga.cli import app
from goga.commands import codegraph as codegraph_facade
from goga.commands.codegraph import codegraph as codegraph_source


@pytest.fixture(autouse=True)
def _empty_package_environment(empty_package_environment) -> None:
    """Pin the package environment empty for every test of this module."""


def _run_codegraph(*args: str):
    runner = CliRunner()

    return runner.invoke(app, ["codegraph", *args])


def _write_config(language: str = "python") -> None:
    """Write a minimal ``.goga/config.yml`` with the given language."""
    goga_dir = Path(".goga")
    goga_dir.mkdir(exist_ok=True)
    (goga_dir / "config.yml").write_text(f"language: {language}\n", encoding="utf-8")


def _write_golden_project() -> None:
    """Write the Task-7 golden project — the ``greeting`` package."""
    _write_config("python")

    greeting = Path("greeting")
    greeting.mkdir()
    (greeting / "__init__.py").write_text(
        '__all__ = ["hello"]\nfrom .impl import hello\n',
        encoding="utf-8",
    )
    (greeting / "impl.py").write_text(
        "def hello() -> str:\n    return 'hi'\n",
        encoding="utf-8",
    )


class TestCodegraphCommand:
    """Facade, click surface, and registration contract of the wrapper."""

    def test_codegraph_importable_from_cell(self) -> None:
        """``codegraph`` is importable from ``goga.commands.codegraph``."""
        assert isinstance(codegraph_source, click.Command)

    def test_codegraph_importable_from_commands_facade(self) -> None:
        """``codegraph`` is importable from the ``goga.commands`` facade."""
        assert codegraph_facade is codegraph_source

    def test_codegraph_registered_on_app(self) -> None:
        """The root group carries the command under the name ``codegraph``."""
        assert any(cmd.name == "codegraph" for cmd in app.commands.values())

    def test_cli_codegraph_success_and_registration(self) -> None:
        """The registered command renders the golden JSON on stdout, exit 0."""
        _write_golden_project()

        result = _run_codegraph()

        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert isinstance(doc, list)
        assert len(doc) == 1
        assert doc[0]["cell"] == "greeting"
        assert any(cmd.name == "codegraph" for cmd in app.commands.values())

    def test_cli_codegraph_help_documents_the_surface(self) -> None:
        """``--help`` documents CELLS, --max-depth, --depends-on, and the JSON node fields."""
        result = _run_codegraph("--help")

        assert result.exit_code == 0
        assert "CELLS" in result.output
        assert "--max-depth" in result.output
        assert "--depends-on" in result.output
        assert "JSON structure per root cell:" in result.output
        assert "cell" in result.output
        assert "types" in result.output
        assert "dependencies" in result.output
        assert "children" in result.output

    def test_cli_codegraph_failure_stderr_only(self) -> None:
        """An uninitialized project is a clean stderr failure, exit 1."""
        result = _run_codegraph()

        assert result.exit_code == 1
        assert result.stdout == ""
        assert result.stderr != ""
        assert "Traceback" not in result.stderr


# --- Golden CLI byte-identity net (captured from the live CLI; the C2 contract) ---

GOLDEN_CODEGRAPH_FULL = """\
[
    {
        "cell": "greeting",
        "children": [
            {
                "cell": "greeting/sub",
                "children": [],
                "dependencies": {},
                "types": [
                    "cheer"
                ]
            }
        ],
        "dependencies": {
            "util": [
                "tag"
            ]
        },
        "types": [
            "hello"
        ]
    },
    {
        "cell": "util",
        "children": [],
        "dependencies": {},
        "types": [
            "tag"
        ]
    }
]
"""

GOLDEN_CODEGRAPH_CELLS_FILTER = """\
[
    {
        "cell": "greeting",
        "children": [
            {
                "cell": "greeting/sub",
                "children": [],
                "dependencies": {},
                "types": [
                    "cheer"
                ]
            }
        ],
        "dependencies": {
            "util": [
                "tag"
            ]
        },
        "types": [
            "hello"
        ]
    }
]
"""

GOLDEN_CODEGRAPH_MAX_DEPTH = """\
[
    {
        "cell": "greeting",
        "children": [],
        "dependencies": {
            "util": [
                "tag"
            ]
        },
        "types": [
            "hello"
        ]
    },
    {
        "cell": "util",
        "children": [],
        "dependencies": {},
        "types": [
            "tag"
        ]
    }
]
"""

GOLDEN_CODEGRAPH_DEPENDS_ON = """\
[
    {
        "cell": "greeting",
        "children": [],
        "dependencies": {
            "util": [
                "tag"
            ]
        },
        "types": [
            "hello"
        ]
    }
]
"""

GOLDEN_CODEGRAPH_EMPTY = "[]\n"


def _write_golden_tree_project() -> None:
    """Write the golden-tree fixture — greeting with a nested sub cell and a util dependency.

    The plain ``greeting`` project of ``_write_golden_project`` pins the flat
    record; this tree adds the nesting and the cross-cell link so the golden
    net also pins the recursive serialization of children and dependencies.
    """
    _write_config("python")

    greeting = Path("greeting")
    greeting.mkdir()
    (greeting / "__init__.py").write_text(
        '__all__ = ["hello"]\nfrom .impl import hello\n',
        encoding="utf-8",
    )
    (greeting / "impl.py").write_text(
        'from util import tag\n\n\ndef hello() -> str:\n    return "hi"\n',
        encoding="utf-8",
    )
    sub = greeting / "sub"
    sub.mkdir()
    (sub / "__init__.py").write_text(
        'def cheer() -> str:\n    return "go"\n',
        encoding="utf-8",
    )
    util = Path("util")
    util.mkdir()
    (util / "__init__.py").write_text(
        'def tag() -> str:\n    return "t"\n',
        encoding="utf-8",
    )


class TestCodegraphCliByteIdentity:
    """The CLI stdout pinned byte for byte — the net the object-return refactor must not tear.

    The goldens were captured from the live CLI over this exact fixture
    project before the domain was touched. A mismatch is a defect in the
    refactor — never adjust a golden.
    """

    def test_codegraph_cli_output_byte_identical_golden(self) -> None:
        """Every form of the command prints its golden document, exit 0."""
        _write_golden_tree_project()

        result = _run_codegraph()

        assert result.exit_code == 0
        assert result.output == GOLDEN_CODEGRAPH_FULL

        result = _run_codegraph("greeting/sub")

        assert result.exit_code == 0
        assert result.output == GOLDEN_CODEGRAPH_CELLS_FILTER

        result = _run_codegraph("--max-depth", "0")

        assert result.exit_code == 0
        assert result.output == GOLDEN_CODEGRAPH_MAX_DEPTH

        result = _run_codegraph("--depends-on", "util")

        assert result.exit_code == 0
        assert result.output == GOLDEN_CODEGRAPH_DEPENDS_ON

    def test_codegraph_cli_empty_project_byte_identical_golden(self) -> None:
        """A config-only project prints the exact empty document."""
        _write_config("python")

        result = _run_codegraph()

        assert result.exit_code == 0
        assert result.output == GOLDEN_CODEGRAPH_EMPTY
