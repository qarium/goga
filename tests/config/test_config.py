# tests/goga/config/test_config.py — contract and logic tests for dataclasses

import dataclasses
import types

import goga.config as goga_config_mod
import pytest
from goga.config import (
    AdditionalReviewConfig,
    BuildConfig,
    CodemanifestConfig,
    LintConfig,
    PipelineConfig,
    ProjectConfig,
    ReviewConfig,
)
from goga.config.project.config import DepConfig

from tests.conftest import is_kw_only_dataclass

# --- Contract tests ---


class TestFacadeAvailability:
    def test_import_from_facade(self):
        """ProjectConfig, BuildConfig, ReviewConfig are importable from goga.config."""
        assert hasattr(goga_config_mod, "ProjectConfig")
        assert hasattr(goga_config_mod, "BuildConfig")
        assert hasattr(goga_config_mod, "ReviewConfig")
        assert hasattr(goga_config_mod, "AdditionalReviewConfig")

    def test_pipeline_config_importable(self):
        """PipelineConfig is importable from goga.config and in __all__."""
        assert hasattr(goga_config_mod, "PipelineConfig")
        assert "PipelineConfig" in goga_config_mod.__all__

    def test_codemanifest_config_importable(self):
        """CodemanifestConfig is importable from goga.config and in __all__."""
        assert hasattr(goga_config_mod, "CodemanifestConfig")
        assert "CodemanifestConfig" in goga_config_mod.__all__

    def test_review_configs_importable(self):
        """ReviewConfig and AdditionalReviewConfig are importable from goga.config and in __all__."""
        assert hasattr(goga_config_mod, "ReviewConfig")
        assert hasattr(goga_config_mod, "AdditionalReviewConfig")
        assert "ReviewConfig" in goga_config_mod.__all__
        assert "AdditionalReviewConfig" in goga_config_mod.__all__

    def test_review_configs_importable_from_project_cell(self):
        """ReviewConfig and AdditionalReviewConfig are importable from goga.config.project."""
        from goga.config.project import AdditionalReviewConfig as ProjectAdditional
        from goga.config.project import ReviewConfig as ProjectReview

        assert ProjectReview is ReviewConfig
        assert ProjectAdditional is AdditionalReviewConfig

    def test_load_config_importable(self):
        """load_project_config is importable from goga.config."""
        assert hasattr(goga_config_mod, "load_project_config")

    def test_project_facade_exposes_full_contract_api(self):
        """goga.config.project.__all__ carries all nine model names plus the loader."""
        import goga.config.project as project_mod

        expected = {
            "ProjectConfig",
            "BuildConfig",
            "ReviewConfig",
            "AdditionalReviewConfig",
            "PipelineConfig",
            "CodemanifestConfig",
            "DepConfig",
            "LintConfig",
            "TopicsConfig",
            "load_project_config",
        }
        assert expected <= set(project_mod.__all__)
        for name in expected:
            assert hasattr(project_mod, name), f"{name} missing from goga.config.project"

    def test_old_names_not_importable(self):
        """TaskExecutor and CodemenifestConfig are NOT importable from goga.config."""
        assert not hasattr(goga_config_mod, "TaskExecutor")
        assert not hasattr(goga_config_mod, "CodemenifestConfig")
        assert "TaskExecutor" not in goga_config_mod.__all__
        assert "CodemenifestConfig" not in goga_config_mod.__all__

    def test_retired_names_not_importable(self):
        """TaskExecutorConfig and ReviewExecutorConfig are gone from the facade."""
        assert not hasattr(goga_config_mod, "TaskExecutorConfig")
        assert not hasattr(goga_config_mod, "ReviewExecutorConfig")
        assert "TaskExecutorConfig" not in goga_config_mod.__all__
        assert "ReviewExecutorConfig" not in goga_config_mod.__all__

    def test_old_names_raise_import_error(self):
        """Importing the renamed/typo classes raises ImportError."""
        with pytest.raises(ImportError):
            from goga.config import TaskExecutor  # noqa: F401

        with pytest.raises(ImportError):
            from goga.config import CodemenifestConfig  # noqa: F401

    def test_retired_names_raise_import_error(self):
        """Importing the retired executor configs raises ImportError."""
        with pytest.raises(ImportError):
            from goga.config import TaskExecutorConfig  # noqa: F401

        with pytest.raises(ImportError):
            from goga.config import ReviewExecutorConfig  # noqa: F401


