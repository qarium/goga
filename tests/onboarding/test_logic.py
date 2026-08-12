from __future__ import annotations

from unittest.mock import MagicMock

from goga.onboarding.answers import GogaConfigAnswers, InitAnswers
from goga.onboarding.logic import InitLogic


class TestContract:
    """Contract-level tests for InitLogic."""

    def test_init_logic_importable_from_logic(self) -> None:
        from goga.onboarding.logic import InitLogic

        assert InitLogic is not None

    def test_init_logic_constructor_accepts_two_args(self) -> None:
        mock_q = MagicMock()
        mock_g = MagicMock()
        logic = InitLogic(mock_q, mock_g)
        assert logic is not None

    def test_init_logic_has_run_method_returning_int(self) -> None:
        mock_q = MagicMock()
        mock_g = MagicMock()
        logic = InitLogic(mock_q, mock_g)
        result = logic.run()
        assert isinstance(result, int)


class TestLogic:
    """Logic tests for InitLogic — mocks Questionnaire and FileGenerator."""

    def _make_config(self) -> GogaConfigAnswers:
        return GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:0.1",
            pipeline_agent="claude",
            env={},
        )

    def test_logic_run_returns_zero_on_success(self) -> None:
        mock_q = MagicMock()
        mock_g = MagicMock()
        answers = InitAnswers(goga_config=self._make_config())
        mock_q.ask.return_value = answers

        logic = InitLogic(mock_q, mock_g)
        result = logic.run()

        assert result == 0

    def test_logic_run_returns_one_on_abort(self) -> None:
        import click

        mock_q = MagicMock()
        mock_g = MagicMock()
        mock_q.ask.side_effect = click.Abort()

        logic = InitLogic(mock_q, mock_g)
        result = logic.run()

        assert result == 1

    def test_logic_run_returns_one_on_generic_exception(self) -> None:
        mock_q = MagicMock()
        mock_g = MagicMock()
        answers = InitAnswers(goga_config=self._make_config())
        mock_q.ask.return_value = answers
        mock_g.generate.side_effect = RuntimeError("disk full")

        logic = InitLogic(mock_q, mock_g)
        result = logic.run()

        assert result == 1

    def test_logic_run_does_not_create_files_on_abort(self) -> None:
        import click

        mock_q = MagicMock()
        mock_g = MagicMock()
        mock_q.ask.side_effect = click.Abort()

        logic = InitLogic(mock_q, mock_g)
        logic.run()

        mock_g.generate.assert_not_called()

    def test_logic_run_calls_ask_then_generate(self) -> None:
        mock_q = MagicMock()
        mock_g = MagicMock()
        answers = InitAnswers(goga_config=self._make_config())
        mock_q.ask.return_value = answers

        logic = InitLogic(mock_q, mock_g)
        logic.run()

        mock_q.ask.assert_called_once()
        mock_g.generate.assert_called_once_with(answers)
