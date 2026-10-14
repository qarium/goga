"""Contract and logic tests for ``discover_sources`` of ``goga/codegraph``.

Routine under test (declared in ``goga/codegraph/CODEMANIFEST`` with
``location: discovery.py``):

- ``discover_sources(language, ignore) -> list[Path]`` — deterministic
  path-only walk of the project tree: the exact relative ignore entries
  prune directories and skip files (normpath mechanics, same as lint),
  the idiomatic per-language test files are always skipped, and only the
  language's primary extension is kept.

Filesystem fixtures live on ``tmp_path`` (the autouse ``_isolate_cwd``
pins the process CWD there); discovery reads no file content — no mocks.
"""

from __future__ import annotations

from pathlib import Path


def _write(root: Path, rel: str) -> None:
    """Create one empty fixture file at the relative path under ``root``."""
    target = root / rel

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("", encoding="utf-8")


class TestDiscoverSources:
    """Facade and call contract of the source discovery."""

    def test_discover_sources_importable_from_facade(self) -> None:
        """``discover_sources`` is importable from the codegraph cell facade."""
        from goga.codegraph import discover_sources  # noqa: F401

    def test_discover_sources_returns_path_list(self, tmp_path: Path) -> None:
        """An empty project discovers no sources."""
        from goga.codegraph import discover_sources

        files = discover_sources(language="python", ignore=[])

        assert isinstance(files, list)
        assert all(isinstance(file, Path) for file in files)
        assert files == []


class TestDiscoverSourcesWalk:
    """Design scenario: ignore entries, test patterns, and walk order."""

    def test_discover_sources_ignore_and_tests_and_order(self, tmp_path: Path) -> None:
        """Ignored dirs prune subtrees, ignored files and test patterns drop, order stable."""
        from goga.codegraph import discover_sources

        for rel in [
            "a/m1.py",
            "a/m2.py",
            "b/n.py",
            "b/test_n.py",
            ".venv/lib/x.py",
            "skipped/orphan.py",
        ]:
            _write(tmp_path, rel)

        ignore = [".venv/", "skipped/orphan.py"]
        files = discover_sources("python", ignore)

        assert files == [Path("a/m1.py"), Path("a/m2.py"), Path("b/n.py")]
        assert discover_sources("python", ignore) == files

    def test_discover_sources_ignore_directory_without_trailing_slash(self, tmp_path: Path) -> None:
        """An ignore entry without the trailing slash prunes the same directory."""
        from goga.codegraph import discover_sources

        _write(tmp_path, "a/m1.py")
        _write(tmp_path, "gen/lib/x.py")

        files = discover_sources("python", ["gen"])

        assert files == [Path("a/m1.py")]
