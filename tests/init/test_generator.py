from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests.exceptions
import yaml
from goga.config import load_project_config
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

    def _make_config(  # noqa: PLR0913, PLR0917
        self,
        language: str = "python",
        agent: str = "claude",
        image: str = "qarium/goga-python-3.12:1.0",
        pipeline_agent: str = "claude",
        pipeline_env: dict | None = None,
        env: dict | None = None,
        codemanifest_usages: dict | None = None,
        codemanifest_annotations: str | None = None,
        dockerfile_path: str | None = None,
    ) -> GogaConfigAnswers:
        return GogaConfigAnswers(
            language=language,
            agent=agent,
            image=image,
            pipeline_agent=pipeline_agent,
            pipeline_env=pipeline_env,
            env=env,
            codemanifest_usages=codemanifest_usages,
            codemanifest_annotations=codemanifest_annotations,
            dockerfile_path=dockerfile_path,
        )

    def _make_gen(self, tmp_path: Path) -> FileGenerator:
        gen = FileGenerator()
        gen._base_dir = tmp_path
        return gen

    def _load_yaml(self, config_path: Path) -> dict:
        with config_path.open() as f:
            return yaml.safe_load(f)

    def test_generate_goga_config_yaml_compatible_with_load_config(self, tmp_path: Path) -> None:
        """Generated YAML must be parseable by load_project_config()."""
        config = self._make_config(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:1.0",
            pipeline_agent="codex",
            pipeline_env={"CODEX_MODEL": "o4-mini"},
            env={"API_KEY": "secret"},
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
            codemanifest_annotations="Use conventions for code rules.",
        )
        mock_response = MagicMock()
        mock_response.text = "# Python conventions"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        gen = self._make_gen(tmp_path)
        with patch("goga.init.generator.requests.get", return_value=mock_response):
            gen.generate_goga_config(config)

        config_path = tmp_path / ".goga" / "config.yml"
        assert config_path.exists()

        data = self._load_yaml(config_path)

        # Verify structure compatible with load_project_config()
        assert data["language"] == "python"
        assert data["image"] == "qarium/goga-python-3.12:1.0"
        assert data["build"]["task_executor"]["agent"] == "claude"
        assert data["build"]["task_executor"]["env"] == {"API_KEY": "secret"}
        assert "image" not in data["build"]
        assert data["pipeline"]["agent"] == "codex"
        assert data["pipeline"]["env"] == {"CODEX_MODEL": "o4-mini"}
        assert data["codemanifest"]["usages"] == {"conventions": ".goga/usages/conventions.md"}
        assert data["codemanifest"]["annotations"] == "Use conventions for code rules.\n"

    def test_generate_goga_config_round_trips_through_load_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Generated config.yml must load without error via load_project_config()."""
        config = self._make_config(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:1.0",
            pipeline_agent="claude",
            env={"API_KEY": "secret"},
        )
        gen = self._make_gen(tmp_path)
        gen.generate_goga_config(config)

        monkeypatch.chdir(tmp_path)
        loaded = load_project_config()
        assert loaded.lang == "python"
        assert loaded.image == "qarium/goga-python-3.12:1.0"
        assert loaded.pipeline.agent == "claude"
        assert loaded.build.task_executor.env == {"API_KEY": "secret"}

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
        mock_response.text = "# Go conventions"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        gen = self._make_gen(tmp_path)
        with patch("goga.init.generator.requests.get", return_value=mock_response) as mock_get:
            gen.generate(answers)

        called_url = mock_get.call_args[0][0]
        assert "golang" in called_url

    def test_generate_skips_convention_when_no_usages(self, tmp_path: Path) -> None:
        """When codemanifest_usages=None, no HTTP request, config.yml created without codemanifest."""
        config = self._make_config(language="python", codemanifest_usages=None)
        answers = InitAnswers(goga_config=config)

        gen = self._make_gen(tmp_path)
        with patch("goga.init.generator.requests.get") as mock_get:
            gen.generate(answers)

        mock_get.assert_not_called()

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
        with patch("goga.init.generator.requests.get") as mock_get:
            gen.generate(answers)

        mock_get.assert_not_called()

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
        mock_response.text = "# Python conventions content"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        gen = self._make_gen(tmp_path)
        with patch("goga.init.generator.requests.get", return_value=mock_response):
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
            patch("goga.init.generator.requests.get", side_effect=requests.exceptions.ConnectionError("Network error")),
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

    # --- New tests for Dockerfile generation ---

    def test_generator_creates_dockerfile(self, tmp_path: Path) -> None:
        """When dockerfile_path is set, Dockerfile is created with FROM image."""
        config = self._make_config(
            image="qarium/goga-python-3.14:1.0",
            dockerfile_path="Dockerfile",
        )
        answers = InitAnswers(goga_config=config)

        gen = self._make_gen(tmp_path)
        gen.generate(answers)

        dockerfile = tmp_path / "Dockerfile"
        assert dockerfile.exists()
        content = dockerfile.read_text(encoding="utf-8")
        assert content == "FROM qarium/goga-python-3.14:1.0\n"

    def test_generator_no_dockerfile_when_none(self, tmp_path: Path) -> None:
        """When dockerfile_path is None, no Dockerfile is created."""
        config = self._make_config(dockerfile_path=None)
        answers = InitAnswers(goga_config=config)

        gen = self._make_gen(tmp_path)
        with patch("goga.init.generator.requests.get"):
            gen.generate(answers)

        assert not (tmp_path / "Dockerfile").exists()

    def test_generator_config_yml_no_dockerfile_field(self, tmp_path: Path) -> None:
        """dockerfile is emitted at the top level (not under build) when dockerfile_path is set."""
        config = self._make_config(dockerfile_path="Dockerfile")
        gen = self._make_gen(tmp_path)
        gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert data["dockerfile"] == "Dockerfile"
        assert "dockerfile" not in data["build"]

    def test_generator_emits_dockerfile_after_image(self, tmp_path: Path) -> None:
        """dockerfile is emitted immediately after image (top level) when set."""
        config = self._make_config(dockerfile_path="Dockerfile")
        gen = self._make_gen(tmp_path)
        gen.generate_goga_config(config)

        text = (tmp_path / ".goga" / "config.yml").read_text(encoding="utf-8")
        assert text.index("language:") < text.index("image:")
        assert text.index("image:") < text.index("dockerfile:")
        assert text.index("dockerfile:") < text.index("build:")
        assert "dockerfile: Dockerfile" in text

    def test_generator_omits_dockerfile_when_none(self, tmp_path: Path) -> None:
        """dockerfile is omitted entirely when dockerfile_path is None."""
        config = self._make_config(dockerfile_path=None)
        gen = self._make_gen(tmp_path)
        gen.generate_goga_config(config)

        text = (tmp_path / ".goga" / "config.yml").read_text(encoding="utf-8")
        assert "dockerfile" not in text

    def test_generator_dockerfile_custom_path(self, tmp_path: Path) -> None:
        """Dockerfile can be created at a custom path."""
        config = self._make_config(
            image="qarium/goga-golang-1.26:1.0",
            dockerfile_path="docker/Dockerfile",
        )
        answers = InitAnswers(goga_config=config)

        gen = self._make_gen(tmp_path)
        gen.generate(answers)

        dockerfile = tmp_path / "docker" / "Dockerfile"
        assert dockerfile.exists()
        content = dockerfile.read_text(encoding="utf-8")
        assert content == "FROM qarium/goga-golang-1.26:1.0\n"

    def test_generator_no_env_in_yaml_when_none(self, tmp_path: Path) -> None:
        """When env is None, 'env' key must not appear in config.yml."""
        config = self._make_config(env=None)
        gen = self._make_gen(tmp_path)
        gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert "env" not in data["build"]["task_executor"]

    def test_generator_no_env_in_yaml_when_empty(self, tmp_path: Path) -> None:
        """When env is empty dict, 'env' key must not appear in config.yml."""
        config = self._make_config(env={})
        gen = self._make_gen(tmp_path)
        gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert "env" not in data["build"]["task_executor"]

    def test_generator_env_in_yaml_when_provided(self, tmp_path: Path) -> None:
        """When env has values, 'env' key must appear in config.yml."""
        config = self._make_config(env={"API_KEY": "secret"})
        gen = self._make_gen(tmp_path)
        gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert data["build"]["task_executor"]["env"] == {"API_KEY": "secret"}


# --- New tests for the new schema (top-level image + pipeline block) ---


class TestNewSchema:
    """Tests for the new top-level image + pipeline block YAML schema."""

    def _make_config(self, **kwargs) -> GogaConfigAnswers:  # type: ignore[no-untyped-def]
        defaults = {
            "language": "python",
            "agent": "claude",
            "image": "qarium/foo:1.0",
            "pipeline_agent": "claude",
        }
        defaults.update(kwargs)
        return GogaConfigAnswers(**defaults)

    def _make_gen(self, tmp_path: Path) -> FileGenerator:
        gen = FileGenerator()
        gen._base_dir = tmp_path
        return gen

    def _load_yaml(self, config_path: Path) -> dict:
        with config_path.open() as f:
            return yaml.safe_load(f)

    def test_generate_goga_config_emits_yaml_in_correct_order(self, tmp_path: Path) -> None:
        """Top-level keys appear in canonical order (commands omitted — no source)."""
        config = self._make_config(
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
            codemanifest_annotations="Use conventions.",
        )
        mock_response = MagicMock()
        mock_response.text = "# Python conventions"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        gen = FileGenerator()
        gen._base_dir = tmp_path
        with patch("goga.init.generator.requests.get", return_value=mock_response):
            gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        canonical = ["language", "image", "commands", "build", "pipeline", "codemanifest"]
        present = list(data.keys())
        # present keys must be a subsequence of the canonical order
        assert present == [k for k in canonical if k in present]
        assert present == ["language", "image", "build", "pipeline", "codemanifest"]

    def test_generate_goga_config_emits_dockerfile_in_full_canonical_order(self, tmp_path: Path) -> None:
        """With dockerfile set, the full canonical order is
        language, image, dockerfile, build, pipeline, codemanifest — dockerfile
        sits between image and build (not after build)."""
        config = self._make_config(
            dockerfile_path="Dockerfile",
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
            codemanifest_annotations="Use conventions.",
        )
        mock_response = MagicMock()
        mock_response.text = "# Python conventions"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        gen = FileGenerator()
        gen._base_dir = tmp_path
        with patch("goga.init.generator.requests.get", return_value=mock_response):
            gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert list(data.keys()) == ["language", "image", "dockerfile", "build", "pipeline", "codemanifest"]

    def test_generate_goga_config_emits_pipeline_block_when_agent_set(self, tmp_path: Path) -> None:
        """pipeline: block is emitted when a pipeline agent is set (even without env)."""
        config = self._make_config(pipeline_agent="claude", pipeline_env=None)
        gen = FileGenerator()
        gen._base_dir = tmp_path
        gen.generate_goga_config(config)

        text = (tmp_path / ".goga" / "config.yml").read_text(encoding="utf-8")
        assert "pipeline:" in text
        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert data["pipeline"]["agent"] == "claude"
        assert "env" not in data["pipeline"]

    def test_generate_goga_config_omits_pipeline_when_no_agent_no_env(self, tmp_path: Path) -> None:
        """No pipeline agent and no pipeline env → the pipeline block is omitted entirely."""
        config = self._make_config(pipeline_agent=None, pipeline_env=None)
        gen = FileGenerator()
        gen._base_dir = tmp_path
        gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert "pipeline" not in data

    def test_generate_goga_config_omits_build_when_no_agent_no_env(self, tmp_path: Path) -> None:
        """No build agent and no build env → the build block is omitted entirely."""
        config = self._make_config(agent=None, env=None)
        gen = FileGenerator()
        gen._base_dir = tmp_path
        gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert "build" not in data

    def test_generate_goga_config_emits_build_env_without_agent(self, tmp_path: Path) -> None:
        """Build env is emitted even when the build agent is None."""
        config = self._make_config(agent=None, env={"API_KEY": "secret"})
        gen = FileGenerator()
        gen._base_dir = tmp_path
        gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert data["build"]["task_executor"]["env"] == {"API_KEY": "secret"}
        assert "agent" not in data["build"]["task_executor"]

    def test_generate_goga_config_omits_agent_keys_when_none(self, tmp_path: Path) -> None:
        """agent keys are omitted from both build and pipeline when None."""
        config = self._make_config(agent="claude", pipeline_agent=None)
        gen = FileGenerator()
        gen._base_dir = tmp_path
        gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert data["build"]["task_executor"]["agent"] == "claude"
        assert "pipeline" not in data

    def test_generate_goga_config_emits_image_at_top_level(self, tmp_path: Path) -> None:
        """image is emitted at the top level, never under build:."""
        config = self._make_config(image="qarium/foo:1.0")
        gen = FileGenerator()
        gen._base_dir = tmp_path
        gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert data["image"] == "qarium/foo:1.0"
        assert "image" not in data["build"]

    def test_generate_goga_config_omits_pipeline_env_when_none(self, tmp_path: Path) -> None:
        """When pipeline_env is None, env: is absent from the pipeline block."""
        config = self._make_config(pipeline_env=None)
        gen = FileGenerator()
        gen._base_dir = tmp_path
        gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert "pipeline" in data
        assert "env" not in data["pipeline"]

    def test_generate_goga_config_emits_pipeline_env_when_provided(self, tmp_path: Path) -> None:
        """When pipeline_env has values, env: appears under pipeline."""
        config = self._make_config(pipeline_env={"FOO": "1"})
        gen = FileGenerator()
        gen._base_dir = tmp_path
        gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert data["pipeline"]["env"] == {"FOO": "1"}

    def test_generate_goga_config_omits_pipeline_env_when_empty(self, tmp_path: Path) -> None:
        """Empty pipeline_env dict is omitted from config.yml."""
        config = self._make_config(pipeline_env={})
        gen = FileGenerator()
        gen._base_dir = tmp_path
        gen.generate_goga_config(config)

        data = self._load_yaml(tmp_path / ".goga" / "config.yml")
        assert "env" not in data["pipeline"]
