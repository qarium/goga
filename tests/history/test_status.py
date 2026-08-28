"""Contract and logic tests for the entities declared in
``goga/history/CODEMANIFEST`` with ``location: status.py``:

- ``TopicStatus()`` — the fixed eight-member status value set
- ``TopicRecord(topic: str, status: TopicStatus)``
- ``resolve_topic_status(topic_dir: Path) -> status: TopicStatus``
- ``collect_topic_statuses(year: str | None = None) -> records: list[TopicRecord]``

The resolver and the collector are read-only with respect to the filesystem.
The single mock target is ``naming.datetime`` (the mandated bare-``now()``
point), patched at the import site; filesystem fixtures use ``tmp_path`` +
``monkeypatch.chdir``.
"""

from __future__ import annotations

import dataclasses
import inspect
import typing
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest
from goga.history import naming, status
from goga.history.status import (
    TopicRecord,
    TopicStatus,
    collect_topic_statuses,
    resolve_topic_status,
)


class _FixedClock:
    """Stand-in for ``datetime`` answering a fixed naive date."""

    @staticmethod
    def now() -> datetime:
        return datetime(2031, 6, 15)  # noqa: DTZ001 — a fixed naive date is the point of the clock


# --- Contract tests ---


class TestStatusContract:
    def test_entities_are_importable_from_module_and_callable(self) -> None:
        """All four entities are importable from ``goga.history.status``."""
        assert status.TopicStatus is TopicStatus
        assert status.TopicRecord is TopicRecord
        assert callable(resolve_topic_status)
        assert callable(collect_topic_statuses)
        assert status.resolve_topic_status is resolve_topic_status
        assert status.collect_topic_statuses is collect_topic_statuses

    def test_facade_reexports_the_status_names(self) -> None:
        """The status entities are importable from the domain facade."""
        import goga.history

        assert goga.history.TopicStatus is TopicStatus
        assert goga.history.TopicRecord is TopicRecord
        assert goga.history.resolve_topic_status is resolve_topic_status
        assert goga.history.collect_topic_statuses is collect_topic_statuses
        for name in ("TopicStatus", "TopicRecord", "resolve_topic_status", "collect_topic_statuses"):
            assert name in goga.history.__all__

    def test_topic_status_fixed_value_set(self) -> None:
        """Eight members; each value is the display name; lookup by value works."""
        assert [member.value for member in TopicStatus] == [
            "empty",
            "defined",
            "discovered",
            "backlog",
            "designed",
            "specified",
            "planned",
            "done",
        ]
        assert TopicStatus("planned") is TopicStatus.planned
        with pytest.raises(ValueError, match="is not a valid TopicStatus"):
            TopicStatus("bogus")

    def test_topic_record_is_frozen_kw_only_dataclass(self) -> None:
        """``@dataclass(frozen=True, kw_only=True)`` with the fields ``topic`` and ``status``."""
        assert dataclasses.is_dataclass(TopicRecord)
        assert TopicRecord.__dataclass_params__.frozen is True
        assert TopicRecord.__dataclass_params__.kw_only is True
        assert typing.get_type_hints(TopicRecord) == {"topic": str, "status": TopicStatus}
        record = TopicRecord(topic="t", status=TopicStatus.planned)
        assert record.topic == "t"
        assert record.status is TopicStatus.planned
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.topic = "other"  # type: ignore[misc]
        with pytest.raises(TypeError):
            TopicRecord("t", TopicStatus.planned)  # type: ignore[misc]

    def test_resolve_topic_status_signature(self) -> None:
        """``resolve_topic_status(topic_dir: Path) -> TopicStatus`` — one positional-or-keyword parameter."""
        signature = inspect.signature(resolve_topic_status)
        assert list(signature.parameters) == ["topic_dir"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
        )
        hints = typing.get_type_hints(resolve_topic_status)
        assert hints == {"topic_dir": Path, "return": TopicStatus}

    def test_collect_topic_statuses_signature(self) -> None:
        """``collect_topic_statuses(year: str | None = None) -> list[TopicRecord]``."""
        signature = inspect.signature(collect_topic_statuses)
        assert list(signature.parameters) == ["year"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        hints = typing.get_type_hints(collect_topic_statuses)
        assert hints == {"year": str | None, "return": list[TopicRecord]}


# --- Logic tests ---


class TestResolveTopicStatus:
    @pytest.mark.parametrize(
        ("artifact", "expected"),
        [
            ("prd.md", TopicStatus.defined),
            ("adr.md", TopicStatus.discovered),
            ("task.md", TopicStatus.backlog),
            ("arch.md", TopicStatus.designed),
            ("design.md", TopicStatus.specified),
            ("plan.md", TopicStatus.planned),
            ("completed/plan.md", TopicStatus.done),
        ],
    )
    def test_resolve_topic_status_progression(
        self,
        artifact: str,
        expected: TopicStatus,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Each progression artifact alone resolves to its mapped status."""
        monkeypatch.chdir(tmp_path)
        topic_dir = tmp_path / ".goga" / "history" / "2026" / "t"
        artifact_path = topic_dir / artifact
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("artifact", encoding="utf-8")
        assert resolve_topic_status(topic_dir) is expected

    def test_resolve_topic_status_completed_wins_over_flat(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``completed/plan.md`` outranks every flat artifact present alongside it."""
        monkeypatch.chdir(tmp_path)
        topic_dir = tmp_path / ".goga" / "history" / "2026" / "t"
        topic_dir.mkdir(parents=True)
        (topic_dir / "prd.md").write_text("flat artifact", encoding="utf-8")
        (topic_dir / "plan.md").write_text("flat artifact", encoding="utf-8")
        (topic_dir / "completed").mkdir()
        (topic_dir / "completed" / "plan.md").write_text("nested artifact", encoding="utf-8")
        assert resolve_topic_status(topic_dir) is TopicStatus.done

    def test_resolve_topic_status_empty_when_no_artifact_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty or absent directory, and files outside the progression, resolve to empty."""
        monkeypatch.chdir(tmp_path)
        year_dir = tmp_path / ".goga" / "history" / "2026"
        empty_dir = year_dir / "empty-topic"
        empty_dir.mkdir(parents=True)
        assert resolve_topic_status(empty_dir) is TopicStatus.empty
        assert resolve_topic_status(year_dir / "absent-topic") is TopicStatus.empty
        stray_dir = year_dir / "stray-topic"
        stray_dir.mkdir(parents=True)
        (stray_dir / "notes.md").write_text("outside the progression", encoding="utf-8")
        assert resolve_topic_status(stray_dir) is TopicStatus.empty


class TestCollectTopicStatuses:
    def test_collect_topic_statuses_sorted_records(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only directories count as topics; records are sorted with resolved statuses."""
        monkeypatch.chdir(tmp_path)
        year_dir = tmp_path / ".goga" / "history" / "2026"
        (year_dir / "zeta").mkdir(parents=True)
        (year_dir / "alpha").mkdir(parents=True)
        (year_dir / "alpha" / "plan.md").write_text("plan", encoding="utf-8")
        (year_dir / "mid").mkdir(parents=True)
        (year_dir / "mid" / "prd.md").write_text("prd", encoding="utf-8")
        (year_dir / "stray.txt").write_text("not a topic", encoding="utf-8")
        records = collect_topic_statuses(year="2026")
        assert [record.topic for record in records] == ["alpha", "mid", "zeta"]
        assert records[0].status is TopicStatus.planned
        assert records[1].status is TopicStatus.defined
        assert records[2].status is TopicStatus.empty

    def test_collect_topic_statuses_absent_year_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An absent year yields an empty list — not an error, and nothing is created."""
        monkeypatch.chdir(tmp_path)
        assert collect_topic_statuses(year="1999") == []
        assert not (tmp_path / ".goga").exists()

    def test_collect_topic_statuses_empty_year_string_means_current(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A falsy year means the current year — not the history root's year children."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga" / "history" / "2025" / "old-topic").mkdir(parents=True)
        (tmp_path / ".goga" / "history" / "2031" / "t").mkdir(parents=True)
        with mock.patch.object(naming, "datetime", _FixedClock):
            records = collect_topic_statuses(year="")
        assert [record.topic for record in records] == ["t"]
        assert "2025" not in [record.topic for record in records]
        assert "2031" not in [record.topic for record in records]
