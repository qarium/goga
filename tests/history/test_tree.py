"""Contract and logic tests for the entities declared in
``goga/history/CODEMANIFEST`` with ``location: tree.py``:

- ``HistoryYear(year: str, topics: list[str])``
- ``collect_history_tree() -> tree: list[HistoryYear]``

The collector is read-only with respect to the filesystem and carries names
only — no statuses are resolved and the clock is never read. Filesystem
fixtures use ``tmp_path`` + ``monkeypatch.chdir``; no mocks are needed.
"""

from __future__ import annotations

import dataclasses
import inspect
import typing
from pathlib import Path

import pytest
from goga.history import tree
from goga.history.tree import HistoryYear, collect_history_tree

# --- Contract tests ---


class TestTreeContract:
    def test_entities_are_importable_from_module_and_callable(self) -> None:
        """Both entities are importable from ``goga.history.tree``."""
        assert tree.HistoryYear is HistoryYear
        assert callable(collect_history_tree)
        assert tree.collect_history_tree is collect_history_tree

    def test_facade_reexports_the_tree_names(self) -> None:
        """The tree entities are importable from the domain facade."""
        import goga.history

        assert goga.history.HistoryYear is HistoryYear
        assert goga.history.collect_history_tree is collect_history_tree
        for name in ("HistoryYear", "collect_history_tree"):
            assert name in goga.history.__all__

    def test_history_year_is_frozen_kw_only_dataclass(self) -> None:
        """``@dataclass(frozen=True, kw_only=True)`` with the fields ``year`` and ``topics``."""
        assert dataclasses.is_dataclass(HistoryYear)
        assert HistoryYear.__dataclass_params__.frozen is True
        assert HistoryYear.__dataclass_params__.kw_only is True
        assert typing.get_type_hints(HistoryYear) == {"year": str, "topics": list[str]}
        record = HistoryYear(year="2026", topics=["history-commands"])
        assert record.year == "2026"
        assert record.topics == ["history-commands"]
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.year = "2025"  # type: ignore[misc]
        with pytest.raises(TypeError):
            HistoryYear("2026", [])  # type: ignore[misc]

    def test_collect_history_tree_signature(self) -> None:
        """``collect_history_tree() -> list[HistoryYear]`` — no parameters."""
        signature = inspect.signature(collect_history_tree)
        assert list(signature.parameters) == []
        hints = typing.get_type_hints(collect_history_tree)
        assert hints == {"return": list[HistoryYear]}


# --- Logic tests ---


class TestCollectHistoryTree:
    def test_collect_history_tree_full_shape(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Four-ASCII-digit year directories ascending; topics alphabetical; everything else ignored."""
        monkeypatch.chdir(tmp_path)
        root = tmp_path / ".goga" / "history"
        (root / "2025" / "b-topic").mkdir(parents=True)
        (root / "2025" / "a-topic").mkdir()
        (root / "2025" / "notes.md").write_text("stray file in a year directory", encoding="utf-8")
        (root / "2026" / "history-commands").mkdir(parents=True)
        (root / "backups").mkdir()
        (root / "20a6").mkdir()
        (root / "²⁰²⁶").mkdir()  # isdigit() is True, isascii() is not — not a year
        (root / "notes.md").write_text("not a year", encoding="utf-8")
        collected = collect_history_tree()
        assert [year_record.year for year_record in collected] == ["2025", "2026"]
        assert collected[0].topics == ["a-topic", "b-topic"]
        assert collected[1].topics == ["history-commands"]

    def test_collect_history_tree_absent_root_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An absent history root yields an empty list — not an error, and nothing is created."""
        monkeypatch.chdir(tmp_path)
        assert collect_history_tree() == []
        assert not (tmp_path / ".goga").exists()
