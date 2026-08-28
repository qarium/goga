"""Contract and logic tests for the routines declared in
``goga/history/CODEMANIFEST`` with ``location: paths.py``:

- ``resolve_topic_dir(topic: str, year: str | None = None) -> Path``
- ``resolve_topic_file(topic: str, filename: str, year: str | None = None) -> Path``
- ``topic_exists(topic: str, year: str | None = None) -> bool``
- ``ensure_topic_dir(name: str) -> Path``

The path composers are pure with respect to the filesystem; ``ensure_topic_dir``
is the only mutating routine. The single mock target is ``naming.datetime``
(the mandated bare-``now()`` point), patched at the import site; filesystem
fixtures use ``tmp_path`` + ``monkeypatch.chdir``.
"""

from __future__ import annotations

import inspect
import typing
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest
from goga.history import naming, paths
from goga.history.paths import (
    ensure_topic_dir,
    resolve_topic_dir,
    resolve_topic_file,
    topic_exists,
)


class _FixedClock:
    """Stand-in for ``datetime`` answering a fixed naive date."""

    @staticmethod
    def now() -> datetime:
        return datetime(2031, 6, 15)  # noqa: DTZ001 — a fixed naive date is the point of the clock


# --- Contract tests ---


class TestPathsContract:
    def test_routines_are_importable_from_module_and_callable(self) -> None:
        """All four routines are importable from ``goga.history.paths`` and callable."""
        assert callable(resolve_topic_dir)
        assert callable(resolve_topic_file)
        assert callable(topic_exists)
        assert callable(ensure_topic_dir)
        assert paths.resolve_topic_dir is resolve_topic_dir
        assert paths.resolve_topic_file is resolve_topic_file
        assert paths.topic_exists is topic_exists
        assert paths.ensure_topic_dir is ensure_topic_dir

    def test_facade_reexports_the_paths_names(self) -> None:
        """The paths routines are importable from the domain facade."""
        import goga.history

        assert goga.history.resolve_topic_dir is resolve_topic_dir
        assert goga.history.resolve_topic_file is resolve_topic_file
        assert goga.history.topic_exists is topic_exists
        assert goga.history.ensure_topic_dir is ensure_topic_dir
        for name in ("resolve_topic_dir", "resolve_topic_file", "topic_exists", "ensure_topic_dir"):
            assert name in goga.history.__all__

    def test_resolve_topic_dir_signature(self) -> None:
        """``resolve_topic_dir(topic: str, year: str | None = None) -> Path``."""
        signature = inspect.signature(resolve_topic_dir)
        assert list(signature.parameters) == ["topic", "year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        hints = typing.get_type_hints(resolve_topic_dir)
        assert hints == {"topic": str, "year": str | None, "return": Path}

    def test_resolve_topic_file_signature(self) -> None:
        """``resolve_topic_file(topic: str, filename: str, year: str | None = None) -> Path``."""
        signature = inspect.signature(resolve_topic_file)
        assert list(signature.parameters) == ["topic", "filename", "year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        hints = typing.get_type_hints(resolve_topic_file)
        assert hints == {"topic": str, "filename": str, "year": str | None, "return": Path}

    def test_topic_exists_signature(self) -> None:
        """``topic_exists(topic: str, year: str | None = None) -> bool``."""
        signature = inspect.signature(topic_exists)
        assert list(signature.parameters) == ["topic", "year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        hints = typing.get_type_hints(topic_exists)
        assert hints == {"topic": str, "year": str | None, "return": bool}

    def test_ensure_topic_dir_signature(self) -> None:
        """``ensure_topic_dir(name: str) -> Path`` — one positional-or-keyword parameter."""
        signature = inspect.signature(ensure_topic_dir)
        assert list(signature.parameters) == ["name"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
        )
        hints = typing.get_type_hints(ensure_topic_dir)
        assert hints == {"name": str, "return": Path}

    def test_history_root_helper_points_at_the_tree(self) -> None:
        """The private helper answers the relative history root."""
        assert paths._history_root() == Path(".goga") / "history"


# --- Logic tests ---


class TestResolveTopicDir:
    def test_resolve_topic_dir_composes_and_normalizes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Branch input normalizes; no year means the current year; nothing is created."""
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(naming, "datetime", _FixedClock):
            assert resolve_topic_dir("Feature/Foo_Bar") == Path(".goga/history/2031/feature-foo-bar")
            assert resolve_topic_dir("release-1-3-0", year="2025") == Path(".goga/history/2025/release-1-3-0")
        assert not (tmp_path / ".goga").exists()

    def test_resolve_topic_dir_is_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The same input yields the same path on every call."""
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(naming, "datetime", _FixedClock):
            first = resolve_topic_dir("My Tool")
            second = resolve_topic_dir("My Tool")
        assert first == second == Path(".goga/history/2031/my-tool")

    def test_resolve_topic_dir_empty_slug_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A fully non-ASCII topic raises the clean empty-slug error, no fallback."""
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match="normalizes to an empty topic slug"):
            resolve_topic_dir("Релиз/Один")

    def test_resolve_topic_dir_empty_year_string_means_current(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A falsy year (``""`` from an empty CLI value) means "not set", not path degradation."""
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(naming, "datetime", _FixedClock):
            assert resolve_topic_dir("feat-x", year="") == Path(".goga/history/2031/feat-x")


class TestResolveTopicFile:
    def test_resolve_topic_file_appends_filename(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The filename is appended verbatim; the file is not created."""
        monkeypatch.chdir(tmp_path)
        path = resolve_topic_file("history-commands", "plan.md", year="2026")
        assert path == Path(".goga/history/2026/history-commands/plan.md")
        assert not path.exists()

    @pytest.mark.parametrize("filename", ["noext", ".md", "plan."])
    def test_resolve_topic_file_rejects_extensionless(
        self, filename: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An extensionless filename — including dotfiles and trailing dots — is a clean error."""
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match="must carry an extension"):
            resolve_topic_file("history-commands", filename, year="2026")

    def test_resolve_topic_file_empty_slug_raises_via_dir_composer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The file composer reuses the single directory composer — its empty-slug error stands."""
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match="normalizes to an empty topic slug"):
            resolve_topic_file("Релиз/Один", "plan.md", year="2026")


class TestTopicExists:
    def test_topic_exists_true_for_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only a directory occupies a topic — and only for its own year."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga" / "history" / "2026" / "feat-x").mkdir(parents=True)
        (tmp_path / ".goga" / "history" / "2026" / "stray").write_text("not a topic", encoding="utf-8")
        assert topic_exists("feat/x", year="2026") is True
        assert topic_exists("feat/x", year="2025") is False
        assert topic_exists("stray", year="2026") is False

    def test_topic_exists_absent_root_is_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing history root is "no", not an error — and creates nothing."""
        monkeypatch.chdir(tmp_path)
        assert topic_exists("feat-x") is False
        assert not (tmp_path / ".goga").exists()


class TestEnsureTopicDir:
    def test_ensure_topic_dir_creates_idempotently(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Creation normalizes, defaults to the current year, and is idempotent."""
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(naming, "datetime", _FixedClock):
            first = ensure_topic_dir("Feature/X")
            second = ensure_topic_dir("feature-x")
        expected = Path(".goga/history/2031/feature-x")
        assert first == expected
        assert second == expected
        assert first.is_dir()
        assert list(first.iterdir()) == []

    def test_ensure_topic_dir_creates_parents(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing parents (.goga/history/<year>) are created on the way."""
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(naming, "datetime", _FixedClock):
            created = ensure_topic_dir("feat-y")
        assert created == Path(".goga/history/2031/feat-y")
        assert (tmp_path / ".goga" / "history" / "2031").is_dir()

    def test_ensure_topic_dir_empty_slug_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty slug is the directory composer's clean error — nothing is created."""
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match="normalizes to an empty topic slug"):
            ensure_topic_dir("Релиз/Один")
        assert not (tmp_path / ".goga").exists()
