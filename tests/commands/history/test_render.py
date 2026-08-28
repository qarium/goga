"""Contract and logic tests for the entities declared in
``goga/commands/history/CODEMANIFEST`` with ``location: render.py``:

- ``render_history_tree(tree: list[HistoryYear])``
- ``render_topic_statuses(records: list[TopicRecord])``

The renderers are pure output: what the input carries is printed as given —
no sorting, no filtering, no computation, and the year of a status record is
never printed. Output is captured with ``capsys``; the color test mocks
``click.secho`` at the import point of the render module.
"""

from __future__ import annotations

import inspect
import typing
from unittest import mock

import pytest
from goga.commands.history import render
from goga.commands.history.render import render_history_tree, render_topic_statuses
from goga.history import HistoryYear, TopicRecord, TopicStatus

# --- Contract tests ---


class TestRenderContract:
    def test_entities_are_importable_from_module_and_callable(self) -> None:
        """Both renderers are importable from ``goga.commands.history.render``."""
        assert render.render_history_tree is render_history_tree
        assert render.render_topic_statuses is render_topic_statuses
        assert callable(render_history_tree)
        assert callable(render_topic_statuses)

    def test_render_history_tree_signature(self) -> None:
        """``render_history_tree(tree: list[HistoryYear]) -> None``."""
        signature = inspect.signature(render_history_tree)
        assert list(signature.parameters) == ["tree"]
        assert signature.parameters["tree"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        hints = typing.get_type_hints(render_history_tree)
        assert hints == {"tree": list[HistoryYear], "return": type(None)}

    def test_render_topic_statuses_signature(self) -> None:
        """``render_topic_statuses(records: list[TopicRecord]) -> None``."""
        signature = inspect.signature(render_topic_statuses)
        assert list(signature.parameters) == ["records"]
        assert signature.parameters["records"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        hints = typing.get_type_hints(render_topic_statuses)
        assert hints == {"records": list[TopicRecord], "return": type(None)}


# --- Logic tests ---


class TestRenderHistoryTree:
    def test_render_history_tree_lines(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Each year prints ``YYYY/`` and each topic an indented marker line under it."""
        tree = [
            HistoryYear(year="2025", topics=["a-topic", "b-topic"]),
            HistoryYear(year="2026", topics=["history-commands"]),
        ]
        render_history_tree(tree)
        assert capsys.readouterr().out == "2025/\n └── a-topic\n └── b-topic\n2026/\n └── history-commands\n"

    def test_render_history_tree_empty_input_prints_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An empty tree renders not a single line."""
        render_history_tree([])
        assert capsys.readouterr().out == ""

    def test_render_history_tree_does_not_mutate_input(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Topics print in the given order — the renderer does not re-sort or mutate."""
        tree = [HistoryYear(year="2025", topics=["z-topic", "a-topic"])]
        render_history_tree(tree)
        capsys.readouterr()
        assert tree[0].topics == ["z-topic", "a-topic"]


class TestRenderTopicStatuses:
    def test_render_topic_statuses_no_color_plain(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-empty NO_COLOR keeps every segment plain — no ANSI escapes."""
        monkeypatch.setenv("NO_COLOR", "1")
        render_topic_statuses([TopicRecord(topic="t", status=TopicStatus.planned)])
        captured = capsys.readouterr()
        assert captured.out.strip() == "t [planned]"
        assert "\x1b" not in captured.out

    def test_render_topic_statuses_colors_status_segment(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One color on the status segment; the topic stays plain with no newline."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        with mock.patch.object(render.click, "secho") as secho_mock:
            render_topic_statuses([TopicRecord(topic="t", status=TopicStatus.planned)])
        assert secho_mock.call_args == mock.call("[planned]", fg="cyan")
        assert capsys.readouterr().out == "t "

    def test_render_topic_statuses_empty_input_prints_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Empty records render not a single line — an empty result is not an error."""
        render_topic_statuses([])
        assert capsys.readouterr().out == ""

    def test_render_topic_statuses_keeps_input_order(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Records print in the given order — the renderer neither sorts nor filters."""
        monkeypatch.setenv("NO_COLOR", "1")
        records = [
            TopicRecord(topic="zeta", status=TopicStatus.empty),
            TopicRecord(topic="alpha", status=TopicStatus.done),
        ]
        render_topic_statuses(records)
        assert capsys.readouterr().out == "zeta [empty]\nalpha [done]\n"
        assert [record.topic for record in records] == ["zeta", "alpha"]
