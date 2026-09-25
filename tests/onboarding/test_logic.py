"""Contract and logic tests for the onboarding domain facade.

The entity declared in ``goga/onboarding/CODEMANIFEST`` with
``location: logic.py``: the orchestrator ``InitLogic`` of one initialization
session — together with the 13 facade re-exports of the leaf cells in the
embedding order of the CODEMANIFEST. The collaborators are stubbed where the
subject is the orchestrator's own control flow (the existing-config guard,
the session error tiers, the degraded plain session); the real participation
mediator runs in the broken-import case — the single fatal path of the tool
moments. The filesystem boundary is pinned by the ``_clean_cwd`` fixture of
this test directory.
"""

from __future__ import annotations

import logging
import sys
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from goga.onboarding import InitLogic, ToolParticipation
from goga.onboarding.generator import FileGenerator

_logic_module = sys.modules["goga.onboarding.logic"]

_EMBEDDING_ALL = [
    "Question",
    "QuestionGroup",
    "SessionAnswers",
    "SessionPlan",
    "Questionnaire",
    "core_questions",
    "assemble_session_plan",
    "apply_skips",
    "ToolParticipation",
    "ToolDeclaration",
    "ToolContribution",
    "FileGenerator",
    "CreatedFile",
    "InitLogic",
]

# The attribute the enumeration reads — the single enumeration mock point
# (mirrors the participation test directory; conftest fixtures do not cross
# test directories).
_ENUMERATION_TARGET = "goga.hooks.tools.packages.packages_distributions"

# Every run test operates on the filesystem state of a clean project dir —
# the repo CWD carries the goga project's own .goga/.
pytestmark = pytest.mark.usefixtures("_clean_cwd")


class TestContract:
    """Contract-level tests for the facade surface and the constructor."""

    def test_facade_reexports_the_session_api_in_embedding_order(self) -> None:
        """The 13 embeddings plus InitLogic are the facade surface, in the CODEMANIFEST order."""
        import goga.onboarding as facade

        assert facade.__all__ == _EMBEDDING_ALL

        for name in _EMBEDDING_ALL:
            assert getattr(facade, name) is not None

    def test_init_logic_importable_from_logic_module(self) -> None:
        """The orchestrator lives in the declared ``location: logic.py``."""
        assert sys.modules["goga.onboarding.logic"].InitLogic is InitLogic

    def test_constructor_requires_three_collaborators(self) -> None:
        """The questionnaire, the generator, and the participation are all required."""
        logic = InitLogic(questionnaire=MagicMock(), generator=MagicMock(), participation=MagicMock())

        assert logic is not None
        assert callable(logic.run)

        with pytest.raises(TypeError):
            InitLogic(MagicMock(), MagicMock())  # type: ignore[call-arg]

    def test_facade_no_longer_exports_the_old_answer_records(self) -> None:
        """The flat-answer surface of the old facade is gone for good."""
        import goga.onboarding as facade

        assert not hasattr(facade, "InitAnswers")
        assert not hasattr(facade, "GogaConfigAnswers")
        assert "InitAnswers" not in facade.__all__
        assert "GogaConfigAnswers" not in facade.__all__


class TestRun:
    """Logic tests for the eight-step ``run`` and its three error tiers."""

    def test_existing_config_ends_session_silently(self, tmp_path) -> None:
        """An existing .goga/config.yml ends the session — no prompts, no events, no artifacts."""
        (tmp_path / ".goga").mkdir()
        (tmp_path / ".goga" / "config.yml").write_text("language: python\n", encoding="utf-8")

        mock_q, mock_g, mock_p = MagicMock(), MagicMock(), MagicMock()
        logic = InitLogic(questionnaire=mock_q, generator=mock_g, participation=mock_p)

        assert logic.run() == 0
        mock_p.collect_declarations.assert_not_called()
        mock_q.run.assert_not_called()
        mock_g.generate.assert_not_called()

    def test_unreadable_version_is_clean_error(self, monkeypatch, capsys) -> None:
        """An unreadable installed version is one clean message, exit 1, no traceback."""
        monkeypatch.setattr(_logic_module, "host_goga_version", MagicMock(side_effect=PackageNotFoundError("goga")))

        logic = InitLogic(questionnaire=MagicMock(), generator=MagicMock(), participation=MagicMock())

        assert logic.run() == 1

        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "Traceback" not in captured.err
        assert "Traceback" not in captured.out

    def test_broken_package_import_is_clean_session_error(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ) -> None:
        """A tool package whose facade fails to import is one clean message naming the package."""
        monkeypatch.setattr(_logic_module, "host_goga_version", lambda: "1.3.0")

        package_dir = tmp_path / "goga_tool_broken"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("import goga_missing_dependency\n", encoding="utf-8")
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.setattr(_ENUMERATION_TARGET, lambda: {"goga_tool_broken": ["goga-tool-broken"]})

        logic = InitLogic(
            questionnaire=MagicMock(),
            generator=MagicMock(),
            participation=ToolParticipation(invited=["broken"]),
        )

        assert logic.run() == 1

        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "goga_tool_broken" in captured.err
        assert "Traceback" not in captured.err
        assert "Traceback" not in captured.out

    def test_zero_invited_tools_degrades_to_the_plain_session(self, monkeypatch, caplog) -> None:
        """No invitations and no installed packages — the core-only survey, exit 0."""
        monkeypatch.setattr(_logic_module, "host_goga_version", lambda: "1.3.0")
        monkeypatch.setattr(_ENUMERATION_TARGET, lambda: {})

        captured: dict = {}

        class _RecordingQuestionnaire:
            """Stub recording the received plan and answering the single required field."""

            def run(self, plan, answers) -> None:  # type: ignore[no-untyped-def]
                captured["tools"] = list(plan.tools)
                captured["section_ids"] = [child.id for child in plan.root.children]
                answers.record("language", "python")

        with caplog.at_level(logging.WARNING):
            logic = InitLogic(
                questionnaire=_RecordingQuestionnaire(),  # type: ignore[arg-type]
                generator=FileGenerator(),
                participation=ToolParticipation(invited=[]),
            )

            assert logic.run() == 0

        assert captured["tools"] == []
        assert captured["section_ids"] == [
            "language",
            "convention",
            "codemanifest",
            "build",
            "docker_image",
            "pipeline",
            "tools",
            "usages",
        ]
        assert not caplog.records  # no uninstalled-invited warnings — nothing was invited
        assert Path(".goga/config.yml").is_file()
        assert not Path(".goga/tools").exists()

    def test_abort_during_the_survey_is_quiet_exit_one(self, monkeypatch, capsys) -> None:
        """A user abort is exit 1 with no message and no traceback."""
        import click

        monkeypatch.setattr(_logic_module, "host_goga_version", lambda: "1.3.0")
        monkeypatch.setattr(_ENUMERATION_TARGET, lambda: {})

        mock_q = MagicMock()
        mock_q.run.side_effect = click.Abort()

        logic = InitLogic(questionnaire=mock_q, generator=MagicMock(), participation=ToolParticipation(invited=[]))

        assert logic.run() == 1

        captured = capsys.readouterr()
        assert "Error:" not in captured.err
        assert "Traceback" not in captured.err
