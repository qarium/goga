"""Contract and logic tests for the entities declared in
``goga/history/CODEMANIFEST`` with ``location: status.py``:

- ``TopicRecord(topic: str, statuses: list[str])``
- ``resolve_topic_status(topic_dir: Path, scale: StatusScale) -> statuses: list[str]``
- ``collect_topic_statuses(year: str | None = None, scale: StatusScale | None = None) -> records: list[TopicRecord]``

The resolver and the collector are read-only with respect to the filesystem;
the scale is a parameter assembled once per command run — never here per
topic. The mocks are patched at their import sites: ``naming.datetime`` (the
mandated bare-``now()`` point) and ``status.assemble_status_scale`` (the
assembly reuse counter). Filesystem fixtures use ``tmp_path`` +
``monkeypatch.chdir``; the scale fixtures are hand-assembled lists of
``Stage``, per the design scenarios.
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
    collect_topic_statuses,
    resolve_topic_status,
)
from goga.history.statuses import Stage, StatusScale

from tests.conftest import is_kw_only_dataclass


class _FixedClock:
    """Stand-in for ``datetime`` answering a fixed naive date."""

    @staticmethod
    def now() -> datetime:
        return datetime(2031, 6, 15)  # noqa: DTZ001 — a fixed naive date is the point of the clock


def _builtin_scale() -> StatusScale:
    """Deterministic built-in scale — nine entries with the contract artifacts."""
    return StatusScale(
        stages=[
            Stage(name="empty", filepath=""),
            Stage(name="todo", filepath="todo.md"),
            Stage(name="defined", filepath="prd.md"),
            Stage(name="discovered", filepath="adr.md"),
            Stage(name="backlog", filepath="task.md"),
            Stage(name="designed", filepath="arch.md"),
            Stage(name="specified", filepath="design.md"),
            Stage(name="planned", filepath="plan.md"),
            Stage(name="done", filepath="completed/plan.md"),
        ]
    )


def _tool_scale() -> StatusScale:
    """Built-in scale plus one tool entry anchored after ``planned``."""
    return StatusScale(
        stages=[
            *_builtin_scale().stages,
            Stage(name="mkdocs.published", filepath="mkdocs/published.md", after="planned"),
        ]
    )


# --- Contract tests ---


class TestStatusContract:
    def test_entities_are_importable_from_module_and_callable(self) -> None:
        """All three entities are importable from ``goga.history.status``."""
        assert status.TopicRecord is TopicRecord
        assert callable(resolve_topic_status)
        assert callable(collect_topic_statuses)
        assert status.resolve_topic_status is resolve_topic_status
        assert status.collect_topic_statuses is collect_topic_statuses

    def test_facade_reexports_the_status_names(self) -> None:
        """The status entities are importable from the domain facade."""
        import goga.history

        assert goga.history.TopicRecord is TopicRecord
        assert goga.history.resolve_topic_status is resolve_topic_status
        assert goga.history.collect_topic_statuses is collect_topic_statuses
        for name in ("TopicRecord", "resolve_topic_status", "collect_topic_statuses"):
            assert name in goga.history.__all__

    def test_single_status_enum_is_deleted(self) -> None:
        """``TopicStatus`` and the artifact progression constant are gone from the module."""
        assert not hasattr(status, "TopicStatus")
        assert not hasattr(status, "_ARTIFACT_PROGRESSION")

    def test_topic_record_is_frozen_kw_only_dataclass(self) -> None:
        """``@dataclass(frozen=True, kw_only=True)`` with the fields ``topic`` and ``statuses``."""
        assert dataclasses.is_dataclass(TopicRecord)
        assert TopicRecord.__dataclass_params__.frozen is True
        assert is_kw_only_dataclass(TopicRecord)
        assert typing.get_type_hints(TopicRecord) == {"topic": str, "statuses": list[str]}
        record = TopicRecord(topic="t", statuses=["planned", "mkdocs.published"])
        assert record.topic == "t"
        assert record.statuses == ["planned", "mkdocs.published"]
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.topic = "other"  # type: ignore[misc]
        with pytest.raises(TypeError):
            TopicRecord("t", ["planned"])  # type: ignore[misc]

    def test_resolve_topic_status_signature(self) -> None:
        """``resolve_topic_status(topic_dir: Path, scale: StatusScale) -> list[str]``."""
        signature = inspect.signature(resolve_topic_status)
        assert list(signature.parameters) == ["topic_dir", "scale"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        hints = typing.get_type_hints(resolve_topic_status)
        assert hints == {"topic_dir": Path, "scale": StatusScale, "return": list[str]}

    def test_collect_topic_statuses_signature(self) -> None:
        """``collect_topic_statuses(year=None, scale=None) -> list[TopicRecord]``."""
        signature = inspect.signature(collect_topic_statuses)
        assert list(signature.parameters) == ["year", "scale"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        assert signature.parameters["scale"].default is None
        hints = typing.get_type_hints(collect_topic_statuses)
        assert hints == {"year": str | None, "scale": StatusScale | None, "return": list[TopicRecord]}


# --- Logic tests ---


class TestResolveTopicStatus:
    @pytest.mark.parametrize(
        ("artifact", "expected"),
        [
            ("todo.md", ["todo"]),
            ("prd.md", ["defined"]),
            ("adr.md", ["discovered"]),
            ("task.md", ["backlog"]),
            ("arch.md", ["designed"]),
            ("design.md", ["specified"]),
            ("plan.md", ["planned"]),
            ("completed/plan.md", ["done"]),
        ],
    )
    def test_resolve_topic_status_progression(
        self,
        artifact: str,
        expected: list[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Each progression artifact alone resolves to its mapped status."""
        monkeypatch.chdir(tmp_path)
        topic_dir = tmp_path / ".goga" / "history" / "2026" / "t"
        artifact_path = topic_dir / artifact
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("artifact", encoding="utf-8")
        assert resolve_topic_status(topic_dir, _builtin_scale()) == expected

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
        assert resolve_topic_status(topic_dir, _builtin_scale()) == ["done"]

    def test_resolve_topic_status_empty_when_no_artifact_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty or absent directory, and files outside the scale, resolve to empty."""
        monkeypatch.chdir(tmp_path)
        year_dir = tmp_path / ".goga" / "history" / "2026"
        empty_dir = year_dir / "empty-topic"
        empty_dir.mkdir(parents=True)
        assert resolve_topic_status(empty_dir, _builtin_scale()) == ["empty"]
        assert resolve_topic_status(year_dir / "absent-topic", _builtin_scale()) == ["empty"]
        stray_dir = year_dir / "stray-topic"
        stray_dir.mkdir(parents=True)
        (stray_dir / "notes.md").write_text("outside the scale", encoding="utf-8")
        assert resolve_topic_status(stray_dir, _builtin_scale()) == ["empty"]

    def test_resolve_topic_status_multi_statuses(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A tool artifact outranks the built-in entry it is anchored after."""
        monkeypatch.chdir(tmp_path)
        year_dir = tmp_path / ".goga" / "history" / "2026"
        tool_topic = year_dir / "release-1-3-0"
        (tool_topic / "mkdocs").mkdir(parents=True)
        (tool_topic / "plan.md").write_text("plan", encoding="utf-8")
        (tool_topic / "mkdocs" / "published.md").write_text("published", encoding="utf-8")
        assert resolve_topic_status(tool_topic, _tool_scale()) == ["mkdocs.published"]
        plain_topic = year_dir / "plain"
        plain_topic.mkdir(parents=True)
        (plain_topic / "plan.md").write_text("plan", encoding="utf-8")
        assert resolve_topic_status(plain_topic, _tool_scale()) == ["planned"]