class TestPipelineConfigAPIShape:
    def test_has_agent_field(self):
        assert "agent" in PipelineConfig.__dataclass_fields__

    def test_has_env_field(self):
        assert "env" in PipelineConfig.__dataclass_fields__

    def test_agent_type_is_str_or_none(self):
        assert PipelineConfig.__dataclass_fields__["agent"].type == str | None

    def test_agent_has_default_none(self):
        assert PipelineConfig.__dataclass_fields__["agent"].default is None

    def test_env_type_is_dict(self):
        assert PipelineConfig.__dataclass_fields__["env"].type is dict

    def test_env_has_default(self):
        assert PipelineConfig.__dataclass_fields__["env"].default_factory is not dataclasses.MISSING

    def test_has_proxy_field(self):
        assert "proxy" in PipelineConfig.__dataclass_fields__

    def test_has_hosts_field(self):
        assert "hosts" in PipelineConfig.__dataclass_fields__

    def test_proxy_type_is_optional_str(self):
        proxy_type = PipelineConfig.__dataclass_fields__["proxy"].type
        assert proxy_type == str | None or types.UnionType in type(proxy_type).__mro__

    def test_hosts_type_is_dict_str_str(self):
        assert PipelineConfig.__dataclass_fields__["hosts"].type == dict[str, str]

    def test_proxy_defaults_none(self):
        assert PipelineConfig.__dataclass_fields__["proxy"].default is None

    def test_hosts_has_default_factory(self):
        assert PipelineConfig.__dataclass_fields__["hosts"].default_factory is not dataclasses.MISSING


class TestReviewConfigAPIShape:
    def test_review_config_is_kw_only_dataclass(self):
        """ReviewConfig passes the shared is_kw_only_dataclass helper."""
        assert dataclasses.is_dataclass(ReviewConfig)
        assert is_kw_only_dataclass(ReviewConfig)

    def test_review_config_is_frozen(self):
        """ReviewConfig is frozen — field reassignment raises FrozenInstanceError."""
        review = ReviewConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            review.agent = "codex"  # type: ignore[misc]

    def test_review_config_declared_fields(self):
        """ReviewConfig declares exactly the eleven contract fields."""
        names = [f.name for f in dataclasses.fields(ReviewConfig)]
        assert names == [
            "skip",
            "agent",
            "env",
            "roles",
            "base_ref",
            "strategy",
            "finalize",
            "additional",
            "session_timeout",
            "idle_timeout",
            "wait",
        ]

    def test_review_config_env_factory_default(self):
        """env defaults to an empty dict via a factory."""
        env_field = ReviewConfig.__dataclass_fields__["env"]
        assert env_field.type == dict[str, str]
        assert env_field.default is dataclasses.MISSING
        assert env_field.default_factory is dict
        assert ReviewConfig().env == {}

    def test_review_config_all_fields_default_none(self):
        """Every field except env defaults to None (unset = inherit at the consumer)."""
        params = {f.name: f for f in dataclasses.fields(ReviewConfig)}
        for name in ("skip", "agent", "roles", "base_ref", "strategy", "finalize", "additional",
                     "session_timeout", "idle_timeout", "wait"):
            assert params[name].default is None, name

    def test_review_config_stores_values_verbatim(self):
        """Pure construction stores every value verbatim — no normalization here."""
        additional = AdditionalReviewConfig(agent="cursor", patience=2, max_iterations=4)
        review = ReviewConfig(
            skip=False,
            agent="codex",
            env={"B": "2"},
            roles=["quality"],
            base_ref="main",
            strategy="short",
            finalize="do it",
            additional=additional,
            session_timeout="40m",
            idle_timeout="9m",
            wait="2m",
        )
        assert review.skip is False
        assert review.agent == "codex"
        assert review.env == {"B": "2"}
        assert review.roles == ["quality"]
        assert review.base_ref == "main"
        assert review.strategy == "short"
        assert review.finalize == "do it"
        assert review.additional is additional
        assert review.session_timeout == "40m"
        assert review.idle_timeout == "9m"
        assert review.wait == "2m"

    def test_review_config_empty_roles_stay_empty(self):
        """roles=[] stays an empty list — NOT coerced to None."""
        assert ReviewConfig(roles=[]).roles == []


