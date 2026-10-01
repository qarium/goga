"""Contract and logic tests for the entity declared in
``goga/onboarding/questions/CODEMANIFEST`` with ``location: answers.py``:

- ``SessionAnswers(tools)`` — the answer space of one session, the single
  mutable accumulator of the run

The space is total and silent — nested mappings keyed by question ids, no
dotted keys ever stored, no logging, nothing raised.
"""

from __future__ import annotations

from goga.onboarding.questions import SessionAnswers

_CELL_ALL = ["Question", "QuestionGroup", "SessionAnswers"]

# --- Contract tests ---


class TestSessionAnswersContract:
    def test_entity_is_importable_from_the_package_facade(self) -> None:
        """The accumulator lives on the cell package and its ``__all__`` is exact."""
        import goga.onboarding.questions as cell

        assert cell.SessionAnswers is SessionAnswers
        assert cell.__all__ == _CELL_ALL

    def test_both_constructions_create_an_empty_space(self) -> None:
        """With and without reserved tool sections the space starts empty."""
        assert SessionAnswers().snapshot() == {}

        assert SessionAnswers(tools=["my-tool"]).snapshot() == {}

    def test_reserved_names_do_not_create_tool_sections(self) -> None:
        """``tools`` reserves the top-level keys without creating them."""
        answers = SessionAnswers(tools=["my-tool", "viewer"])

        assert answers.snapshot() == {}


# --- Logic tests ---


class TestRecord:
    def test_record_creates_nested_mappings(self) -> None:
        """A dot-path lands as nested mappings keyed by the segments."""
        answers = SessionAnswers()

        answers.record("build.agent", "claude")

        assert answers.snapshot() == {"build": {"agent": "claude"}}

    def test_record_replaces_the_earlier_value_at_the_same_path(self) -> None:
        """Recording replaces — merging belongs to amendments."""
        answers = SessionAnswers()
        answers.record("build.agent", "claude")

        answers.record("build.agent", "codex")

        assert answers.snapshot() == {"build": {"agent": "codex"}}

    def test_record_over_scalar_extends_to_a_mapping(self) -> None:
        """The survey is the authoritative writer — a scalar mid-path yields."""
        answers = SessionAnswers()
        answers.record("a.b", 1)

        answers.record("a.b.c", 2)

        assert answers.snapshot() == {"a": {"b": {"c": 2}}}


class TestAmend:
    def test_amend_merges_mappings_replaces_scalars(self) -> None:
        """Mappings merge recursively; scalars replace."""
        answers = SessionAnswers()
        answers.record("pipeline", {"agent": "codex", "env": {"A": "1"}})

        answers.amend("pipeline", {"env": {"B": "2"}, "agent": "claude"})

        assert answers.snapshot() == {"pipeline": {"agent": "claude", "env": {"A": "1", "B": "2"}}}

    def test_amend_creates_an_absent_leaf(self) -> None:
        """An amendment of a fresh path creates the whole branch silently."""
        answers = SessionAnswers()

        answers.amend("tools", {"my-tool": "latest"})

        assert answers.snapshot() == {"tools": {"my-tool": "latest"}}

    def test_amend_replaces_when_either_side_is_not_a_mapping(self) -> None:
        """The merge happens only when both sides are mappings."""
        answers = SessionAnswers()
        answers.record("flags", {"a": 1})

        answers.amend("flags", "on")

        assert answers.snapshot() == {"flags": "on"}

        answers.amend("flags", {"b": 2})

        assert answers.snapshot() == {"flags": {"b": 2}}

    def test_amend_replaces_lists(self) -> None:
        """Lists replace — only mappings merge."""
        answers = SessionAnswers()
        answers.record("items", ["a"])

        answers.amend("items", ["b", "c"])

        assert answers.snapshot() == {"items": ["b", "c"]}

    def test_later_amendment_wins_at_every_conflicting_leaf(self) -> None:
        """Amendments apply in delivery order — the later one wins."""
        answers = SessionAnswers()

        answers.amend("env", {"A": "1", "B": "1"})
        answers.amend("env", {"B": "2"})

        assert answers.snapshot() == {"env": {"A": "1", "B": "2"}}


class TestViewFor:
    def test_view_for_isolates_and_flattens(self) -> None:
        """Core plus the tool's own section under local names; no other tools."""
        answers = SessionAnswers(tools=["my-tool", "viewer"])
        answers.record("language", "python")
        answers.record("my-tool.token", "t0")
        answers.record("viewer.flag", "on")

        view = answers.view_for("my-tool")

        assert view == {"language": "python", "token": "t0"}
        assert "viewer" not in view

        view["token"] = "mutated"

        assert answers.snapshot()["my-tool"]["token"] == "t0"

    def test_view_for_unknown_tool_returns_core_only(self) -> None:
        """A tool without a recorded section sees the core only."""
        answers = SessionAnswers(tools=["my-tool"])
        answers.record("language", "python")
        answers.record("my-tool.token", "t0")

        assert answers.view_for("not-declared") == {"language": "python"}

    def test_local_name_collision_with_core_key_wins_in_that_view_only(self) -> None:
        """The own section is applied after the core — the space stays intact."""
        answers = SessionAnswers(tools=["my-tool"])
        answers.record("language", "python")
        answers.record("my-tool.language", "golang")

        assert answers.view_for("my-tool") == {"language": "golang"}
        assert answers.snapshot() == {"language": "python", "my-tool": {"language": "golang"}}

    def test_view_for_is_a_deep_copy_of_the_core(self) -> None:
        """Mutating a nested value of the view does not touch the space."""
        answers = SessionAnswers(tools=["t"])
        answers.record("build", {"env": {"A": "1"}})

        view = answers.view_for("t")
        view["build"]["env"]["A"] = "mutated"

        assert answers.snapshot() == {"build": {"env": {"A": "1"}}}

    def test_reserved_names_come_from_the_constructor_param(self) -> None:
        """No hardcoded section list — the reservation is the caller's data."""
        answers = SessionAnswers(tools=["custom-tool"])
        answers.record("custom-tool.token", "t0")
        answers.record("language", "python")

        assert answers.view_for("custom-tool") == {"language": "python", "token": "t0"}


class TestSnapshot:
    def test_snapshot_reflects_the_committed_state(self) -> None:
        """The whole space — the core and every committed tool section."""
        answers = SessionAnswers(tools=["my-tool"])
        answers.record("language", "python")
        answers.record("my-tool.token", "t0")

        assert answers.snapshot() == {"language": "python", "my-tool": {"token": "t0"}}

    def test_snapshot_is_a_deep_copy(self) -> None:
        """Mutating the snapshot does not touch the space."""
        answers = SessionAnswers()
        answers.record("build", {"env": {"A": "1"}})

        view = answers.snapshot()
        view["build"]["env"]["A"] = "mutated"

        assert answers.snapshot() == {"build": {"env": {"A": "1"}}}
