"""Integration: the full ``goga codegraph`` CLI surface across the codegraph cells.

Drives the registered ``app`` end-to-end — config load, source discovery,
tree-sitter analysis, link resolution, rendering — through a synthetic python
project of two packages where ``client`` imports from ``app`` (plus one nested
cell under ``client`` so the depth filter is observable). Every assertion is
pinned against ``json.loads`` of the CLI stdout, and the command-table
registration is checked through the root ``--help``.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from goga.cli import app


def _write_two_package_project() -> None:
    """Write the synthetic project — ``client`` imports ``Service`` from ``app``."""
    goga_dir = Path(".goga")
    goga_dir.mkdir(exist_ok=True)
    (goga_dir / "config.yml").write_text("language: python\n", encoding="utf-8")

    app_dir = Path("app")
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("from .core import Service\n", encoding="utf-8")
    (app_dir / "core.py").write_text("class Service:\n    pass\n", encoding="utf-8")

    client_dir = Path("client")
    client_dir.mkdir()
    (client_dir / "__init__.py").write_text("from app import Service\n", encoding="utf-8")

    inner_dir = client_dir / "inner"
    inner_dir.mkdir()
    (inner_dir / "__init__.py").write_text("def ping() -> int:\n    return 1\n", encoding="utf-8")


def _invoke_codegraph(*args: str):
    runner = CliRunner()

    return runner.invoke(app, ["codegraph", *args])


class TestCodegraphCliIntegration:
    """The registered command driving config → discovery → analysis → render."""

    def test_codegraph_cli_renders_full_graph_and_cross_package_link(self) -> None:
        """The unfiltered run renders both roots and the client → app link."""
        _write_two_package_project()

        result = _invoke_codegraph()

        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert [node["cell"] for node in doc] == ["app", "client"]
        client = doc[1]
        assert client["dependencies"] == {"app": ["Service"]}
        assert [child["cell"] for child in client["children"]] == ["client/inner"]

    def test_codegraph_cli_cells_filter_keeps_matching_cell_only(self) -> None:
        """``codegraph client`` keeps ``client`` alone — sibling and nested cells drop."""
        _write_two_package_project()

        result = _invoke_codegraph("client")

        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert [node["cell"] for node in doc] == ["client"]
        assert doc[0]["children"] == []
        assert doc[0]["dependencies"] == {"app": ["Service"]}

    def test_codegraph_cli_max_depth_zero_empties_children(self) -> None:
        """``--max-depth 0`` keeps every root with its children emptied."""
        _write_two_package_project()

        result = _invoke_codegraph("--max-depth", "0")

        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert {node["cell"] for node in doc} == {"app", "client"}
        assert all(node["children"] == [] for node in doc)

    def test_codegraph_cli_depends_on_keeps_dependent_cell(self) -> None:
        """``--depends-on app`` keeps the depending ``client`` root only."""
        _write_two_package_project()

        result = _invoke_codegraph("--depends-on", "app")

        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert [node["cell"] for node in doc] == ["client"]
        assert doc[0]["dependencies"] == {"app": ["Service"]}
        assert doc[0]["children"] == []

    def test_codegraph_cli_two_invocations_byte_identical(self) -> None:
        """Identical invocations produce byte-identical stdout."""
        _write_two_package_project()

        first = _invoke_codegraph()
        second = _invoke_codegraph()

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert first.output == second.output

    def test_codegraph_cli_listed_in_root_help(self) -> None:
        """The root ``goga --help`` command table lists ``codegraph``."""
        _write_two_package_project()

        result = CliRunner().invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "codegraph" in result.output