class TestAdditionalReviewConfigAPIShape:
    def test_additional_review_config_is_kw_only_dataclass(self):
        """AdditionalReviewConfig passes the shared is_kw_only_dataclass helper."""
        assert dataclasses.is_dataclass(AdditionalReviewConfig)
        assert is_kw_only_dataclass(AdditionalReviewConfig)

    def test_additional_review_config_is_frozen(self):
        """AdditionalReviewConfig is frozen — field reassignment raises FrozenInstanceError."""
        additional = AdditionalReviewConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            additional.agent = "codex"  # type: ignore[misc]

    def test_additional_review_config_declared_fields(self):
        """AdditionalReviewConfig declares exactly agent, patience, max_iterations."""
        names = [f.name for f in dataclasses.fields(AdditionalReviewConfig)]
        assert names == ["agent", "patience", "max_iterations"]

    def test_additional_review_config_defaults_none(self):
        """All three fields default to None."""
        params = {f.name: f for f in dataclasses.fields(AdditionalReviewConfig)}
        for name in ("agent", "patience", "max_iterations"):
            assert params[name].default is None, name

    def test_additional_review_config_zero_is_meaningful(self):
        """0 is a meaningful value, not an unset marker — stored verbatim."""
        additional = AdditionalReviewConfig(agent="codex", patience=0, max_iterations=0)
        assert additional.patience == 0
        assert additional.max_iterations == 0


class TestBuildConfigAPIShape:
    def test_build_config_declared_fields(self):
        """BuildConfig exposes exactly the new two-part field set."""
        names = [f.name for f in dataclasses.fields(BuildConfig)]
        assert names == [
            "agent",
            "env",
            "max_iterations",
            "session_timeout",
            "idle_timeout",
            "wait",
            "prompts_dir",
            "agents_dir",
            "proxy",
            "hosts",
            "review",
        ]

    def test_build_config_has_review_field(self):
        assert "review" in BuildConfig.__dataclass_fields__

    def test_build_config_retired_fields_absent(self):
        """The retired fields no longer exist on BuildConfig."""
        for name in ("task_executor", "worktree", "skip_finalize", "codex_review", "review_executor"):
            assert name not in BuildConfig.__dataclass_fields__, name

    def test_has_session_timeout_field(self):
        assert "session_timeout" in BuildConfig.__dataclass_fields__

    def test_has_idle_timeout_field(self):
        assert "idle_timeout" in BuildConfig.__dataclass_fields__

    def test_has_wait_field(self):
        assert "wait" in BuildConfig.__dataclass_fields__

    def test_has_max_iterations_field(self):
        assert "max_iterations" in BuildConfig.__dataclass_fields__

    def test_has_prompts_dir_field(self):
        assert "prompts_dir" in BuildConfig.__dataclass_fields__

    def test_has_agents_dir_field(self):
        assert "agents_dir" in BuildConfig.__dataclass_fields__

    def test_has_proxy_field(self):
        assert "proxy" in BuildConfig.__dataclass_fields__

    def test_has_hosts_field(self):
        assert "hosts" in BuildConfig.__dataclass_fields__

    def test_proxy_type_is_optional_str(self):
        proxy_type = BuildConfig.__dataclass_fields__["proxy"].type
        assert proxy_type == str | None or types.UnionType in type(proxy_type).__mro__

    def test_hosts_type_is_dict_str_str(self):
        assert BuildConfig.__dataclass_fields__["hosts"].type == dict[str, str]

    def test_proxy_defaults_none(self):
        assert BuildConfig.__dataclass_fields__["proxy"].default is None

    def test_hosts_has_default_factory(self):
        assert BuildConfig.__dataclass_fields__["hosts"].default_factory is not dataclasses.MISSING

    def test_does_not_have_image_field(self):
        """BuildConfig.image was removed in the schema break."""
        assert "image" not in BuildConfig.__dataclass_fields__


