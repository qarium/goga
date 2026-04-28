# tests/goga/config/test_loader.py — contract and logic tests for load_config

import dataclasses
import inspect

import goga.config as goga_config_mod
import pytest
import yaml
from goga.config import Config, load_config

# --- Helpers ---


@pytest.fixture
def goga_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write_goga_yml(path, content: str):
    (path / ".goga.yml").write_text(content)


# --- YAML fixtures ---


MINIMAL_YAML = """\
language: python
build:
  task_executor:
    agent: claude
"""

FULL_YAML = """\
language: go
commands:
  test: go test ./...
  build: go build ./...
build:
  task_executor:
    agent: gemini
    env:
      FOO: bar
      BAZ: qux
  worktree: false
  skip_finalize: true
  session_timeout: "30m"
  idle_timeout: "1h"
  wait: "5m"
  max_iterations: 10
  review_patience: 3
  prompts_dir: "/custom/prompts"
  agents_dir: "/custom/agents"
  codex_review: true
"""

HAPPY_YAML = """\
language: python
build:
  task_executor:
    agent: claude
    env:
      KEY: value
  worktree: true
commands:
  foo: bar
"""

# --- Contract tests ---


class TestLoadConfigFacade:
    def test_load_config_facade(self):
        """load_config is importable from goga.config."""
        assert hasattr(goga_config_mod, "load_config")
        assert callable(goga_config_mod.load_config)

    def test_load_config_is_callable_no_args(self):
        """load_config accepts no arguments."""
        sig = inspect.signature(load_config)
        assert list(sig.parameters.keys()) == []

    def test_load_config_returns_config(self):
        """load_config returns a Config instance (annotation)."""
        ret = inspect.signature(load_config).return_annotation
        assert ret is Config

    def test_load_config_returns_config_instance(self, goga_project):
        """load_config actually returns a Config instance at runtime."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        result = load_config()
        assert isinstance(result, Config)


# --- Positive tests ---


class TestLoadConfigPositive:
    def test_load_config_minimal_valid_yaml(self, goga_project):
        """Minimal .goga.yml with language+build.task_executor.agent."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_config()
        assert config.lang == "python"
        assert config.build.task_executor.agent == "claude"
        assert config.build.task_executor.env == {}
        assert config.commands == {}
        assert config.build.worktree is None

    def test_load_config_full_yaml(self, goga_project):
        """.goga.yml with ALL fields populated."""
        _write_goga_yml(goga_project, FULL_YAML)
        config = load_config()
        assert config.lang == "go"
        assert config.commands == {"test": "go test ./...", "build": "go build ./..."}
        assert config.build.task_executor.agent == "gemini"
        assert config.build.task_executor.env == {"FOO": "bar", "BAZ": "qux"}
        assert config.build.worktree is False
        assert config.build.skip_finalize is True
        assert config.build.session_timeout == "30m"
        assert config.build.idle_timeout == "1h"
        assert config.build.wait == "5m"
        assert config.build.max_iterations == 10
        assert config.build.review_patience == 3
        assert config.build.prompts_dir == "/custom/prompts"
        assert config.build.agents_dir == "/custom/agents"
        assert config.build.codex_review is True

    def test_load_config_custom_agent_path(self, goga_project):
        """agent: custom:/path/to/script with env."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: custom:/path/to/script
    env:
      K: v
""",
        )
        config = load_config()
        assert config.build.task_executor.agent == "custom:/path/to/script"
        assert config.build.task_executor.env == {"K": "v"}

    def test_load_config_happy_path(self, goga_project):
        """Happy path with language, env, worktree, commands."""
        _write_goga_yml(goga_project, HAPPY_YAML)
        config = load_config()
        assert config.lang == "python"
        assert config.build.task_executor.agent == "claude"
        assert config.build.task_executor.env == {"KEY": "value"}
        assert config.build.worktree is True
        assert config.commands == {"foo": "bar"}

    def test_task_executor_env_with_multiple_vars(self, goga_project):
        """Multiple env vars."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: codex
    env:
      VAR1: value1
      VAR2: value2
      VAR3: value3
""",
        )
        config = load_config()
        assert config.build.task_executor.env == {
            "VAR1": "value1",
            "VAR2": "value2",
            "VAR3": "value3",
        }

    def test_load_config_extra_build_fields_ignored(self, goga_project):
        """Unknown build fields are silently ignored."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
  unknown_field: value
""",
        )
        config = load_config()
        assert config.build.task_executor.agent == "claude"


# --- Negative tests ---


