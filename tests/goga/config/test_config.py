# tests/goga/config/test_config.py — contract and logic tests for dataclasses

import dataclasses

import goga.config as goga_config_mod
import pytest
from goga.config import BuildConfig, Config, TaskExecutor

# --- Contract tests ---


class TestFacadeAvailability:
    def test_import_from_facade(self):
        """Config, BuildConfig, TaskExecutor are importable from goga.config."""
        assert hasattr(goga_config_mod, "Config")
        assert hasattr(goga_config_mod, "BuildConfig")
        assert hasattr(goga_config_mod, "TaskExecutor")

    def test_load_config_importable(self):
        """load_config is importable from goga.config."""
        assert hasattr(goga_config_mod, "load_config")


class TestTaskExecutorAPIShape:
    def test_has_agent_field(self):
        assert "agent" in TaskExecutor.__dataclass_fields__

    def test_has_env_field(self):
        assert "env" in TaskExecutor.__dataclass_fields__

    def test_agent_type_is_str(self):
        assert TaskExecutor.__dataclass_fields__["agent"].type is str

    def test_env_type_is_dict(self):
        assert TaskExecutor.__dataclass_fields__["env"].type is dict

    def test_env_has_default(self):
        assert TaskExecutor.__dataclass_fields__["env"].default_factory is not dataclasses.MISSING


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


class TestConfigAPIShape:
    def test_has_lang_field(self):
        assert "lang" in Config.__dataclass_fields__

    def test_has_build_field(self):
        assert "build" in Config.__dataclass_fields__

    def test_has_commands_field(self):
        assert "commands" in Config.__dataclass_fields__

    def test_lang_is_required(self):
        """Config without lang raises TypeError (missing required argument)."""
        te = TaskExecutor(agent="claude")
        bc = BuildConfig(task_executor=te)
        with pytest.raises(TypeError, match="lang"):
            Config(build=bc)


class TestKwOnlyEnforced:
    def test_task_executor_kw_only(self):
        assert TaskExecutor.__dataclass_params__.kw_only is True

    def test_build_config_kw_only(self):
        assert BuildConfig.__dataclass_params__.kw_only is True

    def test_config_kw_only(self):
        assert Config.__dataclass_params__.kw_only is True

    def test_task_executor_positional_args_rejected(self):
        with pytest.raises(TypeError):
            TaskExecutor("claude")

    def test_build_config_positional_args_rejected(self):
        te = TaskExecutor(agent="claude")
        with pytest.raises(TypeError):
            BuildConfig(te)

    def test_config_positional_args_rejected(self):
        te = TaskExecutor(agent="claude")
        bc = BuildConfig(task_executor=te)
        with pytest.raises(TypeError):
            Config(bc)


# --- Logic tests ---


class TestTaskExecutorCreation:
    def test_valid_agent_and_env(self):
        te = TaskExecutor(agent="claude", env={"KEY": "value"})
        assert te.agent == "claude"
        assert te.env == {"KEY": "value"}

    def test_empty_env_dict(self):
        te = TaskExecutor(agent="codex")
        assert te.env == {}

    def test_custom_agent_path(self):
        te = TaskExecutor(agent="custom:/path/to/script")
        assert te.agent == "custom:/path/to/script"


class TestBuildConfigCreation:
    def test_all_none_optional_fields(self):
        te = TaskExecutor(agent="claude")
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

    def test_all_fields_populated(self):
        te = TaskExecutor(agent="gemini", env={"X": "1"})
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


class TestConfigCreation:
    def test_default_commands_dict(self):
        te = TaskExecutor(agent="claude")
        bc = BuildConfig(task_executor=te)
        cfg = Config(lang="python", build=bc)
        assert cfg.lang == "python"
        assert cfg.commands == {}

    def test_full_config(self):
        te = TaskExecutor(agent="claude", env={"K": "v"})
        bc = BuildConfig(task_executor=te, worktree=True)
        cfg = Config(lang="python", build=bc, commands={"foo": "bar"})
        assert cfg.lang == "python"
        assert cfg.build is bc
        assert cfg.build.task_executor is te
        assert cfg.commands == {"foo": "bar"}

    def test_nested_task_executor_access(self):
        te = TaskExecutor(agent="copilot", env={"A": "1", "B": "2"})
        bc = BuildConfig(task_executor=te)
        cfg = Config(lang="python", build=bc)
        assert isinstance(cfg.build.task_executor, TaskExecutor)
        assert cfg.build.task_executor.agent == "copilot"
        assert cfg.build.task_executor.env == {"A": "1", "B": "2"}


class TestConfigRequiredLang:
    def test_config_without_lang_raises_type_error(self):
        """Config(build=bc) without lang raises TypeError."""
        te = TaskExecutor(agent="claude")
        bc = BuildConfig(task_executor=te)
        with pytest.raises(TypeError):
            Config(build=bc)