class TestCodemanifestConfigAPIShape:
    def test_has_usages_field(self):
        assert "usages" in CodemanifestConfig.__dataclass_fields__

    def test_has_annotations_field(self):
        assert "annotations" in CodemanifestConfig.__dataclass_fields__

    def test_usages_type_is_dict(self):
        assert CodemanifestConfig.__dataclass_fields__["usages"].type is dict

    def test_annotations_type_is_optional_str(self):
        ann_type = CodemanifestConfig.__dataclass_fields__["annotations"].type
        # str | None creates a UnionType in Python 3.10+; each evaluation creates a new object
        # so use == instead of `is`, or check get_args
        assert ann_type == str | None or types.UnionType in type(ann_type).__mro__

    def test_usages_has_default_factory(self):
        assert CodemanifestConfig.__dataclass_fields__["usages"].default_factory is not dataclasses.MISSING


class TestConfigAPIShape:
    def test_has_language_field(self):
        assert "language" in ProjectConfig.__dataclass_fields__

    def test_lang_field_removed(self):
        """The rename is a clean break — no `lang` field survives on the model."""
        assert "lang" not in ProjectConfig.__dataclass_fields__

    def test_has_image_field(self):
        assert "image" in ProjectConfig.__dataclass_fields__

    def test_has_build_field(self):
        assert "build" in ProjectConfig.__dataclass_fields__

    def test_has_pipeline_field(self):
        assert "pipeline" in ProjectConfig.__dataclass_fields__

    def test_has_commands_field(self):
        assert "commands" in ProjectConfig.__dataclass_fields__

    def test_has_codemanifest_field(self):
        assert "codemanifest" in ProjectConfig.__dataclass_fields__

    def test_has_tools_field(self):
        assert "tools" in ProjectConfig.__dataclass_fields__

    def test_tools_defaults_to_none(self):
        """tools is optional and defaults to None when not supplied."""
        cfg = ProjectConfig(language="python", image=None, dockerfile=None, build=None, pipeline=None)
        assert cfg.tools is None

    def test_tools_accepts_string_mapping(self):
        cfg = ProjectConfig(
            language="python",
            image=None,
            dockerfile=None,
            build=None,
            pipeline=None,
            tools={"afm": "1.0.x", "ralphex": "1.x"},
        )
        assert cfg.tools == {"afm": "1.0.x", "ralphex": "1.x"}

    def test_tools_accepts_empty_dict(self):
        cfg = ProjectConfig(
            language="python",
            image=None,
            dockerfile=None,
            build=None,
            pipeline=None,
            tools={},
        )
        assert cfg.tools == {}

    def test_image_type_is_optional_str(self):
        image_type = ProjectConfig.__dataclass_fields__["image"].type
        assert image_type == str | None or types.UnionType in type(image_type).__mro__

    def test_config_build_annotation_allows_none(self):
        """None is a legal value for ProjectConfig.build — the dataclass accepts it (D2)."""
        cfg = ProjectConfig(
            language="python",
            image=None,
            dockerfile=None,
            build=None,
            pipeline=None,
            commands={},
            codemanifest=None,
        )
        assert cfg.build is None
        assert cfg.pipeline is None

    def test_config_build_annotation_is_optional_buildconfig(self):
        """typing.get_type_hints reports build as Optional[BuildConfig] (D2)."""
        import typing

        hints = typing.get_type_hints(ProjectConfig)
        build_args = set(typing.get_args(hints["build"]))
        assert BuildConfig in build_args
        assert type(None) in build_args

    def test_config_pipeline_annotation_is_optional_pipelineconfig(self):
        """typing.get_type_hints reports pipeline as Optional[PipelineConfig] (D2)."""
        import typing

        hints = typing.get_type_hints(ProjectConfig)
        pipeline_args = set(typing.get_args(hints["pipeline"]))
        assert PipelineConfig in pipeline_args
        assert type(None) in pipeline_args

    def test_language_is_required(self):
        """ProjectConfig without language raises TypeError (missing required argument)."""
        bc = BuildConfig(agent="claude")
        pc = PipelineConfig(agent="claude")
        with pytest.raises(TypeError, match="language"):
            ProjectConfig(image=None, build=bc, pipeline=pc)

    def test_image_is_required(self):
        """ProjectConfig without image raises TypeError (image has no default)."""
        bc = BuildConfig(agent="claude")
        pc = PipelineConfig(agent="claude")
        with pytest.raises(TypeError, match="image"):
            ProjectConfig(language="python", build=bc, pipeline=pc)

    def test_pipeline_is_required(self):
        """ProjectConfig without pipeline raises TypeError."""
        bc = BuildConfig(agent="claude")
        with pytest.raises(TypeError, match="pipeline"):
            ProjectConfig(language="python", image=None, build=bc)


