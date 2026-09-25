"""Contract and logic tests for the entity declared in
``goga/onboarding/participation/CODEMANIFEST`` with ``location: declaration.py``:

- ``ToolDeclaration(tool, invited)`` — the moment-one surface of one tool,
  the session declaration context and its buffer

The surface buffers what a declare-session hook declares — the questions and
the skip paths. Structural violations are warnings, never exceptions; the
engine reads the buffers after the delivery of the moment completes.
"""

from __future__ import annotations

import logging

import pytest
from goga.hooks import wrap_context
from goga.onboarding.participation import ToolDeclaration
from goga.onboarding.questions import Question, QuestionGroup

from tests.conftest import is_kw_only_dataclass

_CELL_ALL = ["ToolContribution", "ToolDeclaration", "ToolParticipation"]

# --- Contract tests ---


class TestToolDeclarationContract:
    def test_entity_is_importable_from_the_package_facade(self) -> None:
        """The surface lives on the cell package and its ``__all__`` is exact."""
        import goga.onboarding.participation as cell

        assert cell.ToolDeclaration is ToolDeclaration
        assert cell.__all__ == _CELL_ALL

    def test_keyword_construction_starts_with_empty_buffers(self) -> None:
        """``ToolDeclaration(tool=..., invited=...)`` — the buffers start empty."""
        surface = ToolDeclaration(tool="t", invited=True)

        assert surface.tool == "t"
        assert surface.invited is True
        assert surface.questions == []
        assert surface.skips == []

    def test_the_surface_is_a_kw_only_dataclass(self) -> None:
        """The construction is keyword-only; positional arguments are refused."""
        assert is_kw_only_dataclass(ToolDeclaration)

        with pytest.raises(TypeError):
            ToolDeclaration("t", True)  # type: ignore[misc]

    def test_the_surface_passes_the_delivery_view(self) -> None:
        """Reads resolve and buffer calls pass through the ``wrap_context`` proxy."""
        proxy = wrap_context(ToolDeclaration(tool="t", invited=True))

        assert proxy.tool == "t"
        assert proxy.invited is True

        proxy.declare(Question(id="token", kind="input", prompt="Token"))

        assert proxy.questions[0].id == "token"


# --- Logic tests ---


class TestDeclare:
    def test_declare_buffers_questions_in_declaration_order(self) -> None:
        """Questions and one-level groups land in the buffer in call order."""
        surface = ToolDeclaration(tool="t", invited=True)
        token = Question(id="token", kind="input", prompt="Token")
        reporting = QuestionGroup(
            id="reporting",
            prompt="Reporting",
            children=[Question(id="enabled", kind="confirm", prompt="Enable reporting?", default=False)],
        )

        surface.declare(token)
        surface.declare(reporting)

        assert surface.questions == [token, reporting]

    def test_declare_rejects_nested_group_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A tool group is limited to one nesting level — the violation is a warning."""
        surface = ToolDeclaration(tool="t", invited=True)

        with caplog.at_level(logging.WARNING):
            surface.declare(QuestionGroup(id="deep", children=[QuestionGroup(id="inner")]))

        assert surface.questions == []
        assert any("one nesting level" in record.message for record in caplog.records)
        assert any("t" in record.message for record in caplog.records)

    def test_declare_rejects_a_non_record_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """An object that is neither Question nor QuestionGroup is never buffered."""
        surface = ToolDeclaration(tool="t", invited=True)

        with caplog.at_level(logging.WARNING):
            surface.declare("not a record")  # type: ignore[arg-type]

        assert surface.questions == []
        assert any("only a Question record or a one-level QuestionGroup" in record.message for record in caplog.records)
        assert any("t" in record.message for record in caplog.records)

    def test_a_refused_non_record_does_not_stop_the_declaration(self) -> None:
        """The refused element is dropped; the following declarations stand."""
        surface = ToolDeclaration(tool="t", invited=True)
        token = Question(id="token", kind="input", prompt="Token")

        surface.declare({"id": "token"})  # type: ignore[arg-type]
        surface.declare(token)

        assert surface.questions == [token]

    def test_declare_never_raises(self) -> None:
        """Structural violations are warnings, never exceptions."""
        surface = ToolDeclaration(tool="t", invited=False)

        surface.declare(QuestionGroup(id="deep", children=[QuestionGroup(id="inner")]))

        assert surface.questions == []

    def test_delivery_continues_after_a_refused_group(self) -> None:
        """The refused element is dropped; the following declarations stand."""
        surface = ToolDeclaration(tool="t", invited=True)
        token = Question(id="token", kind="input", prompt="Token")

        surface.declare(QuestionGroup(id="deep", children=[QuestionGroup(id="inner")]))
        surface.declare(token)

        assert surface.questions == [token]

    def test_a_structural_group_without_children_is_accepted(self) -> None:
        """A purely structural node carries no children — nothing to refuse."""
        surface = ToolDeclaration(tool="t", invited=True)
        structural = QuestionGroup(id="g")

        surface.declare(structural)

        assert surface.questions == [structural]


class TestSkip:
    def test_skip_buffers_the_raw_path(self) -> None:
        """No resolution here — the engine resolves every declared skip later."""
        surface = ToolDeclaration(tool="t", invited=True)

        surface.skip("build.env")
        surface.skip("docker_image.base_image")
        surface.skip("viewer.opt")

        assert surface.skips == ["build.env", "docker_image.base_image", "viewer.opt"]