class TestLoadConfigNegative:
    def test_load_config_file_not_found(self, goga_project):
        """No .goga.yml in directory."""
        with pytest.raises(FileNotFoundError, match=r"\.goga\.yml"):
            load_config()

    def test_load_config_empty_file(self, goga_project):
        """0-byte .goga.yml."""
        _write_goga_yml(goga_project, "")
        with pytest.raises(FileNotFoundError, match=r"\.goga\.yml"):
            load_config()

    def test_load_config_not_a_mapping(self, goga_project):
        """YAML list content."""
        _write_goga_yml(goga_project, "- item1\n- item2\n")
        with pytest.raises(ValueError, match="mapping"):
            load_config()

    def test_load_config_missing_language(self, goga_project):
        """.goga.yml without language key."""
        _write_goga_yml(
            goga_project,
            """\
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(KeyError, match="language is required"):
            load_config()

    def test_load_config_language_null_raises(self, goga_project):
        """language: null (null, not string)."""
        _write_goga_yml(
            goga_project,
            """\
language:
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match="language must be a non-empty string"):
            load_config()

    def test_load_config_language_empty_raises(self, goga_project):
        """language: '' (empty string)."""
        _write_goga_yml(
            goga_project,
            """\
language: ""
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match="language must be a non-empty string"):
            load_config()

    def test_load_config_language_bool_raises(self, goga_project):
        """language: true (bool, not string)."""
        _write_goga_yml(
            goga_project,
            """\
language: true
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match="language must be a non-empty string"):
            load_config()

    def test_load_config_language_whitespace_only_raises(self, goga_project):
        """language: '   ' (whitespace-only string)."""
        _write_goga_yml(
            goga_project,
            """\
language: "   "
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match="language must be a non-empty string"):
            load_config()

    def test_load_config_env_non_string_keys(self, goga_project):
        """env: {123: value} (int key)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
    env:
      123: value
""",
        )
        with pytest.raises(ValueError, match="env must have string"):
            load_config()

    def test_load_config_missing_build(self, goga_project):
        """.goga.yml without build key."""
        _write_goga_yml(goga_project, "language: python\n")
        with pytest.raises(KeyError, match="build is required"):
            load_config()

    def test_load_config_missing_task_executor(self, goga_project):
        """build section without task_executor."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  worktree: true
""",
        )
        with pytest.raises(KeyError, match=r"build\.task_executor is required"):
            load_config()

    def test_load_config_empty_build_raises(self, goga_project):
        """build: {} (no task_executor)."""
        _write_goga_yml(goga_project, "language: python\nbuild: {}\n")
        with pytest.raises(KeyError, match=r"build\.task_executor is required"):
            load_config()

    def test_load_config_missing_agent(self, goga_project):
        """task_executor: {} (no agent key)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor: {}
""",
        )
        with pytest.raises(ValueError, match="agent is required"):
            load_config()

    def test_load_config_empty_agent(self, goga_project):
        """agent: '' (empty string)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: ""
""",
        )
        with pytest.raises(ValueError, match="agent is required"):
            load_config()

    def test_load_config_whitespace_agent_raises(self, goga_project):
        """agent: '   ' (whitespace-only string)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: "   "
""",
        )
        with pytest.raises(ValueError, match="agent is required"):
            load_config()

    def test_load_config_env_not_mapping(self, goga_project):
        """env: "not-a-dict"."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
    env: not-a-dict
""",
        )
        with pytest.raises(ValueError, match="env must be a mapping"):
            load_config()

    def test_load_config_env_non_string_values(self, goga_project):
        """env: {KEY: 123}."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
    env:
      KEY: 123
""",
        )
        with pytest.raises(ValueError, match="env must have string"):
            load_config()

    def test_load_config_agent_bool_raises(self, goga_project):
        """agent: true (bool, not string)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: true
""",
        )
        with pytest.raises(ValueError, match="agent is required"):
            load_config()

    def test_load_config_task_executor_scalar_raises(self, goga_project):
        """task_executor: claude (scalar, not mapping)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor: claude
""",
        )
        with pytest.raises(ValueError, match="task_executor must be a mapping"):
            load_config()

    def test_load_config_task_executor_null_raises(self, goga_project):
        """task_executor: null (null, not mapping)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
""",
        )
        with pytest.raises(ValueError, match="task_executor must be a mapping"):
            load_config()

    def test_load_config_commands_not_dict_raises(self, goga_project):
        """commands: string (not mapping)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
commands: string
""",
        )
        with pytest.raises(ValueError, match="'commands' must be a mapping"):
            load_config()

    def test_load_config_build_not_dict_raises(self, goga_project):
        """build: true (not mapping)."""
        _write_goga_yml(goga_project, "language: python\nbuild: true\n")
        with pytest.raises(ValueError, match="'build' must be a mapping"):
            load_config()

    def test_load_config_env_bool_value_raises(self, goga_project):
        """env: {DEBUG: true}."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
    env:
      DEBUG: true
""",
        )
        with pytest.raises(ValueError, match="env must have string"):
            load_config()

    def test_load_config_env_null_value_raises(self, goga_project):
        """env: {EMPTY: null}."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
    env:
      EMPTY:
""",
        )
        with pytest.raises(ValueError, match="env must have string"):
            load_config()


# --- Edge case tests ---


class TestLoadConfigEdgeCases:
    def test_load_config_commands_optional(self, goga_project):
        """.goga.yml without commands section."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_config()
        assert config.commands == {}

    def test_load_config_frozen_immutability(self, goga_project):
        """Config objects are frozen — mutation raises FrozenInstanceError."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_config()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.lang = "go"

    def test_load_config_invalid_yaml_syntax(self, goga_project):
        """Bad YAML syntax."""
        _write_goga_yml(
            goga_project,
            "language: python\nbuild:\n  task_executor:\n    agent: [unclosed\n",
        )
        with pytest.raises(yaml.YAMLError):
            load_config()