class TestKwOnlyEnforced:
    def test_pipeline_kw_only(self):
        assert all(f.kw_only for f in dataclasses.fields(PipelineConfig))

    def test_build_config_kw_only(self):
        assert all(f.kw_only for f in dataclasses.fields(BuildConfig))

    def test_review_config_kw_only(self):
        assert all(f.kw_only for f in dataclasses.fields(ReviewConfig))

    def test_additional_review_config_kw_only(self):
        assert all(f.kw_only for f in dataclasses.fields(AdditionalReviewConfig))

    def test_config_kw_only(self):
        assert all(f.kw_only for f in dataclasses.fields(ProjectConfig))

    def test_codemanifest_config_kw_only(self):
        assert all(f.kw_only for f in dataclasses.fields(CodemanifestConfig))

    def test_codemanifest_config_positional_args_rejected(self):
        with pytest.raises(TypeError):
            CodemanifestConfig({"lib": ".specs/lib.md"}, "annotations")

    def test_build_config_positional_args_rejected(self):
        with pytest.raises(TypeError):
            BuildConfig("claude")  # type: ignore[call-arg]

    def test_review_config_positional_args_rejected(self):
        with pytest.raises(TypeError):
            ReviewConfig(True)  # type: ignore[call-arg]

    def test_additional_review_config_positional_args_rejected(self):
        with pytest.raises(TypeError):
            AdditionalReviewConfig("codex")  # type: ignore[call-arg]

    def test_config_positional_args_rejected(self):
        bc = BuildConfig(agent="claude")
        with pytest.raises(TypeError):
            ProjectConfig(bc)


# --- Logic tests ---


class TestPipelineConfigCreation:
    def test_valid_agent_and_env(self):
        pc = PipelineConfig(agent="claude", env={"KEY": "value"})
        assert pc.agent == "claude"
        assert pc.env == {"KEY": "value"}

    def test_empty_env_dict(self):
        pc = PipelineConfig(agent="codex")
        assert pc.env == {}

    def test_distinct_from_build(self):
        """PipelineConfig and BuildConfig are separate types."""
        pc = PipelineConfig(agent="claude")
        bc = BuildConfig(agent="claude")
        assert not isinstance(pc, BuildConfig)
        assert not isinstance(bc, PipelineConfig)

    def test_proxy_defaults_none(self):
        pc = PipelineConfig(agent="claude")
        assert pc.proxy is None

    def test_hosts_defaults_empty_dict(self):
        pc = PipelineConfig(agent="claude")
        assert pc.hosts == {}

    def test_explicit_proxy_and_hosts(self):
        pc = PipelineConfig(agent="claude", proxy="http://x:1", hosts={"a": "1"})
        assert pc.proxy == "http://x:1"
        assert pc.hosts == {"a": "1"}


