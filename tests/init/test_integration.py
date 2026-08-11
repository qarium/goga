from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import requests.exceptions
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
            pipeline_agent="claude",
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
            codemanifest_annotations="Использовать `conventions` для правил написания кода и тестов.",
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)

        mock_response = MagicMock()
        mock_response.text = "# Python conventions mock"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("goga.init.generator.requests.get", return_value=mock_response):
            result = logic.run()

        assert result == 0

        config_path = tmp_path / ".goga" / "config.yml"
        assert config_path.exists()
        data = _load_yaml(config_path)
        assert data["language"] == "python"
        assert data["image"] == "qarium/goga-python-3.12:1.0"
        assert data["pipeline"]["agent"] == "claude"
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
            pipeline_agent="claude",
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)

        with patch("goga.init.generator.requests.get") as mock_get:
            result = logic.run()

        assert result == 0

        config_path = tmp_path / ".goga" / "config.yml"
        data = _load_yaml(config_path)
        assert data["language"] == "golang"
        assert "codemanifest" not in data
        assert not (tmp_path / ".goga" / "usages").exists()
        mock_get.assert_not_called()

    def test_init_with_env_vars(self, tmp_path: Path) -> None:
        """Environment variables are written to config.yml."""
        config = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:1.0",
            pipeline_agent="claude",
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
            pipeline_agent="claude",
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
        mock_response.text = "# mock"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("goga.init.generator.requests.get", return_value=mock_response):
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
            pipeline_agent="claude",
            codemanifest_usages={"custom": ".goga/usages/custom.md"},
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)

        with patch("goga.init.generator.requests.get") as mock_get:
            result = logic.run()

        assert result == 0
        mock_get.assert_not_called()

        data = _load_yaml(tmp_path / ".goga" / "config.yml")
        assert data["codemanifest"]["usages"] == {"custom": ".goga/usages/custom.md"}
        assert not (tmp_path / ".goga" / "usages").exists()

    def test_init_empty_env(self, tmp_path: Path) -> None:
        """Empty env is omitted from config.yml."""
        config = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:1.0",
            pipeline_agent="claude",
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)
        result = logic.run()

        assert result == 0

        data = _load_yaml(tmp_path / ".goga" / "config.yml")
        assert "env" not in data["build"]["task_executor"]

    def test_init_reinit_overwrites_existing_config(self, tmp_path: Path) -> None:
        """Pre-existing config.yml is overwritten on re-init."""
        goga_dir = tmp_path / ".goga"
        goga_dir.mkdir()
        (goga_dir / "config.yml").write_text("language: old_lang\n")

        config = GogaConfigAnswers(
            language="golang",
            agent="claude",
            image="qarium/goga-golang-1.23:1.0",
            pipeline_agent="claude",
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
            pipeline_agent="claude",
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
            codemanifest_annotations=("Использовать `conventions` для правил написания кода и тестов.\nCustom rule"),
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)

        mock_response = MagicMock()
        mock_response.text = "# mock"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("goga.init.generator.requests.get", return_value=mock_response):
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
            pipeline_agent="claude",
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
            codemanifest_annotations="Use conventions.",
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)

        with patch(
            "goga.init.generator.requests.get",
            side_effect=requests.exceptions.ConnectionError("Network error"),
        ):
            result = logic.run()

        assert result == 1
        assert not (tmp_path / ".goga" / "config.yml").exists()
        assert not (tmp_path / ".goga" / "usages" / "conventions.md").exists()

    def test_init_emits_pipeline_block_in_generated_config(self, tmp_path: Path) -> None:
        """Generated config.yml always contains a pipeline: block (agent required by load_project_config)."""
        config = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:1.0",
            pipeline_agent="codex",
            pipeline_env={"CODEX_MODEL": "o4-mini"},
        )
        answers = InitAnswers(goga_config=config)

        mock_q = MagicMock(spec=Questionnaire)
        mock_q.ask.return_value = answers

        gen = _make_gen(tmp_path)
        logic = InitLogic(mock_q, gen)
        result = logic.run()

        assert result == 0

        data = _load_yaml(tmp_path / ".goga" / "config.yml")
        assert data["pipeline"]["agent"] == "codex"
        assert data["pipeline"]["env"] == {"CODEX_MODEL": "o4-mini"}
        assert "image" not in data["build"]

    def test_init_generates_goga_dockerfile_at_new_default_path(self, tmp_path: Path) -> None:
        """End-to-end (D5): accept Dockerfile + Enter → .goga/Dockerfile created & recorded.

        Cross-entity scenario exercising the full chain
        Questionnaire.ask_goga_config → InitLogic.run → FileGenerator.generate.
        The user accepts the Dockerfile creation and presses Enter on the path
        prompt, taking the new `.goga/Dockerfile` default (most common case).
        Asserts the default propagates into both the filesystem and config.yml.
        """
        other_prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # base image (FROM)
                "my-python-image:latest",  # built image name
                "claude",  # pipeline agent
            ]
        )

        def fake_prompt(message, *args, **kwargs):
            # On the Dockerfile path prompt, simulate pressing Enter (no input)
            # → click.prompt returns its `default`.
            if message == "Dockerfile path":
                return kwargs.get("default")
            return next(other_prompts)

        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                True,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        gen = FileGenerator()
        gen._base_dir = tmp_path
        logic = InitLogic(Questionnaire(), gen)

        with patch("click.prompt", side_effect=fake_prompt), patch("click.confirm", side_effect=confirms):
            result = logic.run()

        assert result == 0

        dockerfile = tmp_path / ".goga" / "Dockerfile"
        assert dockerfile.exists()
        content = dockerfile.read_text(encoding="utf-8")
        assert content == "FROM qarium/goga-python-3.12:1.0\n"

        config_yml = (tmp_path / ".goga" / "config.yml").read_text(encoding="utf-8")
        assert "dockerfile: .goga/Dockerfile" in config_yml
        assert "image: my-python-image:latest" in config_yml

    def test_init_custom_dockerfile_path_flows_through_chain(self, tmp_path: Path) -> None:
        """Cross-entity: a custom Dockerfile path reaches both the FS and config.yml.

        Confirms that the survey answer (dockerfile_path) is threaded unchanged
        through Questionnaire → InitLogic → FileGenerator, not hardcoded to the
        default. The file lands at the user-chosen location under .goga/.
        """
        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                ".goga/custom.Dockerfile",  # dockerfile path (typed, not default)
                "qarium/goga-python-3.12:1.0",  # base image (FROM)
                "my-python-image:latest",  # built image name
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                True,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        gen = FileGenerator()
        gen._base_dir = tmp_path
        logic = InitLogic(Questionnaire(), gen)

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            result = logic.run()

        assert result == 0

        dockerfile = tmp_path / ".goga" / "custom.Dockerfile"
        assert dockerfile.exists()
        assert dockerfile.read_text(encoding="utf-8") == "FROM qarium/goga-python-3.12:1.0\n"

        config_yml = (tmp_path / ".goga" / "config.yml").read_text(encoding="utf-8")
        assert "dockerfile: .goga/custom.Dockerfile" in config_yml
        assert "image: my-python-image:latest" in config_yml
