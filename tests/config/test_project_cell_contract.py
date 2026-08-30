# tests/config/test_project_cell_contract.py — contract + logic tests for the relocated/renamed project cell

import dataclasses
import inspect

import goga.config as goga_config_mod
import goga.config.project as project_mod
import pytest
from goga.config.project import (
    BuildConfig,
    CodemanifestConfig,
    PipelineConfig,
    ProjectConfig,
    TopicsConfig,
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


class TestTopicsConfigContract:
    def test_topics_config_on_both_facades(self):
        """TopicsConfig is importable from goga.config.project AND goga.config."""
        from goga.config import TopicsConfig

        assert project_mod.TopicsConfig is TopicsConfig
        assert goga_config_mod.TopicsConfig is TopicsConfig
        assert "TopicsConfig" in project_mod.__all__
        assert "TopicsConfig" in goga_config_mod.__all__

    def test_topics_config_is_frozen_kw_only_dataclass(self):
        """TopicsConfig is an immutable kw_only dataclass per `convention`."""
        params = TopicsConfig.__dataclass_params__
        assert params.frozen is True
        assert params.kw_only is True

    def test_topics_config_declares_exactly_the_two_fields(self):
        """The declared field set is exactly {base_ref, publish_commit}."""
        assert {f.name for f in dataclasses.fields(TopicsConfig)} == {"base_ref", "publish_commit"}

    def test_topics_config_fields_are_kw_only_without_defaults(self):
        """Both fields are keyword-only and carry no defaults — the loader always passes both."""
        for field in dataclasses.fields(TopicsConfig):
            assert field.kw_only is True
            assert field.default is dataclasses.MISSING
            assert field.default_factory is dataclasses.MISSING

    def test_topics_config_optional_union_annotations(self):
        """Both fields are typed str | None ("explicit absence" semantics)."""
        fields = {f.name: f for f in dataclasses.fields(TopicsConfig)}
        assert fields["base_ref"].type == str | None
        assert fields["publish_commit"].type == str | None

    def test_topics_config_stores_fields_verbatim(self):
        """Pure construction stores both values verbatim — no normalization here."""
        config = TopicsConfig(base_ref="origin/release-1.3", publish_commit="chore: {slug}")
        assert config.base_ref == "origin/release-1.3"
        assert config.publish_commit == "chore: {slug}"

    def test_project_config_gains_trailing_topics_field(self):
        """ProjectConfig declares `topics` as its LAST field, defaulting to None."""
        fields = dataclasses.fields(ProjectConfig)
        assert fields[-1].name == "topics"
        assert fields[-1].default is None

    def test_project_config_topics_annotation_optional(self):
        """The topics field type is TopicsConfig | None."""
        topics_field = {f.name: f for f in dataclasses.fields(ProjectConfig)}["topics"]
        assert topics_field.type == TopicsConfig | None

    def test_load_project_config_signature_unchanged(self):
        """load_project_config still accepts no arguments."""
        assert list(inspect.signature(load_project_config).parameters.keys()) == []

    def test_project_config_existing_callers_stay_valid(self):
        """ProjectConfig(...) omitting topics=/usages=/lint= stays constructible; topics is None."""
        config = ProjectConfig(
            lang="python",
            image=None,
            dockerfile=None,
            build=None,
            pipeline=None,
            commands={},
        )
        assert config.topics is None
        assert config.lang == "python"


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
