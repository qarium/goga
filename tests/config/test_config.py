# tests/goga/config/test_config.py — contract and logic tests for dataclasses

import dataclasses
import types

import goga.config as goga_config_mod
import pytest
from goga.config import (
    BuildConfig,
    CodemanifestConfig,
    PipelineConfig,
    ProjectConfig,
    TaskExecutorConfig,
)

# --- Contract tests ---


class TestFacadeAvailability:
    def test_import_from_facade(self):
        """ProjectConfig, BuildConfig, TaskExecutorConfig are importable from goga.config."""
        assert hasattr(goga_config_mod, "ProjectConfig")
        assert hasattr(goga_config_mod, "BuildConfig")
        assert hasattr(goga_config_mod, "TaskExecutorConfig")

    def test_pipeline_config_importable(self):
        """PipelineConfig is importable from goga.config and in __all__."""
        assert hasattr(goga_config_mod, "PipelineConfig")
        assert "PipelineConfig" in goga_config_mod.__all__

    def test_codemanifest_config_importable(self):
        """CodemanifestConfig is importable from goga.config and in __all__."""
        assert hasattr(goga_config_mod, "CodemanifestConfig")
        assert "CodemanifestConfig" in goga_config_mod.__all__

    def test_load_config_importable(self):
        """load_project_config is importable from goga.config."""
        assert hasattr(goga_config_mod, "load_project_config")

    def test_old_names_not_importable(self):
        """TaskExecutor and CodemenifestConfig are NOT importable from goga.config."""
        assert not hasattr(goga_config_mod, "TaskExecutor")
        assert not hasattr(goga_config_mod, "CodemenifestConfig")
        assert "TaskExecutor" not in goga_config_mod.__all__
        assert "CodemenifestConfig" not in goga_config_mod.__all__

    def test_old_names_raise_import_error(self):
        """Importing the renamed/typo classes raises ImportError."""
        with pytest.raises(ImportError):
            from goga.config import TaskExecutor  # noqa: F401

        with pytest.raises(ImportError):
            from goga.config import CodemenifestConfig  # noqa: F401


class TestTaskExecutorConfigAPIShape:
    def test_has_agent_field(self):
        assert "agent" in TaskExecutorConfig.__dataclass_fields__

    def test_has_env_field(self):
        assert "env" in TaskExecutorConfig.__dataclass_fields__

    def test_agent_type_is_str(self):
        assert TaskExecutorConfig.__dataclass_fields__["agent"].type is str

    def test_env_type_is_dict(self):
        assert TaskExecutorConfig.__dataclass_fields__["env"].type is dict

    def test_env_has_default(self):
        assert TaskExecutorConfig.__dataclass_fields__["env"].default_factory is not dataclasses.MISSING


class TestPipelineConfigAPIShape:
    def test_has_agent_field(self):
        assert "agent" in PipelineConfig.__dataclass_fields__

    def test_has_env_field(self):
        assert "env" in PipelineConfig.__dataclass_fields__

    def test_agent_type_is_str(self):
        assert PipelineConfig.__dataclass_fields__["agent"].type is str

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


