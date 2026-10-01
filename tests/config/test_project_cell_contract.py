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
    TopicsCreateConfig,
    TopicsPropagateConfig,
    TopicsUpdateConfig,
    load_project_config,
)

from tests.config.conftest import _write_goga_yml
from tests.conftest import is_kw_only_dataclass

# --- Contract tests ---


class TestProjectCellReexports:
    def test_public_names_importable_from_project_cell(self):
        """The public names are importable from goga.config.project."""
        for name in (
            "ProjectConfig",
            "load_project_config",
            "BuildConfig",
            "ReviewConfig",
            "AdditionalReviewConfig",
            "PipelineConfig",
            "CodemanifestConfig",
        ):
            assert hasattr(project_mod, name), f"{name} missing from goga.config.project"
            assert name in project_mod.__all__, f"{name} missing from project __all__"

    def test_old_names_absent_from_project_cell(self):
        """The old names Config / load_config are NOT attributes of goga.config.project."""
        assert not hasattr(project_mod, "Config")
        assert not hasattr(project_mod, "load_config")
        assert "Config" not in project_mod.__all__
        assert "load_config" not in project_mod.__all__

    def test_retired_executor_names_absent_from_project_cell(self):
        """The retired executor configs are NOT attributes of goga.config.project."""
        assert not hasattr(project_mod, "TaskExecutorConfig")
        assert not hasattr(project_mod, "ReviewExecutorConfig")
        assert "TaskExecutorConfig" not in project_mod.__all__
        assert "ReviewExecutorConfig" not in project_mod.__all__

    def test_old_names_raise_import_error(self):
        """Importing the old names from goga.config.project raises ImportError."""
        with pytest.raises(ImportError):
            from goga.config.project import Config  # noqa: F401

        with pytest.raises(ImportError):
            from goga.config.project import load_config  # noqa: F401

    def test_retired_executor_names_raise_import_error(self):
        """Importing the retired executor configs raises ImportError."""
        with pytest.raises(ImportError):
            from goga.config.project import TaskExecutorConfig  # noqa: F401

        with pytest.raises(ImportError):
            from goga.config.project import ReviewExecutorConfig  # noqa: F401

    def test_load_project_config_returns_project_config_annotation(self):
        """load_project_config declares ProjectConfig as its return annotation."""
        ret = inspect.signature(load_project_config).return_annotation
        assert ret is ProjectConfig

    def test_load_project_config_returns_project_config_instance(self, goga_project):
        """load_project_config returns a ProjectConfig instance (identity) at runtime."""
        _write_goga_yml(
            goga_project,
            "language: python\nimage: qarium/foo:1.0\npipeline:\n  agent: claude\nbuild:\n  agent: claude\n",
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
        assert is_kw_only_dataclass(TopicsConfig)

    def test_topics_config_declares_exactly_the_nested_fields(self):
        """The declared field set is exactly {base_ref, create, update, propagate}."""
        assert {f.name for f in dataclasses.fields(TopicsConfig)} == {
            "base_ref",
            "create",
            "update",
            "propagate",
        }

    def test_topics_config_fields_are_kw_only_with_none_defaults(self):
        """All four fields are keyword-only and default to None — overlay-friendly."""
        for field in dataclasses.fields(TopicsConfig):
            assert field.kw_only is True
            assert field.default is None
            assert field.default_factory is dataclasses.MISSING

    def test_topics_config_optional_union_annotations(self):
        """base_ref is str | None; the three sections are their model | None."""
        fields = {f.name: f for f in dataclasses.fields(TopicsConfig)}
        assert fields["base_ref"].type == str | None
        assert fields["create"].type == TopicsCreateConfig | None
        assert fields["update"].type == TopicsUpdateConfig | None
        assert fields["propagate"].type == TopicsPropagateConfig | None

    def test_topics_config_has_no_publish_commit(self):
        """The retired publish_commit key does not exist in the model."""
        assert not hasattr(TopicsConfig, "publish_commit")
        with pytest.raises(AttributeError):
            TopicsConfig(base_ref="main").publish_commit  # noqa: B018

    def test_topics_config_stores_fields_verbatim(self):
        """Pure construction stores every value verbatim — no normalization here."""
        config = TopicsConfig(
            base_ref="origin/release-1.3",
            create=TopicsCreateConfig(commit="Create topic '{slug}'"),
            update=TopicsUpdateConfig(strategy="rebase", commit="U {slug}"),
            propagate=TopicsPropagateConfig(strategy="squash"),
        )
        assert config.base_ref == "origin/release-1.3"
        assert config.create.commit == "Create topic '{slug}'"
        assert config.update.strategy == "rebase"
        assert config.update.commit == "U {slug}"
        assert config.propagate.strategy == "squash"
        assert config.propagate.commit is None

    def test_topics_config_constructible_without_arguments(self):
        """The all-None shape needs no arguments (overlay materialization)."""
        config = TopicsConfig()
        assert config.base_ref is None
        assert config.create is None
        assert config.update is None
        assert config.propagate is None

    def test_topics_config_is_immutable(self):
        """Assignment raises FrozenInstanceError."""
        config = TopicsConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.base_ref = "main"

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
            language="python",
            image=None,
            dockerfile=None,
            build=None,
            pipeline=None,
            commands={},
        )
        assert config.topics is None
        assert config.language == "python"


