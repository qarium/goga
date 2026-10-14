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
        """``--help`` documents CELLS, --max-depth, and --depends-on."""
        result = _run_codegraph("--help")

        assert result.exit_code == 0
        assert "CELLS" in result.output
        assert "--max-depth" in result.output
        assert "--depends-on" in result.output

    def test_cli_codegraph_failure_stderr_only(self) -> None:
        """An uninitialized project is a clean stderr failure, exit 1."""
        result = _run_codegraph()

        assert result.exit_code == 1
        assert result.stdout == ""
        assert result.stderr != ""
        assert "Traceback" not in result.stderr
