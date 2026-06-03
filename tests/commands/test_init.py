from __future__ import annotations

from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner
from goga.init.answers import GogaConfigAnswers, InitAnswers
from goga.init.generator import FileGenerator
from goga.init.logic import InitLogic
from goga.init.questionnaire import Questionnaire


class TestContract:
    """Contract-level tests for init CLI command."""

    def test_init_importable_from_facade(self) -> None:
        from goga.commands.init import init

        assert callable(init)

    def test_init_is_click_command(self) -> None:
        from goga.commands.init import init

        assert isinstance(init, click.Command)

    def test_init_has_name_init(self) -> None:
        from goga.commands.init import init

        assert init.name == "init"


class TestLogic:
    """Logic-level tests for init CLI command."""

    def test_init_cli_command(self, tmp_path) -> None:
        """Successful init: exit_code == 0."""
        from goga.commands.init import init

        config = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:0.1",
            env={},
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = FileGenerator()
        gen._base_dir = tmp_path

        with (
            patch("goga.commands.init.init.Questionnaire", return_value=mock_q),
            patch("goga.commands.init.init.FileGenerator", return_value=gen),
        ):
            runner = CliRunner()
            result = runner.invoke(init)

        assert result.exit_code == 0

    def test_init_cli_returns_nonzero_on_failure(self, tmp_path) -> None:
        """InitLogic.run() returns 1 → non-zero exit."""
        from goga.commands.init import init

        mock_logic = MagicMock(spec=InitLogic)
        mock_logic.run.return_value = 1

        with (
            patch("goga.commands.init.init.Questionnaire"),
            patch("goga.commands.init.init.FileGenerator"),
            patch("goga.commands.init.init.InitLogic", return_value=mock_logic),
        ):
            runner = CliRunner()
            result = runner.invoke(init)

        assert result.exit_code != 0