class TestNestedTopicsModelsContract:
    """Contract shape of the three per-operation topics sections."""

    NESTED_MODELS = (
        (TopicsCreateConfig, ("commit",)),
        (TopicsUpdateConfig, ("strategy", "commit")),
        (TopicsPropagateConfig, ("strategy", "commit")),
    )

    @pytest.mark.parametrize(("model", "expected"), NESTED_MODELS, ids=["create", "update", "propagate"])
    def test_model_declares_exactly_the_declared_fields(self, model, expected):
        """The declared field set matches the contract exactly."""
        assert tuple(f.name for f in dataclasses.fields(model)) == expected

    @pytest.mark.parametrize(("model", "_"), NESTED_MODELS, ids=["create", "update", "propagate"])
    def test_model_is_frozen_kw_only_dataclass(self, model, _):
        """Each model is an immutable kw_only dataclass per `convention`."""
        assert model.__dataclass_params__.frozen is True
        assert is_kw_only_dataclass(model)

    @pytest.mark.parametrize(("model", "_"), NESTED_MODELS, ids=["create", "update", "propagate"])
    def test_model_fields_are_optional_strings_with_none_default(self, model, _):
        """Every field is keyword-only, typed str | None, with a None default."""
        for field in dataclasses.fields(model):
            assert field.kw_only is True
            assert field.type == str | None
            assert field.default is None
            assert field.default_factory is dataclasses.MISSING

    @pytest.mark.parametrize(("model", "_"), NESTED_MODELS, ids=["create", "update", "propagate"])
    def test_model_constructible_without_arguments(self, model, _):
        """The all-None shape needs no arguments (overlay materialization)."""
        instance = model()
        assert all(getattr(instance, f.name) is None for f in dataclasses.fields(model))

    @pytest.mark.parametrize(("model", "_"), NESTED_MODELS, ids=["create", "update", "propagate"])
    def test_model_is_immutable(self, model, _):
        """Assignment raises FrozenInstanceError."""
        instance = model()
        with pytest.raises(dataclasses.FrozenInstanceError):
            instance.commit = "nope"

    def test_nested_models_importable_from_project_cell(self):
        """The three models are public names of goga.config.project."""
        for name in ("TopicsCreateConfig", "TopicsUpdateConfig", "TopicsPropagateConfig"):
            assert hasattr(project_mod, name), f"{name} missing from goga.config.project"
            assert name in project_mod.__all__, f"{name} missing from project __all__"


# --- Logic tests (relocated loader exercised end-to-end) ---


class TestLoadProjectConfigLogic:
    def test_minimal_parse_noneable_image_dockerfile(self, goga_project):
        """image absent → None (None-able), dockerfile absent → None, build/pipeline optional."""
        _write_goga_yml(
            goga_project,
            "language: python\npipeline:\n  agent: claude\nbuild:\n  agent: claude\n",
        )
        config = load_project_config()
        assert config.language == "python"
        assert config.image is None
        assert config.dockerfile is None
        assert isinstance(config.pipeline, PipelineConfig)
        assert config.pipeline.agent == "claude"
        assert isinstance(config.build, BuildConfig)
        assert config.build.agent == "claude"
        assert config.build.env == {}
        assert config.build.review is None
        assert config.commands == {}
        assert config.codemanifest is None
        assert config.tools is None

    def test_image_and_dockerfile_present(self, goga_project):
        """When image/dockerfile are present they pass through."""
        _write_goga_yml(
            goga_project,
            "language: go\nimage: goga:latest\ndockerfile: ./Dockerfile\n"
            "pipeline:\n  agent: codex\nbuild:\n  agent: gemini\n",
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
