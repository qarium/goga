"""Contract and logic tests for the entities declared in
``goga/onboarding/questions/CODEMANIFEST`` with ``location: questions.py``:

- ``Question(id, kind, prompt, choices, default, keys)`` — one declarative
  question record, the survey unit of the session
- ``QuestionGroup(id, prompt, children)`` — one nesting node of the question
  tree

Data only — no validation, no rendering: the records are immutable declarative
data of the survey; kinds are checked at ask time.
"""

from __future__ import annotations

import dataclasses

import pytest
from goga.onboarding.questions import Question, QuestionGroup

from tests.conftest import is_kw_only_dataclass

_CELL_ALL = ["Question", "QuestionGroup", "SessionAnswers"]

# --- Contract tests ---


class TestQuestionsContract:
    def test_entities_are_importable_from_the_package_facade(self) -> None:
        """Both records live on the cell package and its ``__all__`` is exact."""
        import goga.onboarding.questions as cell

        assert cell.Question is Question
        assert cell.QuestionGroup is QuestionGroup
        assert cell.__all__ == _CELL_ALL

    def test_question_is_a_kw_only_frozen_dataclass(self) -> None:
        """``Question(id=..., kind=..., prompt=...)`` — keyword-only, frozen."""
        question = Question(id="token", kind="input", prompt="Service token")

        assert question.id == "token"
        assert question.kind == "input"
        assert question.prompt == "Service token"

        assert dataclasses.is_dataclass(Question)
        assert Question.__dataclass_params__.frozen
        assert is_kw_only_dataclass(Question)

        with pytest.raises(TypeError):
            Question("token", "input", "Service token")  # type: ignore[misc]

    def test_question_assignment_raises_frozen_instance_error(self) -> None:
        """A declared record is never rewritten."""
        question = Question(id="token", kind="input", prompt="Service token")

        with pytest.raises(dataclasses.FrozenInstanceError):
            question.prompt = "Other"  # type: ignore[misc]

    def test_question_carries_exactly_the_six_declared_fields(self) -> None:
        """No computed properties, no extra state — the record is data only."""
        field_names = [field.name for field in dataclasses.fields(Question)]

        assert field_names == ["id", "kind", "prompt", "choices", "default", "keys"]

    def test_question_group_constructs_without_prompt(self) -> None:
        """A purely structural node carries no prompt and no children."""
        group = QuestionGroup(id="g", children=None)

        assert group.id == "g"
        assert group.prompt is None
        assert group.children is None

        assert dataclasses.is_dataclass(QuestionGroup)
        assert QuestionGroup.__dataclass_params__.frozen
        assert is_kw_only_dataclass(QuestionGroup)

        with pytest.raises(TypeError):
            QuestionGroup("g")  # type: ignore[misc]

    def test_question_group_assignment_raises_frozen_instance_error(self) -> None:
        """A declared group is never rewritten."""
        group = QuestionGroup(id="g")

        with pytest.raises(dataclasses.FrozenInstanceError):
            group.prompt = "--- Section ---"  # type: ignore[misc]

    def test_question_group_carries_exactly_the_three_declared_fields(self) -> None:
        """No computed properties, no extra state — the record is data only."""
        field_names = [field.name for field in dataclasses.fields(QuestionGroup)]

        assert field_names == ["id", "prompt", "children"]


# --- Logic tests ---


class TestQuestionRecords:
    def test_question_exposes_all_fields_with_given_values(self) -> None:
        """Every parameterization field round-trips with the given value."""
        question = Question(id="q", kind="choice", prompt="Pick", choices=["a", "b"], default="a")

        assert question.id == "q"
        assert question.kind == "choice"
        assert question.prompt == "Pick"
        assert question.choices == ["a", "b"]
        assert question.default == "a"
        assert question.keys is None

    def test_group_round_trips_children_in_survey_order(self) -> None:
        """A group holds the nested questions and groups, in order."""
        inner = Question(id="x", kind="input", prompt="X")
        deeper = QuestionGroup(id="nested", children=[inner])
        group = QuestionGroup(id="g", prompt="--- G ---", children=[inner, deeper])

        assert group.children == [inner, deeper]
        assert group.children[0].id == "x"
        assert group.children[1].children == [inner]

    def test_optional_fields_default_to_none(self) -> None:
        """``None`` is the explicit absence of a parameterization."""
        question = Question(id="q", kind="input", prompt="P")
        group = QuestionGroup(id="g")

        assert question.choices is None
        assert question.default is None
        assert question.keys is None
        assert group.prompt is None
        assert group.children is None

    def test_construction_performs_no_kind_validation(self) -> None:
        """Kinds are checked at ask time — an unknown kind constructs."""
        question = Question(id="bad", kind="text", prompt="Weird")

        assert question.kind == "text"

    def test_records_are_hashable_value_objects(self) -> None:
        """Frozen records compare and hash by value."""
        first = Question(id="q", kind="input", prompt="P")
        second = Question(id="q", kind="input", prompt="P")

        assert first == second
        assert len({first, second}) == 1

        left = QuestionGroup(id="g")
        right = QuestionGroup(id="g")

        assert left == right
        assert len({left, right}) == 1
