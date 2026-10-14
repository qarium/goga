"""Contract and logic tests for the ``codegraph`` orchestrator of ``goga/codegraph``.

Routine under test (declared in ``goga/codegraph/CODEMANIFEST`` with
``location: codegraph.py``):

- ``codegraph(cells, max_depth, depends_on) -> str`` — load the project
  configuration, validate the language, discover the sources, run the three
  analysis stages in order, and render the JSON tree.

The scenarios build real trees on ``tmp_path`` (cwd pinned by the autouse
``_isolate_cwd`` fixture) — no mocks, the pipeline runs for real.
"""

from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

GOLDEN_OUTPUT = textwrap.dedent("""\
    [
        {
            "cell": "greeting",
            "children": [],
            "dependencies": {},
            "types": [
                "hello"
            ]
        }
    ]
""").strip()


def _write_config(language: str) -> None:
    """Write a minimal ``.goga/config.yml`` with the given language."""
    goga_dir = Path(".goga")
    goga_dir.mkdir(exist_ok=True)
    (goga_dir / "config.yml").write_text(f"language: {language}\n", encoding="utf-8")


def _snapshot_tree() -> dict[str, str]:
    """Snapshot the project tree — relative file paths to content hashes."""
    snapshot: dict[str, str] = {}

    for path in sorted(Path().rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot[path.as_posix()] = digest

    return snapshot


class TestCodegraph:
    """Facade and call contract of the orchestrator."""

    def test_codegraph_importable_from_facade(self) -> None:
        """``codegraph`` is importable from the codegraph cell facade."""
        from goga.codegraph import codegraph  # noqa: F401

    def test_codegraph_facade_all_exact(self) -> None:
        """The facade exposes exactly the three orchestrator-cell routines."""
        import goga.codegraph

        assert goga.codegraph.__all__ == ["codegraph", "discover_sources", "render_graph"]

    def test_codegraph_callable_no_arguments(self) -> None:
        """``codegraph`` is callable with no arguments and returns a string."""
        from goga.codegraph import codegraph

        _write_config("python")

        result = codegraph()

        assert isinstance(result, str)


class TestCodegraphEndToEnd:
    """Design scenario: the golden project renders the golden document."""

    def test_codegraph_end_to_end_golden_output(self) -> None:
        """The greeting package renders as the single golden root node."""
        from goga.codegraph import codegraph

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

        assert codegraph() == GOLDEN_OUTPUT

        assert codegraph() == codegraph()


class TestCodegraphFailures:
    """Design scenarios: the failure modes propagate uncaught."""

    def test_codegraph_uninitialized_project(self) -> None:
        """An absent ``.goga/config.yml`` raises FileNotFoundError."""
        import pytest
        from goga.codegraph import codegraph

        with pytest.raises(FileNotFoundError):
            codegraph()

    def test_codegraph_unsupported_language(self) -> None:
        """A language outside the whitelist raises ValueError naming it."""
        import pytest
        from goga.codegraph import codegraph

        _write_config("rust")

        with pytest.raises(ValueError, match="rust"):
            codegraph()


class TestCodegraphEmptyProject:
    """Design scenario: no analyzable units render as the empty list."""

    def test_render_graph_empty_project_renders_empty_list(self) -> None:
        """A loose non-unit file yields no units and the output is ``[]``."""
        from goga.codegraph import codegraph

        _write_config("python")
        Path("loose.py").write_text("def anything():\n    pass\n", encoding="utf-8")

        assert codegraph() == "[]"


class TestCodegraphReadOnly:
    """Design scenario: the run leaves the project tree unchanged."""

    def test_codegraph_read_only(self) -> None:
        """The file set and file contents are identical before and after."""
        from goga.codegraph import codegraph

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

        before = _snapshot_tree()

        codegraph()

        assert _snapshot_tree() == before