class TestBuildConfigCreation:
    def test_all_none_optional_fields(self):
        bc = BuildConfig()
        assert bc.agent is None
        assert bc.env == {}
        assert bc.max_iterations is None
        assert bc.session_timeout is None
        assert bc.idle_timeout is None
        assert bc.wait is None
        assert bc.prompts_dir is None
        assert bc.agents_dir is None
        assert bc.proxy is None
        assert bc.hosts == {}
        assert bc.review is None
        assert not hasattr(bc, "task_executor")
        assert not hasattr(bc, "worktree")
        assert not hasattr(bc, "image")

    def test_all_fields_populated(self):
        review = ReviewConfig(
            skip=False,
            agent="codex",
            env={"B": "2"},
            roles=["quality"],
            base_ref="origin/1.2.x",
            strategy="full",
            finalize="final pass",
            additional=AdditionalReviewConfig(agent="cursor", patience=3, max_iterations=4),
        )
        bc = BuildConfig(
            agent="gemini",
            env={"X": "1"},
            max_iterations=10,
            session_timeout="30m",
            idle_timeout="1h",
            wait="5m",
            prompts_dir="/custom/prompts",
            agents_dir="/custom/agents",
            proxy="http://x:1",
            hosts={"a": "1"},
            review=review,
        )
        assert bc.agent == "gemini"
        assert bc.env == {"X": "1"}
        assert bc.max_iterations == 10
        assert bc.session_timeout == "30m"
        assert bc.idle_timeout == "1h"
        assert bc.wait == "5m"
        assert bc.prompts_dir == "/custom/prompts"
        assert bc.agents_dir == "/custom/agents"
        assert bc.proxy == "http://x:1"
        assert bc.hosts == {"a": "1"}
        assert bc.review is review
        assert bc.review.additional.patience == 3
        assert bc.review.additional.max_iterations == 4
        assert bc.review.strategy == "full"

    def test_proxy_defaults_none(self):
        bc = BuildConfig(agent="claude")
        assert bc.proxy is None

    def test_hosts_defaults_empty_dict(self):
        bc = BuildConfig(agent="claude")
        assert bc.hosts == {}

    def test_explicit_proxy_and_hosts(self):
        bc = BuildConfig(agent="claude", proxy="http://x:1", hosts={"a": "1"})
        assert bc.proxy == "http://x:1"
        assert bc.hosts == {"a": "1"}

    def test_build_config_is_frozen(self):
        bc = BuildConfig(agent="claude")
        with pytest.raises(dataclasses.FrozenInstanceError):
            bc.agent = "codex"  # type: ignore[misc]


