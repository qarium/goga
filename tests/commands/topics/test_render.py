"""Contract and logic tests for the entities declared in
``goga/commands/topics/CODEMANIFEST`` with ``location: render.py``:

- ``render_topic_board(records: list[BoardRecord], width: int)``

The board renderer is pure output: the collected records print as given —
no sorting, no filtering, no mutation — as a three-column table of topic,
branch, and statuses whose widths follow the P9 arithmetic. Output is
captured with ``capsys``.
"""

from __future__ import annotations

import inspect
import typing

import pytest
from goga.commands.topics import render, render_topic_board
from goga.topics import BoardRecord

# --- Contract tests ---


class TestRenderContract:
    def test_entity_is_importable_from_facade_and_callable(self) -> None:
        """``render_topic_board`` is importable from ``goga.commands.topics``."""
        assert render.render_topic_board is render_topic_board
        assert callable(render_topic_board)

    def test_render_topic_board_signature(self) -> None:
        """``render_topic_board(records: list[BoardRecord], width: int) -> None``."""
        signature = inspect.signature(render_topic_board)
        assert list(signature.parameters) == ["records", "width"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        hints = typing.get_type_hints(render_topic_board)
        assert hints == {"records": list[BoardRecord], "width": int, "return": type(None)}

    def test_render_topic_board_empty_input_prints_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An empty board renders not a single line — header included."""
        render_topic_board([], 80)
        assert capsys.readouterr().out == ""


# --- Logic tests ---


class TestRenderTopicBoard:
    def test_render_topic_board_widths_and_wrap(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Width 60 — thirds of 17, overlong cells truncated, statuses wrapped."""
        records = [
            BoardRecord(
                topic="very-long-topic-name-123",
                branch="feat/very-long-branch",
                statuses=["planned", "mkdocs.published"],
                current=False,
                remote=False,
            )
        ]
        render_topic_board(records, 60)
        lines = capsys.readouterr().out.splitlines()
        # usable = 51, so topic_cap = branch_cap = 17 and statuses_w = 17;
        # every grid line stays within the measured width.
        assert len(lines) == 4
        assert all(len(line) <= 60 for line in lines)
        assert lines[0].startswith("| Topic")
        assert "Branch" in lines[0]
        assert "Statuses" in lines[0]
        assert set(lines[1]) == {"-", "|"}
        # The topic and the branch exceed 17 columns — both carry the ellipsis.
        assert "…" in lines[2]
        # The first segment prints whole; the second one is 18 > 17 and
        # therefore appears truncated on the continuation line.
        assert "[planned]" in lines[2]
        assert "mkdocs.publis" in lines[3]
        assert "…" in lines[3]
        # The grid survives the wrap — empty topic and branch continuation cells.
        assert lines[3].startswith(f"|{' ' * 19}|{' ' * 19}|")
        # Read-only — the renderer does not mutate, re-sort, or filter the input.
        assert records[0].topic == "very-long-topic-name-123"
        assert records[0].statuses == ["planned", "mkdocs.published"]

    def test_render_topic_board_current_asterisk_and_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The current row carries the ``* `` marker; an empty board prints nothing."""
        records = [
            BoardRecord(
                topic="feat-a",
                branch="feat/a",
                statuses=["planned"],
                current=True,
                remote=False,
            )
        ]
        render_topic_board(records, 80)
        captured = capsys.readouterr()
        assert any(line.startswith("| * feat-a") for line in captured.out.splitlines())
        assert "[planned]" in captured.out
        render_topic_board([], 80)
        assert capsys.readouterr().out == ""

    def test_render_topic_board_degenerate_narrow_terminal(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Width 20 — every column keeps its minimum of 8, the table may exceed."""
        records = [
            BoardRecord(
                topic="a-very-long-topic",
                branch="feat/x",
                statuses=["done"],
                current=False,
                remote=False,
            )
        ]
        render_topic_board(records, 20)
        lines = capsys.readouterr().out.splitlines()
        # Three minimum-8 columns plus the grid overhead of 9 — the table is
        # 33 columns wide on a 20-column terminal: minimum readability wins.
        assert all(len(line) == 33 for line in lines)
        # Truncation still applies — the 17-column topic does not fit 8.
        assert "…" in lines[2]
        assert "feat/x" in lines[2]
        assert "[done]" in lines[2]

    @pytest.mark.parametrize(("width", "degenerate"), [(33, False), (32, True)])
    def test_render_topic_board_boundary_width_33_32(
        self, capsys: pytest.CaptureFixture[str], width: int, degenerate: bool
    ) -> None:
        """Width 33 splits evenly into the minimum thirds; 32 stays at them anyway."""
        records = [
            BoardRecord(topic="feat-a", branch="feat/a", statuses=["done"], current=False, remote=False),
            BoardRecord(
                topic="a-very-long-topic-name", branch="feat/x", statuses=["done"], current=False, remote=False
            ),
        ]
        render_topic_board(records, width)
        lines = capsys.readouterr().out.splitlines()
        # Both boundaries resolve to the 8/8/8 minimum layout — width 33 fits
        # the table exactly; width 32 is the documented one-column overflow.
        assert all(len(line) == 33 for line in lines)
        assert "feat-a" in lines[2]
        assert "[done]" in lines[2]
        assert "…" in lines[3]
        if degenerate:
            assert width < 33
        else:
            assert width == 33
