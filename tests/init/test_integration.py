from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import click
import yaml
from goga.init.answers import GogaConfigAnswers, InitAnswers
from goga.init.generator import FileGenerator
from goga.init.logic import InitLogic
from goga.init.questionnaire import Questionnaire


def _make_gen(tmp_path: Path) -> FileGenerator:
    gen = FileGenerator()
    gen._base_dir = tmp_path
    return gen


def _load_yaml(config_path: Path) -> dict:
    with config_path.open() as f:
        return yaml.safe_load(f)


class TestIntegration:
    """End-to-end integration tests: Questionnaire → InitLogic → FileGenerator."""

    def test_init_full_flow_with_convention(self, tmp_path: Path) -> None:
        """Full flow: python, convention=True, agent=claude, default image, no env."""
        config = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:1.0",
            env={},
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
            codemanifest_annotations="Использовать `conventions` для правил написания кода и тестов.",
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)

        mock_response = MagicMock()
        mock_response.read.return_value = b"# Python conventions mock"
        mock_response.__enter__ = MagicMock(return_value=mock_response)

        with patch("goga.init.generator.urllib.request.urlopen", return_value=mock_response):
            result = logic.run()

        assert result == 0

        config_path = tmp_path / ".goga" / "config.yml"
        assert config_path.exists()
        data = _load_yaml(config_path)
        assert data["language"] == "python"
        assert data["codemanifest"]["usages"] == {"conventions": ".goga/usages/conventions.md"}

        conventions_path = tmp_path / ".goga" / "usages" / "conventions.md"
        assert conventions_path.exists()
        assert conventions_path.read_text(encoding="utf-8") == "# Python conventions mock"

    def test_init_without_convention(self, tmp_path: Path) -> None:
        """Golang without convention: no codemanifest section, no .goga/usages/."""
        config = GogaConfigAnswers(
            language="golang",
            agent="claude",
            image="qarium/goga-golang-1.23:1.0",
            env={},
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)

        with patch("goga.init.generator.urllib.request.urlopen") as mock_urlopen:
            result = logic.run()

        assert result == 0

        config_path = tmp_path / ".goga" / "config.yml"
        data = _load_yaml(config_path)
        assert data["language"] == "golang"
        assert "codemanifest" not in data
        assert not (tmp_path / ".goga" / "usages").exists()
        mock_urlopen.assert_not_called()

    def test_init_with_env_vars(self, tmp_path: Path) -> None:
        """Environment variables are written to config.yml."""
        config = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:1.0",
            env={"API_KEY": "secret", "MODEL": "gpt-4"},
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)
        result = logic.run()

        assert result == 0

        data = _load_yaml(tmp_path / ".goga" / "config.yml")
        assert data["build"]["task_executor"]["env"] == {"API_KEY": "secret", "MODEL": "gpt-4"}

    def test_init_with_custom_usages_added_to_convention(self, tmp_path: Path) -> None:
        """Convention + custom usage: codemanifest.usages has both keys."""
        config = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:1.0",
            env={},
            codemanifest_usages={
                "conventions": ".goga/usages/conventions.md",
                "custom": ".goga/usages/custom.md",
            },
            codemanifest_annotations="Use conventions.",
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)

        mock_response = MagicMock()
        mock_response.read.return_value = b"# mock"
        mock_response.__enter__ = MagicMock(return_value=mock_response)

        with patch("goga.init.generator.urllib.request.urlopen", return_value=mock_response):
            result = logic.run()

        assert result == 0

        data = _load_yaml(tmp_path / ".goga" / "config.yml")
        usages = data["codemanifest"]["usages"]
        assert "conventions" in usages
        assert "custom" in usages

    def test_init_custom_usages_without_convention(self, tmp_path: Path) -> None:
        """Custom usage without convention: usages={"custom": "..."}, no HTTP download."""
        config = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:1.0",
            env={},
            codemanifest_usages={"custom": ".goga/usages/custom.md"},
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)

        with patch("goga.init.generator.urllib.request.urlopen") as mock_urlopen:
            result = logic.run()

        assert result == 0
        mock_urlopen.assert_not_called()

        data = _load_yaml(tmp_path / ".goga" / "config.yml")
        assert data["codemanifest"]["usages"] == {"custom": ".goga/usages/custom.md"}
        assert not (tmp_path / ".goga" / "usages").exists()

    def test_init_empty_env(self, tmp_path: Path) -> None:
        """Empty env dict is written correctly."""
        config = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:1.0",
            env={},
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)
        result = logic.run()

        assert result == 0

        data = _load_yaml(tmp_path / ".goga" / "config.yml")
        assert data["build"]["task_executor"]["env"] == {}

    def test_init_reinit_overwrites_existing_config(self, tmp_path: Path) -> None:
        """Pre-existing config.yml is overwritten on re-init."""
        goga_dir = tmp_path / ".goga"
        goga_dir.mkdir()
        (goga_dir / "config.yml").write_text("language: old_lang\n")

        config = GogaConfigAnswers(
            language="golang",
            agent="claude",
            image="qarium/goga-golang-1.23:1.0",
            env={},
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)
        result = logic.run()

        assert result == 0

        data = _load_yaml(tmp_path / ".goga" / "config.yml")
        assert data["language"] == "golang"

    def test_init_custom_annotations_appended_to_convention(self, tmp_path: Path) -> None:
        """Convention annotations + custom annotations are concatenated via newline."""
        config = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:1.0",
            env={},
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
            codemanifest_annotations=(
                "Использовать `conventions` для правил написания кода и тестов."
                "\nCustom rule"
            ),
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)

        mock_response = MagicMock()
        mock_response.read.return_value = b"# mock"
        mock_response.__enter__ = MagicMock(return_value=mock_response)

        with patch("goga.init.generator.urllib.request.urlopen", return_value=mock_response):
            result = logic.run()

        assert result == 0

        data = _load_yaml(tmp_path / ".goga" / "config.yml")
        annotations = data["codemanifest"]["annotations"]
        assert annotations.startswith("Использовать")
        assert "Custom rule" in annotations

    def test_init_user_cancels_questionnaire(self, tmp_path: Path) -> None:
        """User cancels (click.Abort): run() returns 1, no .goga/ created."""
        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.side_effect = click.Abort()

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)
        result = logic.run()

        assert result == 1
        assert not (tmp_path / ".goga").exists()

    def test_init_convention_download_fails(self, tmp_path: Path) -> None:
        """URLError during convention download: run() returns 1, no files created."""
        config = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:1.0",
            env={},
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
            codemanifest_annotations="Use conventions.",
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)

        with patch("goga.init.generator.urllib.request.urlopen", side_effect=URLError("Network error")):
            result = logic.run()

        assert result == 1
        assert not (tmp_path / ".goga" / "config.yml").exists()
        assert not (tmp_path / ".goga" / "usages" / "conventions.md").exists()