class TestConfigCreation:
    def test_default_commands_dict(self):
        bc = BuildConfig(agent="claude")
        pc = PipelineConfig(agent="claude")
        cfg = ProjectConfig(language="python", image=None, dockerfile=None, build=bc, pipeline=pc)
        assert cfg.language == "python"
        assert cfg.image is None
        assert cfg.dockerfile is None
        assert cfg.commands == {}

    def test_full_config(self):
        bc = BuildConfig(agent="claude", env={"K": "v"}, review=ReviewConfig(agent="codex"))
        pc = PipelineConfig(agent="codex", env={"P": "1"})
        cfg = ProjectConfig(
            language="python",
            image="qarium/foo:1.0",
            dockerfile="Dockerfile",
            build=bc,
            pipeline=pc,
            commands={"foo": "bar"},
        )
        assert cfg.language == "python"
        assert cfg.image == "qarium/foo:1.0"
        assert cfg.dockerfile == "Dockerfile"
        assert cfg.build is bc
        assert cfg.build.agent == "claude"
        assert cfg.build.review.agent == "codex"
        assert cfg.pipeline is pc
        assert cfg.pipeline.agent == "codex"
        assert cfg.commands == {"foo": "bar"}

    def test_nested_review_access(self):
        bc = BuildConfig(agent="copilot", env={"A": "1", "B": "2"}, review=ReviewConfig(base_ref="main"))
        pc = PipelineConfig(agent="claude")
        cfg = ProjectConfig(language="python", image=None, dockerfile=None, build=bc, pipeline=pc)
        assert isinstance(cfg.build, BuildConfig)
        assert cfg.build.agent == "copilot"
        assert cfg.build.env == {"A": "1", "B": "2"}
        assert isinstance(cfg.build.review, ReviewConfig)
        assert cfg.build.review.base_ref == "main"


class TestCodemanifestConfigCreation:
    def test_creation_with_defaults(self):
        cc = CodemanifestConfig()
        assert cc.usages == {}
        assert cc.annotations is None

    def test_full_creation(self):
        cc = CodemanifestConfig(usages={"lib": ".specs/lib.md"}, annotations="Use lib")
        assert cc.usages == {"lib": ".specs/lib.md"}
        assert cc.annotations == "Use lib"


class TestCodemanifestConfigFrozen:
    def test_frozen(self):
        cc = CodemanifestConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cc.usages = {"x": "y"}


class TestConfigCodemanifestField:
    def test_codemanifest_field_defaults_none(self):
        bc = BuildConfig(agent="claude")
        pc = PipelineConfig(agent="claude")
        cfg = ProjectConfig(language="python", image=None, dockerfile=None, build=bc, pipeline=pc)
        assert cfg.codemanifest is None

    def test_config_with_codemanifest(self):
        bc = BuildConfig(agent="claude")
        pc = PipelineConfig(agent="claude")
        cc = CodemanifestConfig(usages={"lib": ".specs/lib.md"}, annotations="Use lib")
        cfg = ProjectConfig(
            language="python",
            image=None,
            dockerfile=None,
            build=bc,
            pipeline=pc,
            codemanifest=cc,
        )
        assert cfg.codemanifest is cc


# --- Task 1: DepConfig + ProjectConfig.usages ---


class TestDepConfigAPIShape:
    def test_has_git_field(self):
        assert "git" in DepConfig.__dataclass_fields__

    def test_has_ref_field(self):
        assert "ref" in DepConfig.__dataclass_fields__

    def test_git_type_is_str(self):
        assert DepConfig.__dataclass_fields__["git"].type is str

    def test_ref_type_is_optional_str(self):
        ref_type = DepConfig.__dataclass_fields__["ref"].type
        assert ref_type == str | None or types.UnionType in type(ref_type).__mro__

    def test_ref_defaults_to_none(self):
        assert DepConfig.__dataclass_fields__["ref"].default is None

    def test_git_is_required(self):
        """DepConfig without git raises TypeError (missing required argument)."""
        with pytest.raises(TypeError, match="git"):
            DepConfig(ref="main")  # type: ignore[call-arg]

    def test_kw_only_enforced(self):
        assert all(f.kw_only for f in dataclasses.fields(DepConfig))


class TestDepConfigCreation:
    def test_depcfg_is_frozen_kw_only(self):
        """DepConfig stores fields, is frozen, and rejects positional args (kw_only)."""
        cfg = DepConfig(git="https://x/r.git", ref="main")
        assert cfg.git == "https://x/r.git"
        assert cfg.ref == "main"
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.git = "y"  # type: ignore[misc]
        with pytest.raises(TypeError):
            DepConfig("https://x/r.git", "main")  # type: ignore[call-arg]

    def test_depcfg_ref_defaults_to_none(self):
        """ref omitted → None (clone default branch)."""
        cfg = DepConfig(git="https://x/r.git")
        assert cfg.ref is None