class TestCollectTopicStatuses:
    def test_collect_topic_statuses_sorted_records(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only directories count as topics; records are sorted with resolved statuses."""
        monkeypatch.chdir(tmp_path)
        year_dir = tmp_path / ".goga" / "history" / "2026"
        (year_dir / "zeta").mkdir(parents=True)
        (year_dir / "alpha").mkdir(parents=True)
        (year_dir / "alpha" / "plan.md").write_text("plan", encoding="utf-8")
        (year_dir / "mid").mkdir(parents=True)
        (year_dir / "mid" / "prd.md").write_text("prd", encoding="utf-8")
        (year_dir / "stray.txt").write_text("not a topic", encoding="utf-8")
        records = collect_topic_statuses(year="2026", scale=_builtin_scale())
        assert [record.topic for record in records] == ["alpha", "mid", "zeta"]
        assert records[0].statuses == ["planned"]
        assert records[1].statuses == ["defined"]
        assert records[2].statuses == ["empty"]

    def test_collect_topic_statuses_reuses_scale(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A passed scale is used as-is — the assembly is not repeated per run."""
        monkeypatch.chdir(tmp_path)
        year_dir = tmp_path / ".goga" / "history" / "2026"
        (year_dir / "alpha").mkdir(parents=True)
        (year_dir / "alpha" / "plan.md").write_text("plan", encoding="utf-8")
        (year_dir / "beta").mkdir(parents=True)
        assembly = mock.patch.object(status, "assemble_status_scale", wraps=status.assemble_status_scale)
        with assembly as assemble:
            records = collect_topic_statuses("2026", _builtin_scale())
        assert [record.topic for record in records] == ["alpha", "beta"]
        assert records[0].statuses == ["planned"]
        assert records[1].statuses == ["empty"]
        assert assemble.call_count == 0

    def test_collect_topic_statuses_assembles_scale_once_when_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``scale=None`` assembles the scale exactly once for the whole run."""
        monkeypatch.chdir(tmp_path)
        year_dir = tmp_path / ".goga" / "history" / "2026"
        (year_dir / "alpha").mkdir(parents=True)
        (year_dir / "alpha" / "plan.md").write_text("plan", encoding="utf-8")
        (year_dir / "beta").mkdir(parents=True)
        with mock.patch.object(status, "assemble_status_scale", return_value=_builtin_scale()) as assemble:
            records = collect_topic_statuses("2026")
        assert [record.topic for record in records] == ["alpha", "beta"]
        assert records[0].statuses == ["planned"]
        assert records[1].statuses == ["empty"]
        assert assemble.call_count == 1

    def test_collect_topic_statuses_absent_year_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An absent year yields an empty list — not an error, and nothing is created."""
        monkeypatch.chdir(tmp_path)
        assert collect_topic_statuses(year="1999", scale=_builtin_scale()) == []
        assert not (tmp_path / ".goga").exists()

    def test_collect_topic_statuses_empty_year_string_means_current(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A falsy year means the current year — not the history root's year children."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga" / "history" / "2025" / "old-topic").mkdir(parents=True)
        (tmp_path / ".goga" / "history" / "2031" / "t").mkdir(parents=True)
        with mock.patch.object(naming, "datetime", _FixedClock):
            records = collect_topic_statuses(year="", scale=_builtin_scale())
        assert [record.topic for record in records] == ["t"]
        assert "2025" not in [record.topic for record in records]
        assert "2031" not in [record.topic for record in records]
