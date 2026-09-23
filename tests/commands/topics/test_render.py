"""Contract and logic tests for the entities declared in
``goga/commands/topics/CODEMANIFEST`` with ``location: render.py``:

- ``render_topic_board(entries: list[BoardEntry], width: int, info: bool = False)``
- ``render_topic_host_rows(records: list[BoardRecord], width: int, info: bool = False)``
- ``render_board_json(board: list[BoardEntry] | list[BoardRecord])``

The board renderers are pure output: the aggregated entries and the
per-host records print as given — no sorting, no filtering, no mutation.
The default view prints a four-column table of topic, branch, hosts, and
statuses, or a five-column table with the todo column between hosts and
statuses under ``info`` — the widths follow the quarters or the fifths
arithmetic of the active column rule. The audit view prints a
three-column table of topic, branch, and statuses, or a four-column table
with the todo column between branch and statuses — the thirds or the
quarters arithmetic. The JSON projection pretty-prints either view's
items. Output is captured with ``capsys``.
"""

from __future__ import annotations

import inspect
import json
import re
import typing

import pytest
from goga.commands.topics import (
    render,
    render_board_json,
    render_topic_board,
    render_topic_host_rows,
)
from goga.topics import BoardEntry, BoardRecord

# --- Contract tests ---


class TestRenderContract:
    def test_entity_is_importable_from_facade_and_callable(self) -> None:
        """``render_topic_board`` is importable from ``goga.commands.topics``."""
        assert render.render_topic_board is render_topic_board
        assert callable(render_topic_board)

    def test_render_topic_host_rows_is_importable_and_callable(self) -> None:
        """``render_topic_host_rows`` is importable from the cell facade."""
        assert render.render_topic_host_rows is render_topic_host_rows
        assert callable(render_topic_host_rows)

    def test_render_board_json_is_importable_and_callable(self) -> None:
        """``render_board_json`` is importable from the cell facade."""
        assert render.render_board_json is render_board_json
        assert callable(render_board_json)

    def test_render_topic_board_signature(self) -> None:
        """``render_topic_board(entries: list[BoardEntry], width: int, info: bool = False)``."""
        signature = inspect.signature(render_topic_board)
        assert list(signature.parameters) == ["entries", "width", "info"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        assert signature.parameters["info"].default is False
        hints = typing.get_type_hints(render_topic_board)
        assert hints == {"entries": list[BoardEntry], "width": int, "info": bool, "return": type(None)}

    def test_render_topic_host_rows_signature(self) -> None:
        """``render_topic_host_rows(records: list[BoardRecord], width: int, info: bool = False)``."""
        signature = inspect.signature(render_topic_host_rows)
        assert list(signature.parameters) == ["records", "width", "info"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        assert signature.parameters["info"].default is False
        hints = typing.get_type_hints(render_topic_host_rows)
        assert hints == {"records": list[BoardRecord], "width": int, "info": bool, "return": type(None)}

    def test_render_board_json_signature(self) -> None:
        """``render_board_json(board: list[BoardEntry] | list[BoardRecord])``."""
        signature = inspect.signature(render_board_json)
        assert list(signature.parameters) == ["board"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        hints = typing.get_type_hints(render_board_json)
        assert hints == {"board": list[BoardEntry] | list[BoardRecord], "return": type(None)}

    def test_render_topic_board_empty_input_prints_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An empty board renders not a single line — header included."""
        render_topic_board([], 80)
        assert capsys.readouterr().out == ""

    def test_render_topic_host_rows_empty_input_prints_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An empty audit board renders not a single line — header included."""
        render_topic_host_rows([], 80)
        assert capsys.readouterr().out == ""

    def test_render_topic_host_rows_info_header_is_the_word_todo_capitalized(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Under ``info`` the third column header is the word ``Todo``.

        The header cell pads to its column cap, so the assertion matches the
        literal ``| Todo`` run followed by padding spaces and the divider —
        a bare substring check would miss the padded cell.
        """
        records = [
            BoardRecord(
                topic="feat-a",
                branch="feat/a",
                statuses=["todo"],
                current=False,
                remote=False,
                todo="Pay retry cap",
            )
        ]
        render_topic_host_rows(records, 100, info=True)
        header_line = capsys.readouterr().out.splitlines()[0]
        assert re.search(r"\| Todo\s+\|", header_line)


# --- Logic tests: the audit view (one row per topic and hosting branch) ---


class TestRenderTopicHostRows:
    def test_render_topic_host_rows_widths_and_wrap(self, capsys: pytest.CaptureFixture[str]) -> None:
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
        render_topic_host_rows(records, 60)
        lines = capsys.readouterr().out.splitlines()
        # usable = 51, so topic_cap = branch_cap = 17 and statuses_w = 17;
        # every grid line stays within the measured width; the closing row
        # divider adds the fifth line.
        assert len(lines) == 5
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

    def test_render_topic_host_rows_current_asterisk_and_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
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
        render_topic_host_rows(records, 80)
        captured = capsys.readouterr()
        assert any(line.startswith("| * feat-a") for line in captured.out.splitlines())
        assert "[planned]" in captured.out
        render_topic_host_rows([], 80)
        assert capsys.readouterr().out == ""

    def test_render_topic_host_rows_degenerate_narrow_terminal(self, capsys: pytest.CaptureFixture[str]) -> None:
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
        render_topic_host_rows(records, 20)
        lines = capsys.readouterr().out.splitlines()
        # Three minimum-8 columns plus the grid overhead of 9 — the table is
        # 33 columns wide on a 20-column terminal: minimum readability wins.
        assert all(len(line) == 33 for line in lines)
        # Truncation still applies — the 17-column topic does not fit 8.
        assert "…" in lines[2]
        assert "feat/x" in lines[2]
        assert "[done]" in lines[2]

    @pytest.mark.parametrize("width", [33, 32])
    def test_render_topic_host_rows_boundary_width_33_32(self, capsys: pytest.CaptureFixture[str], width: int) -> None:
        """Width 33 splits evenly into the minimum thirds; 32 stays at them anyway."""
        records = [
            BoardRecord(topic="feat-a", branch="feat/a", statuses=["done"], current=False, remote=False),
            BoardRecord(
                topic="a-very-long-topic-name", branch="feat/x", statuses=["done"], current=False, remote=False
            ),
        ]
        render_topic_host_rows(records, width)
        lines = capsys.readouterr().out.splitlines()
        # Both boundaries resolve to the 8/8/8 minimum layout — width 33 fits
        # the table exactly; width 32 is the documented one-column overflow.
        assert all(len(line) == 33 for line in lines)
        assert "feat-a" in lines[2]
        assert "[done]" in lines[2]
        assert "…" in lines[4]

    def test_render_topic_host_rows_two_segments_fit_one_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Width 80 — two short status segments join on one statuses line."""
        records = [
            BoardRecord(
                topic="feat-a",
                branch="feat/a",
                statuses=["defined", "planned"],
                current=False,
                remote=False,
            )
        ]
        render_topic_host_rows(records, 80)
        lines = capsys.readouterr().out.splitlines()
        # usable = 71, so topic_cap = branch_cap = 23 and statuses_w = 25;
        # "[defined] [planned]" is 19 columns and fits — one data row plus
        # its closing row divider.
        assert len(lines) == 4
        assert "[defined] [planned]" in lines[2]
        assert all(len(line) <= 80 for line in lines)

    def test_render_topic_host_rows_three_columns_unchanged_without_info(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Regression gate — without ``info`` the three-column output is byte-identical."""
        records = [
            BoardRecord(
                topic="feat-a",
                branch="feat/a",
                statuses=["defined", "planned"],
                todo="Pay retry cap",
                current=False,
                remote=False,
            ),
            BoardRecord(
                topic="a-very-long-topic-name",
                branch="feat/x",
                statuses=["done"],
                todo=None,
                current=False,
                remote=False,
            ),
        ]
        render_topic_host_rows(records, 100)
        first = capsys.readouterr().out
        render_topic_host_rows(records, 100, info=False)
        second = capsys.readouterr().out
        # The explicit False and the default produce the very same bytes.
        assert first == second
        lines = first.splitlines()
        # usable = 91, so topic_cap = branch_cap = 30 and statuses_w = 31;
        # the header keeps the three columns — the todo stays invisible.
        assert lines[0].startswith("| Topic")
        assert not re.search(r"\| Todo\s+\|", lines[0])
        assert "Statuses" in lines[0]
        assert all(len(line) <= 100 for line in lines)
        assert "Pay retry cap" not in first

    @pytest.mark.parametrize("width", [33, 32])
    def test_render_topic_host_rows_three_column_narrow_threshold(
        self, capsys: pytest.CaptureFixture[str], width: int
    ) -> None:
        """Widths 33 and 32 without ``info`` stay on the 8/8/8 minimum thirds."""
        records = [
            BoardRecord(topic="feat-a", branch="feat/a", statuses=["done"], todo="T", current=False, remote=False)
        ]
        render_topic_host_rows(records, width)
        lines = capsys.readouterr().out.splitlines()
        # The narrow threshold of the three-column rule is 33 usable columns —
        # both boundaries resolve to the 8/8/8 minimum layout.
        assert all(len(line) == 33 for line in lines)
        assert lines[0].startswith("| Topic")
        assert not re.search(r"\| Todo\s+\|", lines[0])


class TestRenderTopicHostRowsInfo:
    def test_render_topic_host_rows_info_four_columns(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Width 100 under ``info`` — quarters of 22, the todo column visible."""
        records = [
            BoardRecord(
                topic="feat-a",
                branch="feat/a",
                statuses=["planned"],
                todo="Pay retry cap",
                current=False,
                remote=False,
            ),
            BoardRecord(
                topic="feat-b",
                branch="feat/b",
                statuses=["done"],
                todo="an-overlong-todo-summary-exceeding-cap",
                current=False,
                remote=False,
            ),
        ]
        render_topic_host_rows(records, 100, info=True)
        lines = capsys.readouterr().out.splitlines()
        # usable = 88, so every column takes a quarter — 22/22/22/22.
        assert lines[0].startswith("| Topic")
        assert "Branch" in lines[0]
        assert re.search(r"\| Todo\s+\|", lines[0])
        assert "Statuses" in lines[0]
        for line in lines:
            assert line.count("|") == 4
        assert all(len(line) <= 100 for line in lines)
        assert "Pay retry cap" in lines[2]
        # The 37-column summary exceeds its cap of 22 — truncated with the
        # ellipsis on the second record row, past the divider between the
        # two records.
        assert "…" in lines[4]
        assert "[planned]" in lines[2]
        assert "[done]" in lines[4]

    def test_render_info_column_carries_todo_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The ``info`` header carries the word todo and the record's todo summary."""
        records = [
            BoardRecord(
                topic="feat-a",
                branch="feat/a",
                statuses=["todo"],
                current=False,
                remote=False,
                todo="Pay retry cap",
            )
        ]
        render_topic_host_rows(records, 100, info=True)
        lines = capsys.readouterr().out.splitlines()
        # usable = 88, so every text column takes a quarter — (100 - 12) // 4 = 22.
        header_line = lines[0]
        assert re.search(r"\| Todo\s+\|", header_line)
        assert "Pay retry cap" in lines[2]

    @pytest.mark.parametrize("todo", [None, ""])
    def test_render_todo_none_renders_empty_cell(self, capsys: pytest.CaptureFixture[str], todo: str | None) -> None:
        """A todo of None or of the empty string renders an empty padded cell."""
        records = [
            BoardRecord(
                topic="feat-a",
                branch="feat/a",
                statuses=["planned"],
                todo=todo,
                current=False,
                remote=False,
            )
        ]
        render_topic_host_rows(records, 100, info=True)
        lines = capsys.readouterr().out.splitlines()
        # The cell between branch and statuses is the whitespace padding of a
        # 22-column cell — no text.
        cells = lines[2][2:-1].split(" | ")
        assert len(cells) == 4
        assert cells[2] == " " * 22
        assert len(lines[2]) == 100

    @pytest.mark.parametrize("width", [44, 43])
    def test_render_topic_host_rows_info_boundary_widths_44_43(
        self, capsys: pytest.CaptureFixture[str], width: int
    ) -> None:
        """Widths 44 and 43 under ``info`` — the narrow threshold of the quarters."""
        records = [
            BoardRecord(topic="feat-a", branch="feat/a", statuses=["done"], todo="T", current=False, remote=False)
        ]
        render_topic_host_rows(records, width, info=True)
        lines = capsys.readouterr().out.splitlines()
        # usable = width - 12: 44 gives exactly 32 = 8x4 — the table fits the
        # width; 43 gives 31 < 32 — the documented one-column overflow.
        assert all(len(line) == 44 for line in lines)
        assert lines[0].startswith("| Topic")
        assert re.search(r"\| Todo\s+\|", lines[0])
        assert "[done]" in lines[2]

    def test_render_topic_host_rows_info_wraps_statuses_with_empty_leading_cells(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Wrapped statuses under ``info`` continue on three empty leading cells."""
        records = [
            BoardRecord(
                topic="feat-a",
                branch="feat/a",
                statuses=["done", "planned"],
                todo="T",
                current=False,
                remote=False,
            )
        ]
        render_topic_host_rows(records, 44, info=True)
        lines = capsys.readouterr().out.splitlines()
        # usable = 32 = 8x4 — the minimum quarters; "[done]" and the
        # truncated "[planned]" cannot share the 8-column statuses cell;
        # the closing row divider adds the fifth line.
        assert len(lines) == 5
        assert "[done]" in lines[2]
        assert "[planne…" in lines[3]
        # The continuation row keeps the grid: topic, branch, and todo are
        # the empty padding of their columns — 10 columns per leading cell.
        assert lines[3].startswith(f"|{' ' * 10}|{' ' * 10}|{' ' * 10}|")
        assert len(lines[3]) == 44

    def test_render_topic_host_rows_info_empty_records_print_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An empty board under ``info`` renders not a single line — header included."""
        render_topic_host_rows([], 100, info=True)
        assert capsys.readouterr().out == ""


class TestRenderTopicHostRowsRowDividers:
    def test_render_topic_host_rows_row_divider_closes_every_record(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A row divider — the header separator's own line — closes every record.

        Two records print header, header separator, row, divider, row,
        divider: the divider after the last record included, and every
        divider byte-identical to the header separator.
        """
        records = [
            BoardRecord(topic="feat-a", branch="feat/a", statuses=["planned"], current=False, remote=False),
            BoardRecord(topic="feat-b", branch="feat/b", statuses=["done"], current=False, remote=False),
        ]
        render_topic_host_rows(records, 80)
        lines = capsys.readouterr().out.splitlines()
        assert len(lines) == 6
        assert lines[0].startswith("| Topic")
        # The dividers sit after every record — the last one included.
        assert lines[3] == lines[1]
        assert lines[5] == lines[1]
        assert set(lines[3]) == {"-", "|"}
        # The record rows themselves stay put between the dividers.
        assert "feat-a" in lines[2]
        assert "feat-b" in lines[4]

    def test_render_topic_host_rows_continuation_lines_stay_undivided(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The wrapped statuses of one record stay undivided — the divider
        closes the whole record, not every grid line."""
        records = [
            BoardRecord(
                topic="feat-a",
                branch="feat/a",
                statuses=["planned", "mkdocs.published"],
                current=False,
                remote=False,
            )
        ]
        render_topic_host_rows(records, 60)
        lines = capsys.readouterr().out.splitlines()
        # usable = 51 — the 18-column "[mkdocs.published]" wraps: the
        # continuation line directly follows its record row, and the single
        # divider closes the record after the continuation.
        assert lines[3].startswith(f"|{' ' * 19}|{' ' * 19}|")
        assert "mkdocs.publis" in lines[3]
        assert lines[4] == lines[1]

    def test_render_topic_host_rows_info_row_divider_closes_every_record(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Under ``info`` the dividers keep the four-pipe grid of the quarters."""
        records = [
            BoardRecord(topic="feat-a", branch="feat/a", statuses=["planned"], todo="T", current=False, remote=False),
            BoardRecord(topic="feat-b", branch="feat/b", statuses=["done"], todo=None, current=False, remote=False),
        ]
        render_topic_host_rows(records, 100, info=True)
        lines = capsys.readouterr().out.splitlines()
        assert len(lines) == 6
        assert lines[3] == lines[1]
        assert lines[5] == lines[1]
        for line in lines:
            assert line.count("|") == 4
        assert all(len(line) <= 100 for line in lines)
        assert "feat-a" in lines[2]
        assert "feat-b" in lines[4]


# --- Logic tests: the default view (one entry per topic) ---


class TestRenderTopicBoard:
    def test_render_topic_board_default_four_columns_with_hosts(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Width 100 — the four-column default grid: topic, branch, hosts, statuses.

        Every host name prints on its own grid line of the hosts column —
        the column never joins names into one run.
        """
        entry = BoardEntry(
            topic="feat-a",
            branch="feat/a",
            hosts=["feat/a", "main", "release/1.3.0"],
            statuses=["planned"],
            current=True,
            remote=False,
            todo="Fix.",
        )
        render_topic_board([entry], 100)
        lines = capsys.readouterr().out.splitlines()
        # usable = 88, so every column takes a quarter — 22 each; the hosts
        # column header is the word Hosts.
        columns = ("Topic", "Branch", "Hosts", "Statuses")
        assert lines[0] == "| " + " | ".join(column.ljust(22) for column in columns) + " "
        # The current marker sits in the topic cell of the first grid line.
        assert lines[2].startswith("| * feat-a")
        assert lines[2][2:-1].split(" | ")[2] == "feat/a".ljust(22)
        assert "[planned]" in lines[2]
        # Every host prints on its own continuation line, the earlier
        # columns empty.
        assert lines[3][2:-1].split(" | ")[2] == "main".ljust(22)
        assert lines[3].startswith(f"|{' ' * 24}|{' ' * 24}|")
        assert lines[4][2:-1].split(" | ")[2] == "release/1.3.0".ljust(22)
        assert lines[4].startswith(f"|{' ' * 24}|{' ' * 24}|")
        # One row divider closes the record — the last record included.
        assert len(lines) == 6
        assert lines[5] == lines[1]
        assert all(len(line) <= 100 for line in lines)
        # Read-only — the renderer does not mutate, re-sort, or filter the input.
        assert entry.hosts == ["feat/a", "main", "release/1.3.0"]
        assert entry.statuses == ["planned"]

    def test_render_topic_board_overlong_host_truncates_on_its_own_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A host longer than its column truncates with the ellipsis on its own line."""
        entry = BoardEntry(
            topic="feat-a",
            branch="feat/a",
            hosts=["feat/a", "release/1.3.0-with-a-long-suffix"],
            statuses=["planned"],
            current=False,
            remote=False,
        )
        render_topic_board([entry], 100)
        lines = capsys.readouterr().out.splitlines()
        # usable = 88 — a quarter of 22 per column; the 32-column host name
        # truncates to 21 columns plus the ellipsis on the second line.
        assert lines[2][2:-1].split(" | ")[2] == "feat/a".ljust(22)
        assert lines[3][2:-1].split(" | ")[2] == "release/1.3.0-with-a-…".ljust(22)
        assert "…" in lines[3]

    def test_render_topic_board_statuses_wrap_while_hosts_fit_one_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Statuses wrap onto continuation lines while the hosts fit the first line.

        The continuation lines carry empty leading cells — the topic, the
        branch, the hosts, and (under ``info``) the todo print on the first
        line alone; at width 60 the quarters give every column 12 and the
        fifths 9, so no two bracketed statuses share a line.
        """
        entry = BoardEntry(
            topic="feat-a",
            branch="feat/a",
            hosts=["feat/a"],
            statuses=["todo", "defined", "planned"],
            current=False,
            remote=False,
            todo="Fix.",
        )
        render_topic_board([entry], 60)
        lines = capsys.readouterr().out.splitlines()
        assert "feat/a" in lines[2]
        assert lines[2].endswith("[todo]".ljust(12) + " ")
        assert lines[3][2:-1].split(" | ") == [" " * 12, " " * 12, " " * 12, "[defined]".ljust(12)]
        assert lines[4][2:-1].split(" | ") == [" " * 12, " " * 12, " " * 12, "[planned]".ljust(12)]

        render_topic_board([entry], 60, info=True)
        lines = capsys.readouterr().out.splitlines()
        assert "Fix." in lines[2]
        assert lines[2].endswith("[todo]".ljust(9) + " ")
        # The todo cell blanks on the continuation line — the four leading
        # cells of the five-column grid are pure padding.
        assert lines[3][2:-1].split(" | ") == [" " * 9, " " * 9, " " * 9, " " * 9, "[defined]".ljust(9)]
        assert lines[4][2:-1].split(" | ") == [" " * 9, " " * 9, " " * 9, " " * 9, "[planned]".ljust(9)]

    def test_render_topic_board_info_five_columns_order(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Width 120 under ``info`` — fifths of 21, the todo column between hosts and statuses."""
        entry = BoardEntry(
            topic="feat-a",
            branch="feat/a",
            hosts=["feat/a", "main", "release/1.3.0"],
            statuses=["planned"],
            current=False,
            remote=False,
            todo="Fix.",
        )
        render_topic_board([entry], 120, info=True)
        lines = capsys.readouterr().out.splitlines()
        # usable = 105, so every column takes a fifth — 21 each; the column
        # order under info is topic, branch, hosts, todo, statuses.
        header_cells = lines[0][2:-1].split(" | ")
        assert [cell.strip() for cell in header_cells] == ["Topic", "Branch", "Hosts", "Todo", "Statuses"]
        cells = lines[2][2:-1].split(" | ")
        assert cells[2] == "feat/a".ljust(21)
        assert cells[3] == "Fix.".ljust(21)
        assert cells[4] == "[planned]".ljust(21)
        # The remaining hosts follow one per line on the continuation lines.
        assert lines[3][2:-1].split(" | ")[2] == "main".ljust(21)
        assert lines[4][2:-1].split(" | ")[2] == "release/1.3.0".ljust(21)
        assert all(len(line) <= 120 for line in lines)

    @pytest.mark.parametrize("todo", [None, ""])
    def test_render_topic_board_info_none_todo_renders_empty_cell(
        self, capsys: pytest.CaptureFixture[str], todo: str | None
    ) -> None:
        """A todo of None or of the empty string renders an empty padded cell."""
        entry = BoardEntry(
            topic="feat-a",
            branch="feat/a",
            hosts=["feat/a"],
            statuses=["planned"],
            current=False,
            remote=False,
            todo=todo,
        )
        render_topic_board([entry], 120, info=True)
        lines = capsys.readouterr().out.splitlines()
        # The cell between hosts and statuses is the whitespace padding of a
        # 21-column cell — no text.
        cells = lines[2][2:-1].split(" | ")
        assert cells[3] == " " * 21

    @pytest.mark.parametrize(
        ("width", "info", "dash_run"),
        [(100, False, 24), (125, True, 24), (43, False, 10), (54, True, 10)],
    )
    def test_render_topic_board_width_rules_quarter_and_fifth(
        self, capsys: pytest.CaptureFixture[str], width: int, info: bool, dash_run: int
    ) -> None:
        """The quarters and fifths rules and their all-min-8 floors.

        usable(100, 4) = 88 -> 22 per column -> dash runs of 24;
        usable(125, 5) = 110 -> 22 per column -> dash runs of 24. Below the
        narrow thresholds — 44 at k=4, 55 at k=5 — every dash run shrinks
        to the 8+2 padding of the minimum layout.
        """
        entry = BoardEntry(
            topic="feat-a",
            branch="feat/a",
            hosts=["feat/a"],
            statuses=["planned"],
            current=False,
            remote=False,
        )
        render_topic_board([entry], width, info=info)
        lines = capsys.readouterr().out.splitlines()
        separator = lines[1]
        columns_count = 5 if info else 4
        assert separator == "|" + "|".join("-" * dash_run for _ in range(columns_count))
        # On the minimum layout the table may exceed the terminal — the
        # documented narrow-threshold exception; otherwise it never does.
        table_width = columns_count * 11 if dash_run == 10 else width
        assert all(len(line) <= table_width for line in lines)

    def test_render_topic_host_rows_matches_established_layout(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The audit view keeps its established byte layout after the rename.

        The moved body renders the very same grid as before: at width 80 the
        thirds give topic and branch 23 columns and statuses 25.
        """
        records = [BoardRecord(topic="feat-a", branch="feat/a", statuses=["planned"], current=False, remote=False)]
        render_topic_host_rows(records, 80)
        expected = (
            "\n".join(
                [
                    "| " + " | ".join(("Topic".ljust(23), "Branch".ljust(23), "Statuses".ljust(25))) + " ",
                    "|" + "|".join(("-" * 25, "-" * 25, "-" * 27)),
                    "| " + " | ".join(("feat-a".ljust(23), "feat/a".ljust(23), "[planned]".ljust(25))) + " ",
                    "|" + "|".join(("-" * 25, "-" * 25, "-" * 27)),
                ]
            )
            + "\n"
        )
        assert capsys.readouterr().out == expected

    def test_render_topic_board_empty_board_and_info(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An empty board prints nothing — with and without ``info``."""
        render_topic_board([], 100)
        assert capsys.readouterr().out == ""
        render_topic_board([], 100, info=True)
        assert capsys.readouterr().out == ""


# --- Logic tests: the JSON projection ---


class TestRenderBoardJson:
    def test_render_board_json_empty_board(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An empty board prints the empty JSON array with one trailing newline."""
        render_board_json([])
        assert capsys.readouterr().out == "[]\n"

    def test_render_board_json_entry_and_record_shapes(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An entry projects with the hosts key; a record without it — todo always present."""
        entry = BoardEntry(
            topic="feat-a",
            branch="feat/a",
            hosts=["feat/a", "main"],
            statuses=["planned"],
            current=True,
            remote=False,
            todo="Fix.",
        )
        render_board_json([entry])
        captured = capsys.readouterr().out
        assert json.loads(captured) == [
            {
                "topic": "feat-a",
                "branch": "feat/a",
                "hosts": ["feat/a", "main"],
                "statuses": ["planned"],
                "current": True,
                "remote": False,
                "todo": "Fix.",
            }
        ]
        # indent=4 pretty-printing — the array opens with a four-space member.
        assert captured.startswith("[\n    {")

        record = BoardRecord(
            topic="feat-a",
            branch="feat/a",
            statuses=["planned"],
            current=True,
            remote=False,
            todo=None,
        )
        render_board_json([record])
        captured = capsys.readouterr().out
        assert json.loads(captured) == [
            {
                "topic": "feat-a",
                "branch": "feat/a",
                "statuses": ["planned"],
                "current": True,
                "remote": False,
                "todo": None,
            }
        ]
        assert captured.startswith("[\n    {")
        # Read-only — the items project as given.
        assert entry.hosts == ["feat/a", "main"]
        assert record.todo is None

    def test_render_board_json_non_ascii_stays_raw_utf8(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Non-ASCII content prints as raw UTF-8 — never as \\u escapes."""
        entry = BoardEntry(
            topic="feature-foo-bar",
            branch="origin/Feature/Foo_Bar",
            hosts=["origin/Feature/Foo_Bar", "main"],
            statuses=["todo"],
            current=False,
            remote=True,
            todo="Оплата повторно",
        )
        render_board_json([entry])
        captured = capsys.readouterr().out

        assert "Оплата повторно" in captured
        assert "\\u" not in captured
