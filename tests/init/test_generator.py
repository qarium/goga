from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest
import yaml
from goga.init.answers import GogaConfigAnswers, InitAnswers
from goga.init.generator import FileGenerator


class TestContract:
    """Contract-level tests for FileGenerator."""

    def test_file_generator_importable_from_generator(self) -> None:
        from goga.init.generator import FileGenerator

        assert FileGenerator is not None

    def test_file_generator_constructor_no_args(self) -> None:
        gen = FileGenerator()
        assert gen is not None

    def test_file_generator_has_generate_method(self) -> None:
        gen = FileGenerator()
        assert hasattr(gen, "generate")
        assert callable(gen.generate)

    def test_file_generator_has_generate_goga_config_method(self) -> None:
        gen = FileGenerator()
        assert hasattr(gen, "generate_goga_config")
        assert callable(gen.generate_goga_config)


class TestLogic:
    """Logic tests for FileGenerator — uses tmp_path and mocks urllib."""

    def _make_config(  # noqa: PLR0913
        self,
        language: str = "python",
        agent: str = "claude",
        image: str = "qarium/goga-python-3.12:1.0",
        env: dict | None = None,
        codemanifest_usages: dict | None = None,
        codemanifest_annotations: str | None = None,
    ) -> GogaConfigAnswers:
        return GogaConfigAnswers(
            language=language,
            agent=agent,
            image=image,
            env=env if env is not None else {},
            codemanifest_usages=codemanifest_usages,
            codemanifest_annotations=codemanifest_annotations,
        )

    def _make_gen(self, tmp_path: Path) -> FileGenerator:
        gen = FileGenerator()
        gen._base_dir = tmp_path
        return gen

    def _load_yaml(self, config_path: Path) -> dict:
        with config_path.open() as f:
            return yaml.safe_load(f)

    def test_generate_goga_config_yaml_compatible_with_load_config(self, tmp_path: Path) -> None:
        """Generated YAML must be parseable by load_config()."""
        config = self._make_config(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:1.0",
            env={"API_KEY": "secret"},
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
            codemanifest_annotations="Use conventions for code rules.",
        )
        gen = self._make_gen(tmp_path)
        gen.generate_goga_config(config)

        config_path = tmp_path / ".goga" / "config.yml"
        assert config_path.exists()

        data = self._load_yaml(config_path)

        # Verify structure compatible with load_config()
        assert data["language"] == "python"
        assert data["build"]["task_executor"]["agent"] == "claude"
        assert data["build"]["task_executor"]["env"] == {"API_KEY": "secret"}
        assert data["build"]["image"] == "qarium/goga-python-3.12:1.0"
        assert data["codemanifest"]["usages"] == {"conventions": ".goga/usages/conventions.md"}
        assert data["codemanifest"]["annotations"] == "Use conventions for code rules.\n"

    def test_generate_creates_goga_directory_when_missing(self, tmp_path: Path) -> None:
        """generate_goga_config() must create .goga/ directory if absent."""
        config = self._make_config(language="golang")
        gen = self._make_gen(tmp_path)
        gen.generate_goga_config(config)

        assert (tmp_path / ".goga").is_dir()
        assert (tmp_path / ".goga" / "config.yml").exists()

    def test_generate_golang_language_url(self, tmp_path: Path) -> None:
        """When language=golang, the URL must contain 'golang'."""
        config = self._make_config(
            language="golang",
            agent="claude",
            image="qarium/goga-golang-1.23:1.0",
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
        )
        answers = InitAnswers(goga_config=config)

        mock_response = MagicMock()
        mock_response.read.return_value = b"# Go conventions"
        mock_response.__enter__ = MagicMock(return_value=mock_response)

        gen = self._make_gen(tmp_path)
        with patch("goga.init.generator.urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            gen.generate(answers)

        called_url = mock_urlopen.call_args[0][0]
        assert "golang" in called_url

    def test_generate_skips_convention_when_no_usages(self, tmp_path: Path) -> None:
        """When codemanifest_usages=None, no HTTP request, config.yml created without codemanifest."""
        config = self._make_config(language="python", codemanifest_usages=None)
        answers = InitAnswers(goga_config=config)

        gen = self._make_gen(tmp_path)
        with patch("goga.init.generator.urllib.request.urlopen") as mock_urlopen:
            gen.generate(answers)

        mock_urlopen.assert_not_called()

        config_path = tmp_path / ".goga" / "config.yml"
        assert config_path.exists()
        data = self._load_yaml(config_path)
        assert "codemanifest" not in data

    def test_generate_skips_convention_when_usages_without_conventions_key(self, tmp_path: Path) -> None:
        """When codemanifest_usages has no 'conventions' key, no HTTP request, config.yml has codemanifest.usages."""
        config = self._make_config(
            language="python",
            codemanifest_usages={"custom": ".goga/usages/custom.md"},
        )
        answers = InitAnswers(goga_config=config)

        gen = self._make_gen(tmp_path)
        with patch("goga.init.generator.urllib.request.urlopen") as mock_urlopen:
            gen.generate(answers)

        mock_urlopen.assert_not_called()

        config_path = tmp_path / ".goga" / "config.yml"
        assert config_path.exists()
        data = self._load_yaml(config_path)
        assert data["codemanifest"]["usages"] == {"custom": ".goga/usages/custom.md"}
        assert not (tmp_path / ".goga" / "usages").exists()

    def test_generate_creates_usages_directory_for_convention(self, tmp_path: Path) -> None:
        """When convention=True, .goga/usages/ is created and conventions.md written."""
        config = self._make_config(
            language="python",
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
            codemanifest_annotations="Use conventions.",
        )
        answers = InitAnswers(goga_config=config)

        mock_response = MagicMock()
        mock_response.read.return_value = b"# Python conventions content"
        mock_response.__enter__ = MagicMock(return_value=mock_response)

        gen = self._make_gen(tmp_path)
        with patch("goga.init.generator.urllib.request.urlopen", return_value=mock_response):
            gen.generate(answers)

        conventions_path = tmp_path / ".goga" / "usages" / "conventions.md"
        assert conventions_path.exists()
        content = conventions_path.read_text(encoding="utf-8")
        assert content == "# Python conventions content"

    def test_generate_convention_download_fails_propagates(self, tmp_path: Path) -> None:
        """When urlopen raises URLError, RuntimeError wraps it and config.yml is NOT created."""
        config = self._make_config(
            language="python",
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
        )
        answers = InitAnswers(goga_config=config)

        gen = self._make_gen(tmp_path)
        with (
            patch("goga.init.generator.urllib.request.urlopen", side_effect=URLError("Network error")),
            pytest.raises(RuntimeError, match="Failed to download convention"),
        ):
            gen.generate(answers)

        # config.yml must NOT be created
        assert not (tmp_path / ".goga" / "config.yml").exists()

    def test_generate_reinit_overwrites_existing_config(self, tmp_path: Path) -> None:
        """If .goga/config.yml already exists, generate_goga_config overwrites it."""
        goga_dir = tmp_path / ".goga"
        goga_dir.mkdir()
        (goga_dir / "config.yml").write_text("language: old_lang\n")

        config = self._make_config(language="golang", agent="claude", image="qarium/goga-golang-1.23:1.0")
        gen = self._make_gen(tmp_path)
        gen.generate_goga_config(config)

        data = self._load_yaml(goga_dir / "config.yml")
        assert data["language"] == "golang"