class TestBuildConfigAPIShape:
    def test_has_task_executor_field(self):
        assert "task_executor" in BuildConfig.__dataclass_fields__

    def test_has_worktree_field(self):
        assert "worktree" in BuildConfig.__dataclass_fields__

    def test_has_skip_finalize_field(self):
        assert "skip_finalize" in BuildConfig.__dataclass_fields__

    def test_has_session_timeout_field(self):
        assert "session_timeout" in BuildConfig.__dataclass_fields__

    def test_has_idle_timeout_field(self):
        assert "idle_timeout" in BuildConfig.__dataclass_fields__

    def test_has_wait_field(self):
        assert "wait" in BuildConfig.__dataclass_fields__

    def test_has_max_iterations_field(self):
        assert "max_iterations" in BuildConfig.__dataclass_fields__

    def test_has_review_patience_field(self):
        assert "review_patience" in BuildConfig.__dataclass_fields__

    def test_has_prompts_dir_field(self):
        assert "prompts_dir" in BuildConfig.__dataclass_fields__

    def test_has_agents_dir_field(self):
        assert "agents_dir" in BuildConfig.__dataclass_fields__

    def test_has_codex_review_field(self):
        assert "codex_review" in BuildConfig.__dataclass_fields__

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
    def test_has_lang_field(self):
        assert "lang" in ProjectConfig.__dataclass_fields__

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
        cfg = ProjectConfig(lang="python", image=None, dockerfile=None, build=None, pipeline=None)
        assert cfg.tools is None

    def test_tools_accepts_string_mapping(self):
        cfg = ProjectConfig(
            lang="python",
            image=None,
            dockerfile=None,
            build=None,
            pipeline=None,
            tools={"afm": "1.0.x", "ralphex": "1.x"},
        )
        assert cfg.tools == {"afm": "1.0.x", "ralphex": "1.x"}

    def test_tools_accepts_empty_dict(self):
        cfg = ProjectConfig(
            lang="python",
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
            lang="python",
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

    def test_lang_is_required(self):
        """ProjectConfig without lang raises TypeError (missing required argument)."""
        te = TaskExecutorConfig(agent="claude")
        bc = BuildConfig(task_executor=te)
        pc = PipelineConfig(agent="claude")
        with pytest.raises(TypeError, match="lang"):
            ProjectConfig(image=None, build=bc, pipeline=pc)

    def test_image_is_required(self):
        """ProjectConfig without image raises TypeError (image has no default)."""
        te = TaskExecutorConfig(agent="claude")
        bc = BuildConfig(task_executor=te)
        pc = PipelineConfig(agent="claude")
        with pytest.raises(TypeError, match="image"):
            ProjectConfig(lang="python", build=bc, pipeline=pc)

    def test_pipeline_is_required(self):
        """ProjectConfig without pipeline raises TypeError."""
        te = TaskExecutorConfig(agent="claude")
        bc = BuildConfig(task_executor=te)
        with pytest.raises(TypeError, match="pipeline"):
            ProjectConfig(lang="python", image=None, build=bc)


class TestKwOnlyEnforced:
    def test_task_executor_kw_only(self):
        assert all(f.kw_only for f in dataclasses.fields(TaskExecutorConfig))

    def test_pipeline_kw_only(self):
        assert all(f.kw_only for f in dataclasses.fields(PipelineConfig))

    def test_build_config_kw_only(self):
        assert all(f.kw_only for f in dataclasses.fields(BuildConfig))

    def test_config_kw_only(self):
        assert all(f.kw_only for f in dataclasses.fields(ProjectConfig))

    def test_codemanifest_config_kw_only(self):
        assert all(f.kw_only for f in dataclasses.fields(CodemanifestConfig))

    def test_codemanifest_config_positional_args_rejected(self):
        with pytest.raises(TypeError):
            CodemanifestConfig({"lib": ".specs/lib.md"}, "annotations")

    def test_task_executor_positional_args_rejected(self):
        with pytest.raises(TypeError):
            TaskExecutorConfig("claude")

    def test_build_config_positional_args_rejected(self):
        te = TaskExecutorConfig(agent="claude")
        with pytest.raises(TypeError):
            BuildConfig(te)

    def test_config_positional_args_rejected(self):
        te = TaskExecutorConfig(agent="claude")
        bc = BuildConfig(task_executor=te)
        with pytest.raises(TypeError):
            ProjectConfig(bc)


# --- Logic tests ---


class TestTaskExecutorConfigCreation:
    def test_valid_agent_and_env(self):
        te = TaskExecutorConfig(agent="claude", env={"KEY": "value"})
        assert te.agent == "claude"
        assert te.env == {"KEY": "value"}

    def test_empty_env_dict(self):
        te = TaskExecutorConfig(agent="codex")
        assert te.env == {}

    def test_custom_agent_path(self):
        te = TaskExecutorConfig(agent="custom:/path/to/script")
        assert te.agent == "custom:/path/to/script"


class TestPipelineConfigCreation:
    def test_valid_agent_and_env(self):
        pc = PipelineConfig(agent="claude", env={"KEY": "value"})
        assert pc.agent == "claude"
        assert pc.env == {"KEY": "value"}

    def test_empty_env_dict(self):
        pc = PipelineConfig(agent="codex")
        assert pc.env == {}

    def test_distinct_from_task_executor(self):
        """PipelineConfig and TaskExecutorConfig are separate types."""
        pc = PipelineConfig(agent="claude")
        te = TaskExecutorConfig(agent="claude")
        assert not isinstance(pc, TaskExecutorConfig)
        assert not isinstance(te, PipelineConfig)

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
        te = TaskExecutorConfig(agent="claude")
        bc = BuildConfig(task_executor=te)
        assert bc.task_executor is te
        assert bc.worktree is None
        assert bc.skip_finalize is None
        assert bc.session_timeout is None
        assert bc.idle_timeout is None
        assert bc.wait is None
        assert bc.max_iterations is None
        assert bc.review_patience is None
        assert bc.prompts_dir is None
        assert bc.agents_dir is None
        assert bc.codex_review is None
        assert bc.proxy is None
        assert bc.hosts == {}
        assert not hasattr(bc, "image")

    def test_all_fields_populated(self):
        te = TaskExecutorConfig(agent="gemini", env={"X": "1"})
        bc = BuildConfig(
            task_executor=te,
            worktree=True,
            skip_finalize=False,
            session_timeout="30m",
            idle_timeout="1h",
            wait="5m",
            max_iterations=10,
            review_patience=3,
            prompts_dir="/custom/prompts",
            agents_dir="/custom/agents",
            codex_review=True,
        )
        assert bc.task_executor.agent == "gemini"
        assert bc.task_executor.env == {"X": "1"}
        assert bc.worktree is True
        assert bc.skip_finalize is False
        assert bc.session_timeout == "30m"
        assert bc.idle_timeout == "1h"
        assert bc.wait == "5m"
        assert bc.max_iterations == 10
        assert bc.review_patience == 3
        assert bc.prompts_dir == "/custom/prompts"
        assert bc.agents_dir == "/custom/agents"
        assert bc.codex_review is True

    def test_proxy_defaults_none(self):
        te = TaskExecutorConfig(agent="claude")
        bc = BuildConfig(task_executor=te)
        assert bc.proxy is None

    def test_hosts_defaults_empty_dict(self):
        te = TaskExecutorConfig(agent="claude")
        bc = BuildConfig(task_executor=te)
        assert bc.hosts == {}

    def test_explicit_proxy_and_hosts(self):
        te = TaskExecutorConfig(agent="claude")
        bc = BuildConfig(task_executor=te, proxy="http://x:1", hosts={"a": "1"})
        assert bc.proxy == "http://x:1"
        assert bc.hosts == {"a": "1"}


class TestConfigCreation:
    def test_default_commands_dict(self):
        te = TaskExecutorConfig(agent="claude")
        bc = BuildConfig(task_executor=te)
        pc = PipelineConfig(agent="claude")
        cfg = ProjectConfig(lang="python", image=None, dockerfile=None, build=bc, pipeline=pc)
        assert cfg.lang == "python"
        assert cfg.image is None
        assert cfg.dockerfile is None
        assert cfg.commands == {}

    def test_full_config(self):
        te = TaskExecutorConfig(agent="claude", env={"K": "v"})
        bc = BuildConfig(task_executor=te, worktree=True)
        pc = PipelineConfig(agent="codex", env={"P": "1"})
        cfg = ProjectConfig(
            lang="python",
            image="qarium/foo:1.0",
            dockerfile="Dockerfile",
            build=bc,
            pipeline=pc,
            commands={"foo": "bar"},
        )
        assert cfg.lang == "python"
        assert cfg.image == "qarium/foo:1.0"
        assert cfg.dockerfile == "Dockerfile"
        assert cfg.build is bc
        assert cfg.build.task_executor is te
        assert cfg.pipeline is pc
        assert cfg.pipeline.agent == "codex"
        assert cfg.commands == {"foo": "bar"}

    def test_nested_task_executor_access(self):
        te = TaskExecutorConfig(agent="copilot", env={"A": "1", "B": "2"})
        bc = BuildConfig(task_executor=te)
        pc = PipelineConfig(agent="claude")
        cfg = ProjectConfig(lang="python", image=None, dockerfile=None, build=bc, pipeline=pc)
        assert isinstance(cfg.build.task_executor, TaskExecutorConfig)
        assert cfg.build.task_executor.agent == "copilot"
        assert cfg.build.task_executor.env == {"A": "1", "B": "2"}


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
        te = TaskExecutorConfig(agent="claude")
        bc = BuildConfig(task_executor=te)
        pc = PipelineConfig(agent="claude")
        cfg = ProjectConfig(lang="python", image=None, dockerfile=None, build=bc, pipeline=pc)
        assert cfg.codemanifest is None

    def test_config_with_codemanifest(self):
        te = TaskExecutorConfig(agent="claude")
        bc = BuildConfig(task_executor=te)
        pc = PipelineConfig(agent="claude")
        cc = CodemanifestConfig(usages={"lib": ".specs/lib.md"}, annotations="Use lib")
        cfg = ProjectConfig(
            lang="python",
            image=None,
            dockerfile=None,
            build=bc,
            pipeline=pc,
            codemanifest=cc,
        )
        assert cfg.codemanifest is cc
