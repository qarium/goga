# tests/config/test_project_cell_contract.py — contract + logic tests for the relocated/renamed project cell

import inspect

import goga.config.project as project_mod
import pytest
from goga.config.project import (
    BuildConfig,
    CodemanifestConfig,
    PipelineConfig,
    ProjectConfig,
    load_project_config,
)

# --- Helpers ---


@pytest.fixture
def goga_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write_goga_yml(path, content: str):
    goga_dir = path / ".goga"
    goga_dir.mkdir(exist_ok=True)
    (goga_dir / "config.yml").write_text(content)


# --- Contract tests ---


class TestProjectCellReexports:
    def test_public_names_importable_from_project_cell(self):
        """The 7 public names are importable from goga.config.project."""
        for name in (
            "ProjectConfig",
            "load_project_config",
            "BuildConfig",
            "TaskExecutorConfig",
            "PipelineConfig",
            "CodemanifestConfig",
            "ReviewExecutorConfig",
        ):
            assert hasattr(project_mod, name), f"{name} missing from goga.config.project"
            assert name in project_mod.__all__, f"{name} missing from project __all__"

    def test_old_names_absent_from_project_cell(self):
        """The old names Config / load_config are NOT attributes of goga.config.project."""
        assert not hasattr(project_mod, "Config")
        assert not hasattr(project_mod, "load_config")
        assert "Config" not in project_mod.__all__
        assert "load_config" not in project_mod.__all__

    def test_old_names_raise_import_error(self):
        """Importing the old names from goga.config.project raises ImportError."""
        with pytest.raises(ImportError):
            from goga.config.project import Config  # noqa: F401

        with pytest.raises(ImportError):
            from goga.config.project import load_config  # noqa: F401

    def test_load_project_config_returns_project_config_annotation(self):
        """load_project_config declares ProjectConfig as its return annotation."""
        ret = inspect.signature(load_project_config).return_annotation
        assert ret is ProjectConfig

    def test_load_project_config_returns_project_config_instance(self, goga_project):
        """load_project_config returns a ProjectConfig instance (identity) at runtime."""
        _write_goga_yml(
            goga_project,
            "language: python\nimage: qarium/foo:1.0\npipeline:\n  agent: claude\n"
            "build:\n  task_executor:\n    agent: claude\n",
        )
        result = load_project_config()
        # identity — the facade-reexported ProjectConfig IS the class returned
        assert isinstance(result, project_mod.ProjectConfig)
        assert type(result) is project_mod.ProjectConfig


# --- Logic tests (relocated loader exercised end-to-end) ---


class TestLoadProjectConfigLogic:
    def test_minimal_parse_noneable_image_dockerfile(self, goga_project):
        """image absent → None (None-able), dockerfile absent → None, build/pipeline optional."""
        _write_goga_yml(
            goga_project,
            "language: python\npipeline:\n  agent: claude\nbuild:\n  task_executor:\n    agent: claude\n",
        )
        config = load_project_config()
        assert config.lang == "python"
        assert config.image is None
        assert config.dockerfile is None
        assert isinstance(config.pipeline, PipelineConfig)
        assert config.pipeline.agent == "claude"
        assert isinstance(config.build, BuildConfig)
        assert config.build.task_executor.agent == "claude"
        assert config.build.task_executor.env == {}
        assert config.commands == {}
        assert config.codemanifest is None
        assert config.tools is None

    def test_image_and_dockerfile_present(self, goga_project):
        """When image/dockerfile are present they pass through."""
        _write_goga_yml(
            goga_project,
            "language: go\nimage: goga:latest\ndockerfile: ./Dockerfile\n"
            "pipeline:\n  agent: codex\nbuild:\n  task_executor:\n    agent: gemini\n",
        )
        config = load_project_config()
        assert config.image == "goga:latest"
        assert config.dockerfile == "./Dockerfile"

    def test_optional_build_and_pipeline_absent(self, goga_project):
        """build / pipeline absent → None (optional sections)."""
        _write_goga_yml(goga_project, "language: python\n")
        config = load_project_config()
        assert config.build is None
        assert config.pipeline is None

    def test_tools_structural_passthrough(self, goga_project):
        """tools pass through structurally — no semantic validation (operator forms kept)."""
        _write_goga_yml(
            goga_project,
            "language: python\ntools:\n  viewer: '>=1.0'\n  scriba: latest\n  mkdocs: 1.x\n",
        )
        config = load_project_config()
        assert config.tools == {"viewer": ">=1.0", "scriba": "latest", "mkdocs": "1.x"}

    def test_codemanifest_parsed(self, goga_project):
        """codemanifest block is parsed into CodemanifestConfig."""
        _write_goga_yml(
            goga_project,
            "language: python\ncodemanifest:\n  usages:\n    foo: path/to/foo.md\n  annotations: notes\n",
        )
        config = load_project_config()
        assert isinstance(config.codemanifest, CodemanifestConfig)
        assert config.codemanifest.usages == {"foo": "path/to/foo.md"}
        assert config.codemanifest.annotations == "notes"