class TestProjectConfigUsagesField:
    def test_has_usages_field(self):
        assert "usages" in ProjectConfig.__dataclass_fields__

    def test_usages_defaults_to_none(self):
        """usages omitted → None (section absent, no-op in sync)."""
        cfg = ProjectConfig(language="python", image=None, dockerfile=None, build=None, pipeline=None)
        assert cfg.usages is None

    def test_usages_accepts_nested_depcfg_dict(self):
        """usages can be set to dict[str, dict[str, DepConfig]]."""
        cfg = ProjectConfig(
            language="python",
            image=None,
            dockerfile=None,
            build=None,
            pipeline=None,
            usages={"libs": {"click": DepConfig(git="https://x/click.git", ref="main")}},
        )
        assert cfg.usages == {"libs": {"click": DepConfig(git="https://x/click.git", ref="main")}}
        assert cfg.usages["libs"]["click"].git == "https://x/click.git"
        assert cfg.usages["libs"]["click"].ref == "main"


# --- Plan task: LintConfig + ProjectConfig.lint ---


class TestLintConfigFacadeAndShape:
    def test_facade_exports_lintconfig(self):
        """LintConfig is importable from goga.config, present in __all__, and stores ignore."""
        from goga.config import LintConfig as FacadeLintConfig

        assert hasattr(goga_config_mod, "LintConfig")
        assert "LintConfig" in goga_config_mod.__all__
        assert FacadeLintConfig(ignore=["x"]).ignore == ["x"]
        assert FacadeLintConfig is LintConfig

    def test_lintconfig_ignore_has_no_default(self):
        """ignore is a required field (no default) — the [] default is created by the loader."""
        field_obj = LintConfig.__dataclass_fields__["ignore"]
        assert field_obj.default is dataclasses.MISSING
        assert field_obj.default_factory is dataclasses.MISSING

    def test_lintconfig_kw_only_enforced(self):
        assert all(f.kw_only for f in dataclasses.fields(LintConfig))

    def test_projectconfig_has_lint_field_default_none(self):
        """ProjectConfig.lint defaults to None and keeps its trailing append (topics follows it)."""
        cfg = ProjectConfig(language="python", image=None, dockerfile=None, build=None, pipeline=None)
        assert cfg.lint is None
        assert "lint" in ProjectConfig.__dataclass_fields__

        field_names = list(ProjectConfig.__dataclass_fields__.keys())
        assert field_names[-2] == "lint"
        assert field_names[-1] == "topics"

    def test_projectconfig_lint_accepts_lintconfig(self):
        bc = BuildConfig(agent="claude")
        pc = PipelineConfig(agent="claude")
        lc = LintConfig(ignore=[".venv/"])
        cfg = ProjectConfig(
            language="python",
            image=None,
            dockerfile=None,
            build=bc,
            pipeline=pc,
            lint=lc,
        )
        assert cfg.lint is lc
        assert cfg.lint.ignore == [".venv/"]


class TestLintConfigCreation:
    def test_lintconfig_stores_ignore_verbatim(self):
        """Trailing slash and glob characters are preserved verbatim (no normalization)."""
        cfg = LintConfig(ignore=[".venv/", "*"])
        assert cfg.ignore == [".venv/", "*"]

    def test_lintconfig_empty_ignore_list(self):
        cfg = LintConfig(ignore=[])
        assert cfg.ignore == []

    def test_lintconfig_is_frozen(self):
        cfg = LintConfig(ignore=[".venv/"])
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.ignore = []  # type: ignore[misc]

    def test_lintconfig_rejects_positional_args(self):
        with pytest.raises(TypeError):
            LintConfig([".venv/"])  # type: ignore[call-arg]
