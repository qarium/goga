# tests/goga/config/test_loader.py — contract and logic tests for load_config

import dataclasses
import inspect

import goga.config as goga_config_mod
import pytest
import yaml
from goga.config import (
    CodemanifestConfig,
    Config,
    PipelineConfig,
    TaskExecutorConfig,
    load_config,
)
from goga.config.loader import _parse_codemanifest, _parse_dockerfile

# --- Helpers ---


@pytest.fixture
def goga_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write_goga_yml(path, content: str):
    goga_dir = path / ".goga"
    goga_dir.mkdir(exist_ok=True)
    (goga_dir / "config.yml").write_text(content)


# --- YAML fixtures ---


MINIMAL_YAML = """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
"""

FULL_YAML = """\
language: go
image: goga:latest
commands:
  test: go test ./...
  build: go build ./...
pipeline:
  agent: codex
  env:
    PIPELINE_OPT: "1"
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
image: qarium/foo:1.0
pipeline:
  agent: claude
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
        """Minimal .goga/config.yml with language+image+pipeline+build.task_executor.agent."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_config()
        assert config.lang == "python"
        assert config.image == "qarium/foo:1.0"
        assert config.build.task_executor.agent == "claude"
        assert config.build.task_executor.env == {}
        assert config.commands == {}
        assert config.build.worktree is None

    def test_load_config_pipeline_defaults(self, goga_project):
        """pipeline.env defaults to empty when not specified."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_config()
        assert config.pipeline.agent == "claude"
        assert config.pipeline.env == {}

    def test_load_config_full_yaml(self, goga_project):
        """.goga/config.yml with ALL fields populated."""
        _write_goga_yml(goga_project, FULL_YAML)
        config = load_config()
        assert config.lang == "go"
        assert config.image == "goga:latest"
        assert config.commands == {"test": "go test ./...", "build": "go build ./..."}
        assert config.pipeline.agent == "codex"
        assert config.pipeline.env == {"PIPELINE_OPT": "1"}
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
image: qarium/foo:1.0
pipeline:
  agent: claude
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
        assert config.image == "qarium/foo:1.0"
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
image: qarium/foo:1.0
pipeline:
  agent: claude
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
        """Unknown build fields are silently ignored (except image, which is rejected)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
  unknown_field: value
""",
        )
        config = load_config()
        assert config.build.task_executor.agent == "claude"


# --- Proxy and hosts tests ---


class TestLoadConfigProxyHosts:
    def test_load_config_pipeline_proxy_and_hosts_populated(self, goga_project):
        """pipeline.proxy and pipeline.hosts are read into PipelineConfig."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
  proxy: "http://corp:3128"
  hosts:
    foo.local: 127.0.0.1
    bar.local: 10.0.0.2
build:
  task_executor:
    agent: claude
""",
        )
        config = load_config()
        assert config.pipeline.proxy == "http://corp:3128"
        assert config.pipeline.hosts == {"foo.local": "127.0.0.1", "bar.local": "10.0.0.2"}

    def test_load_config_pipeline_proxy_hosts_absent_defaults(self, goga_project):
        """Missing pipeline.proxy/hosts default to None and empty dict."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_config()
        assert config.pipeline.proxy is None
        assert config.pipeline.hosts == {}

    def test_load_config_build_proxy_and_hosts_populated(self, goga_project):
        """build.proxy and build.hosts are read into BuildConfig."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
  proxy: "http://build-proxy:8080"
  hosts:
    svc.local: 192.168.1.1
""",
        )
        config = load_config()
        assert config.build.proxy == "http://build-proxy:8080"
        assert config.build.hosts == {"svc.local": "192.168.1.1"}

    def test_load_config_build_proxy_hosts_absent_defaults(self, goga_project):
        """Missing build.proxy/hosts default to None and empty dict."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_config()
        assert config.build.proxy is None
        assert config.build.hosts == {}

    def test_load_config_hosts_null_treated_as_empty(self, goga_project):
        """pipeline.hosts: null resolves to empty dict, not None."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
  hosts:
build:
  task_executor:
    agent: claude
""",
        )
        config = load_config()
        assert config.pipeline.hosts == {}

    def test_load_config_proxy_null_treated_as_none(self, goga_project):
        """pipeline.proxy: null resolves to None."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
  proxy:
build:
  task_executor:
    agent: claude
""",
        )
        config = load_config()
        assert config.pipeline.proxy is None


class TestLoadConfigProxyHostsNegative:
    def test_load_config_pipeline_proxy_non_string_raises(self, goga_project):
        """pipeline.proxy must be a string when present."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
  proxy: 3128
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match=r"pipeline\.proxy must be a string"):
            load_config()

    def test_load_config_build_proxy_non_string_raises(self, goga_project):
        """build.proxy must be a string when present."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
  proxy: 3128
""",
        )
        with pytest.raises(ValueError, match=r"build\.proxy must be a string"):
            load_config()

    def test_load_config_pipeline_hosts_not_mapping_raises(self, goga_project):
        """pipeline.hosts must be a mapping when present."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
  hosts: not-a-mapping
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match=r"pipeline\.hosts must be a mapping"):
            load_config()

    def test_load_config_build_hosts_not_mapping_raises(self, goga_project):
        """build.hosts must be a mapping when present."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
  hosts: not-a-mapping
""",
        )
        with pytest.raises(ValueError, match=r"build\.hosts must be a mapping"):
            load_config()

    def test_load_config_pipeline_hosts_non_string_value_raises(self, goga_project):
        """pipeline.hosts values must be strings."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
  hosts:
    foo.local: 127.0.0.1
    bar.local: 10
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match=r"pipeline\.hosts must have string keys and values"):
            load_config()

    def test_load_config_build_hosts_non_string_key_raises(self, goga_project):
        """build.hosts keys must be strings."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
  hosts:
    123: 10.0.0.1
""",
        )
        with pytest.raises(ValueError, match=r"build\.hosts must have string keys and values"):
            load_config()


# --- Schema-break tests ---


class TestLoadConfigSchemaBreak:
    def test_load_config_minimal_valid_returns_config_with_image_and_pipeline(self, goga_project):
        """Minimal valid config exposes top-level image + pipeline + build.task_executor."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_config()
        assert config.lang == "python"
        assert config.image == "qarium/foo:1.0"
        assert config.pipeline.agent == "claude"
        assert isinstance(config.pipeline, PipelineConfig)
        assert config.build.task_executor.agent == "claude"
        assert isinstance(config.build.task_executor, TaskExecutorConfig)
        # BuildConfig.image was removed
        assert not hasattr(config.build, "image")
        # codemanifest absent -> None
        assert config.codemanifest is None

    def test_load_config_rejects_build_image(self, goga_project):
        """The deprecated build.image field is hard-rejected."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
  image: goga:latest
""",
        )
        with pytest.raises(ValueError, match=r"build\.image"):
            load_config()

    def test_load_config_pipeline_absent_returns_none(self, goga_project):
        """YAML without the pipeline block yields config.pipeline is None."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
build:
  task_executor:
    agent: claude
""",
        )
        config = load_config()
        assert config.pipeline is None

    def test_load_config_image_none_is_valid(self, goga_project):
        """YAML without the top-level image field yields config.image is None."""
        _write_goga_yml(
            goga_project,
            """\
language: python
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
""",
        )
        config = load_config()
        assert config.image is None

    def test_load_config_pipeline_agent_empty_raises(self, goga_project):
        """pipeline.agent empty string raises ValueError."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: ""
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match=r"pipeline\.agent"):
            load_config()

    def test_load_config_pipeline_agent_missing_raises(self, goga_project):
        """pipeline block without agent raises ValueError."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline: {}
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match=r"pipeline\.agent"):
            load_config()

    def test_load_config_image_non_string_raises(self, goga_project):
        """image must be a string when present."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: 123
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match="image must be a string"):
            load_config()


# --- Optional sections tests (pipeline/build absent → None) ---


class TestLoadConfigOptionalSections:
    def test_load_config_minimal_only_language(self, goga_project):
        """Config with only language → all other sections None / empty."""
        _write_goga_yml(
            goga_project,
            """\
language: python
""",
        )
        config = load_config()
        assert config.lang == "python"
        assert config.image is None
        assert config.dockerfile is None
        assert config.pipeline is None
        assert config.build is None
        assert config.commands == {}
        assert config.codemanifest is None

    def test_load_config_pipeline_null_treated_as_absent(self, goga_project):
        """pipeline: null → config.pipeline is None."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline: null
build:
  task_executor:
    agent: claude
""",
        )
        config = load_config()
        assert config.pipeline is None

    def test_load_config_build_null_treated_as_absent(self, goga_project):
        """build: null → config.build is None."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build: null
""",
        )
        config = load_config()
        assert config.build is None

    def test_load_config_empty_pipeline_mapping_raises_inner_error(self, goga_project):
        """pipeline: {} → inner validation preserved (ValueError on missing agent)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline: {}
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match=r"pipeline\.agent"):
            load_config()

    def test_load_config_empty_build_mapping_raises_inner_error(self, goga_project):
        """build: {} → inner validation preserved (KeyError on missing task_executor)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build: {}
""",
        )
        with pytest.raises(KeyError, match=r"build\.task_executor is required"):
            load_config()


# --- Negative tests ---


class TestLoadConfigNegative:
    def test_load_config_file_not_found(self, goga_project):
        """No .goga/config.yml in directory."""
        with pytest.raises(FileNotFoundError, match=r"\.goga/config\.yml"):
            load_config()

    def test_load_config_empty_file(self, goga_project):
        """0-byte .goga/config.yml."""
        _write_goga_yml(goga_project, "")
        with pytest.raises(FileNotFoundError, match=r"\.goga/config\.yml"):
            load_config()

    def test_load_config_not_a_mapping(self, goga_project):
        """YAML list content."""
        _write_goga_yml(goga_project, "- item1\n- item2\n")
        with pytest.raises(ValueError, match="mapping"):
            load_config()

    def test_load_config_missing_language(self, goga_project):
        """.goga/config.yml without language key."""
        _write_goga_yml(
            goga_project,
            """\
image: qarium/foo:1.0
pipeline:
  agent: claude
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
image: qarium/foo:1.0
pipeline:
  agent: claude
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
image: qarium/foo:1.0
pipeline:
  agent: claude
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
image: qarium/foo:1.0
pipeline:
  agent: claude
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
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match="language must be a non-empty string"):
            load_config()

    def test_load_config_task_executor_env_non_string_keys(self, goga_project):
        """task_executor env: {123: value} (int key)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
    env:
      123: value
""",
        )
        with pytest.raises(ValueError, match="env must have string"):
            load_config()

    def test_load_config_pipeline_env_non_string_keys(self, goga_project):
        """pipeline env: {123: value} (int key)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
  env:
    123: value
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match="env must have string"):
            load_config()

    def test_load_config_build_absent_returns_none(self, goga_project):
        """YAML without the build block yields config.build is None."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
""",
        )
        config = load_config()
        assert config.build is None

    def test_load_config_missing_task_executor(self, goga_project):
        """build section without task_executor."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  worktree: true
""",
        )
        with pytest.raises(KeyError, match=r"build\.task_executor is required"):
            load_config()

    def test_load_config_empty_build_raises(self, goga_project):
        """build: {} (no task_executor)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build: {}
""",
        )
        with pytest.raises(KeyError, match=r"build\.task_executor is required"):
            load_config()

    def test_load_config_missing_agent(self, goga_project):
        """task_executor: {} (no agent key)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
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
image: qarium/foo:1.0
pipeline:
  agent: claude
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
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: "   "
""",
        )
        with pytest.raises(ValueError, match="agent is required"):
            load_config()

    def test_load_config_task_executor_env_not_mapping(self, goga_project):
        """env: "not-a-dict"."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
    env: not-a-dict
""",
        )
        with pytest.raises(ValueError, match="env must be a mapping"):
            load_config()

    def test_load_config_task_executor_env_non_string_values(self, goga_project):
        """env: {KEY: 123}."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
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
image: qarium/foo:1.0
pipeline:
  agent: claude
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
image: qarium/foo:1.0
pipeline:
  agent: claude
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
image: qarium/foo:1.0
pipeline:
  agent: claude
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
image: qarium/foo:1.0
pipeline:
  agent: claude
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
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build: true
""",
        )
        with pytest.raises(ValueError, match="'build' must be a mapping"):
            load_config()

    def test_load_config_pipeline_not_dict_raises(self, goga_project):
        """pipeline: true (not mapping)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline: true
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match="'pipeline' must be a mapping"):
            load_config()

    def test_load_config_task_executor_env_bool_value_raises(self, goga_project):
        """env: {DEBUG: true}."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
    env:
      DEBUG: true
""",
        )
        with pytest.raises(ValueError, match="env must have string"):
            load_config()

    def test_load_config_task_executor_env_null_value_raises(self, goga_project):
        """env: {EMPTY: null}."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
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
        """.goga/config.yml without commands section."""
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
            "language: python\npipeline:\n  agent: claude\nbuild:\n  task_executor:\n    agent: [unclosed\n",
        )
        with pytest.raises(yaml.YAMLError):
            load_config()


# --- Contract tests for _parse_codemanifest ---


class TestParseCodemanifestContract:
    def test_parse_codemanifest_exists(self):
        """_parse_codemanifest is importable from goga.config.loader."""
        assert callable(_parse_codemanifest)

    def test_parse_codemanifest_signature(self):
        """_parse_codemanifest accepts a single dict parameter."""
        sig = inspect.signature(_parse_codemanifest)
        params = list(sig.parameters.keys())
        assert params == ["data"]

    def test_parse_codemanifest_return_annotation(self):
        """_parse_codemanifest returns CodemanifestConfig | None."""
        ret = inspect.signature(_parse_codemanifest).return_annotation
        assert ret == CodemanifestConfig | None


# --- Logic tests for _parse_codemanifest ---


class TestParseCodemanifestPositive:
    def test_parse_codemanifest_with_full_data(self):
        """Full codemanifest section with usages and annotations."""
        data = {
            "codemanifest": {
                "usages": {"lib": ".specs/lib.md", "api": ".specs/api.md"},
                "annotations": "Use lib for core logic",
            }
        }
        result = _parse_codemanifest(data)
        assert isinstance(result, CodemanifestConfig)
        assert result.usages == {"lib": ".specs/lib.md", "api": ".specs/api.md"}
        assert result.annotations == "Use lib for core logic"

    def test_parse_codemanifest_without_section(self):
        """No codemanifest section → returns None."""
        result = _parse_codemanifest({})
        assert result is None

    def test_parse_codemanifest_empty_section(self):
        """codemanifest: {} → CodemanifestConfig with defaults."""
        data = {"codemanifest": {}}
        result = _parse_codemanifest(data)
        assert isinstance(result, CodemanifestConfig)
        assert result.usages == {}
        assert result.annotations is None

    def test_parse_codemanifest_annotations_only(self):
        """codemanifest with annotations only, no usages."""
        data = {"codemanifest": {"annotations": "Some notes"}}
        result = _parse_codemanifest(data)
        assert result.usages == {}
        assert result.annotations == "Some notes"

    def test_parse_codemanifest_usages_only(self):
        """codemanifest with usages only, no annotations."""
        data = {"codemanifest": {"usages": {"lib": ".specs/lib.md"}}}
        result = _parse_codemanifest(data)
        assert result.usages == {"lib": ".specs/lib.md"}
        assert result.annotations is None

    def test_parse_codemanifest_null_section(self):
        """codemanifest: null → returns None."""
        data = {"codemanifest": None}
        result = _parse_codemanifest(data)
        assert result is None

    def test_parse_codemanifest_annotations_empty_string(self):
        """annotations: '' → empty string is valid."""
        data = {"codemanifest": {"annotations": ""}}
        result = _parse_codemanifest(data)
        assert result.annotations == ""

    def test_parse_codemanifest_annotations_multiline(self):
        """Multiline annotations and multiple usages."""
        data = {
            "codemanifest": {
                "usages": {
                    "lib": ".specs/lib.md",
                    "api": ".specs/api.md",
                    "core": ".specs/core.md",
                },
                "annotations": "Line 1\nLine 2\nLine 3",
            }
        }
        result = _parse_codemanifest(data)
        assert result.usages == {
            "lib": ".specs/lib.md",
            "api": ".specs/api.md",
            "core": ".specs/core.md",
        }
        assert result.annotations == "Line 1\nLine 2\nLine 3"


class TestParseCodemanifestNegative:
    def test_parse_codemanifest_usages_not_mapping(self):
        """usages: not-a-mapping → ValueError."""
        data = {"codemanifest": {"usages": "not-a-mapping"}}
        with pytest.raises(ValueError, match=r"codemanifest\.usages must be a mapping"):
            _parse_codemanifest(data)

    def test_parse_codemanifest_usages_null(self):
        """usages: null → ValueError."""
        data = {"codemanifest": {"usages": None}}
        with pytest.raises(ValueError, match=r"codemanifest\.usages must be a mapping"):
            _parse_codemanifest(data)

    def test_parse_codemanifest_usages_list(self):
        """usages: [item] → ValueError."""
        data = {"codemanifest": {"usages": ["a", "b"]}}
        with pytest.raises(ValueError, match=r"codemanifest\.usages must be a mapping"):
            _parse_codemanifest(data)

    def test_parse_codemanifest_usages_non_string_key(self):
        """usages: {123: path} → ValueError (non-string key)."""
        data = {"codemanifest": {"usages": {123: "path.md"}}}
        with pytest.raises(ValueError, match=r"codemanifest\.usages must have string keys and values"):
            _parse_codemanifest(data)

    def test_parse_codemanifest_usages_non_string_value(self):
        """usages: {lib: 123} → ValueError (non-string value)."""
        data = {"codemanifest": {"usages": {"lib": 123}}}
        with pytest.raises(ValueError, match=r"codemanifest\.usages must have string keys and values"):
            _parse_codemanifest(data)

    def test_parse_codemanifest_annotations_not_string(self):
        """annotations: 123 → ValueError."""
        data = {"codemanifest": {"annotations": 123}}
        with pytest.raises(ValueError, match=r"codemanifest\.annotations must be a string"):
            _parse_codemanifest(data)

    def test_parse_codemanifest_annotations_bool_raises(self):
        """annotations: true → ValueError."""
        data = {"codemanifest": {"annotations": True}}
        with pytest.raises(ValueError, match=r"codemanifest\.annotations must be a string"):
            _parse_codemanifest(data)

    def test_parse_codemanifest_scalar_string(self):
        """codemanifest: "string" → ValueError (not a mapping)."""
        data = {"codemanifest": "some-string"}
        with pytest.raises(ValueError, match=r"'codemanifest' must be a mapping"):
            _parse_codemanifest(data)

    def test_parse_codemanifest_scalar_int(self):
        """codemanifest: 42 → ValueError (not a mapping)."""
        data = {"codemanifest": 42}
        with pytest.raises(ValueError, match=r"'codemanifest' must be a mapping"):
            _parse_codemanifest(data)


# --- Integration tests: load_config with codemanifest ---


class TestLoadConfigCodemanifest:
    def test_load_config_with_codemanifest_section(self, goga_project):
        """.goga/config.yml with full codemanifest section."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest:
  usages:
    lib: .specs/lib.md
    api: .specs/api.md
  annotations: "Use lib for core logic"
""",
        )
        config = load_config()
        assert config.codemanifest is not None
        assert config.codemanifest.usages == {"lib": ".specs/lib.md", "api": ".specs/api.md"}
        assert config.codemanifest.annotations == "Use lib for core logic"

    def test_load_config_without_codemanifest_section(self, goga_project):
        """.goga/config.yml without codemanifest → codemanifest is None."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_config()
        assert config.codemanifest is None

    def test_load_config_codemanifest_empty_section(self, goga_project):
        """codemanifest: {} → defaults."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest: {}
""",
        )
        config = load_config()
        assert config.codemanifest is not None
        assert config.codemanifest.usages == {}
        assert config.codemanifest.annotations is None

    def test_load_config_codemanifest_annotations_only(self, goga_project):
        """codemanifest with annotations only."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest:
  annotations: "Some notes"
""",
        )
        config = load_config()
        assert config.codemanifest is not None
        assert config.codemanifest.usages == {}
        assert config.codemanifest.annotations == "Some notes"

    def test_load_config_codemanifest_usages_not_mapping(self, goga_project):
        """usages: not-a-mapping → ValueError."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest:
  usages: not-a-mapping
""",
        )
        with pytest.raises(ValueError, match=r"codemanifest\.usages must be a mapping"):
            load_config()

    def test_load_config_codemanifest_annotations_not_string(self, goga_project):
        """annotations: 123 → ValueError."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest:
  annotations: 123
""",
        )
        with pytest.raises(ValueError, match=r"codemanifest\.annotations must be a string"):
            load_config()

    def test_load_config_codemanifest_annotations_bool_raises(self, goga_project):
        """annotations: true → ValueError."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest:
  annotations: true
""",
        )
        with pytest.raises(ValueError, match=r"codemanifest\.annotations must be a string"):
            load_config()

    def test_load_config_codemanifest_usages_null(self, goga_project):
        """usages: null → ValueError."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest:
  usages:
""",
        )
        with pytest.raises(ValueError, match=r"codemanifest\.usages must be a mapping"):
            load_config()

    def test_load_config_codemanifest_annotations_empty_string(self, goga_project):
        """annotations: '' → empty string is valid."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest:
  annotations: ""
""",
        )
        config = load_config()
        assert config.codemanifest is not None
        assert config.codemanifest.annotations == ""

    def test_load_config_codemanifest_scalar_string_raises(self, goga_project):
        """codemanifest: "string" → ValueError (not a mapping)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest: string
""",
        )
        with pytest.raises(ValueError, match=r"'codemanifest' must be a mapping"):
            load_config()

    def test_load_config_codemanifest_scalar_bool_raises(self, goga_project):
        """codemanifest: true → ValueError (not a mapping)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest: true
""",
        )
        with pytest.raises(ValueError, match=r"'codemanifest' must be a mapping"):
            load_config()

    def test_load_config_codemanifest_usages_non_string_key_raises(self, goga_project):
        """usages: {123: path} → ValueError (non-string key)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest:
  usages:
    123: path.md
""",
        )
        with pytest.raises(ValueError, match=r"codemanifest\.usages must have string keys and values"):
            load_config()

    def test_load_config_codemanifest_usages_non_string_value_raises(self, goga_project):
        """usages: {lib: 123} → ValueError (non-string value)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest:
  usages:
    lib: 123
""",
        )
        with pytest.raises(ValueError, match=r"codemanifest\.usages must have string keys and values"):
            load_config()

    def test_load_config_codemanifest_annotations_multiline(self, goga_project):
        """Multiline annotations and multiple usages."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest:
  usages:
    lib: .specs/lib.md
    api: .specs/api.md
  annotations: |
    Line 1
    Line 2
    Line 3
""",
        )
        config = load_config()
        assert config.codemanifest is not None
        assert config.codemanifest.usages == {"lib": ".specs/lib.md", "api": ".specs/api.md"}
        assert config.codemanifest.annotations == "Line 1\nLine 2\nLine 3\n"

    def test_load_config_codemanifest_null_returns_none(self, goga_project):
        """codemanifest: null → config.codemanifest is None."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
codemanifest: null
""",
        )
        config = load_config()
        assert config.codemanifest is None


# --- Contract tests for Config.dockerfile + _parse_dockerfile ---


class TestConfigDockerfileContract:
    def test_config_has_dockerfile_field(self):
        """Config declares a `dockerfile` field."""
        field_names = {f.name for f in dataclasses.fields(Config)}
        assert "dockerfile" in field_names

    def test_config_dockerfile_field_positioned_after_image(self):
        """dockerfile is declared immediately after image (field order)."""
        field_names = [f.name for f in dataclasses.fields(Config)]
        assert field_names.index("dockerfile") == field_names.index("image") + 1

    def test_config_dockerfile_annotation_optional_str(self):
        """dockerfile field type is str | None."""
        dockerfile_field = {f.name: f for f in dataclasses.fields(Config)}["dockerfile"]
        assert dockerfile_field.type == str | None

    def test_load_config_still_callable(self):
        """load_config remains callable from goga.config."""
        assert callable(load_config)

    def test_parse_dockerfile_exists(self):
        """_parse_dockerfile is importable from goga.config.loader."""
        assert callable(_parse_dockerfile)

    def test_parse_dockerfile_signature(self):
        """_parse_dockerfile accepts a single dict parameter (parity with _parse_image)."""
        sig = inspect.signature(_parse_dockerfile)
        assert list(sig.parameters.keys()) == ["data"]

    def test_parse_dockerfile_return_annotation(self):
        """_parse_dockerfile returns str | None (parity with _parse_image)."""
        ret = inspect.signature(_parse_dockerfile).return_annotation
        assert ret == str | None


# --- Logic tests for _parse_dockerfile ---


class TestParseDockerfilePositive:
    def test_parse_dockerfile_with_string_value(self):
        """A string dockerfile value is returned as-is."""
        assert _parse_dockerfile({"dockerfile": "Dockerfile"}) == "Dockerfile"

    def test_parse_dockerfile_absent_returns_none(self):
        """No dockerfile key → None."""
        assert _parse_dockerfile({}) is None

    def test_parse_dockerfile_null_returns_none(self):
        """dockerfile: null → None."""
        assert _parse_dockerfile({"dockerfile": None}) is None

    def test_parse_dockerfile_empty_string_valid(self):
        """dockerfile: '' → empty string is a valid str."""
        assert _parse_dockerfile({"dockerfile": ""}) == ""


class TestParseDockerfileNegative:
    def test_parse_dockerfile_rejects_non_string(self):
        """A non-string dockerfile value raises ValueError."""
        with pytest.raises(ValueError, match="dockerfile must be a string"):
            _parse_dockerfile({"dockerfile": ["a", "b"]})

    def test_parse_dockerfile_rejects_int(self):
        """dockerfile: 123 → ValueError."""
        with pytest.raises(ValueError, match="dockerfile must be a string"):
            _parse_dockerfile({"dockerfile": 123})

    def test_parse_dockerfile_rejects_bool(self):
        """dockerfile: true → ValueError."""
        with pytest.raises(ValueError, match="dockerfile must be a string"):
            _parse_dockerfile({"dockerfile": True})

    def test_parse_dockerfile_rejects_dict(self):
        """dockerfile: mapping → ValueError."""
        with pytest.raises(ValueError, match="dockerfile must be a string"):
            _parse_dockerfile({"dockerfile": {"path": "Dockerfile"}})


# --- Integration tests: load_config with dockerfile ---


class TestLoadConfigDockerfile:
    def test_load_config_parses_dockerfile_field(self, goga_project):
        """.goga/config.yml with image + dockerfile → both parsed."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: img:tag
dockerfile: Dockerfile
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
""",
        )
        config = load_config()
        assert config.image == "img:tag"
        assert config.dockerfile == "Dockerfile"

    def test_load_config_dockerfile_defaults_none_when_absent(self, goga_project):
        """No dockerfile key → config.dockerfile is None."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_config()
        assert config.dockerfile is None

    def test_load_config_dockerfile_empty_string_valid(self, goga_project):
        """dockerfile: '' → config.dockerfile == '' (valid str)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: img:tag
dockerfile: ''
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
""",
        )
        config = load_config()
        assert config.dockerfile == ""

    def test_load_config_dockerfile_non_string_raises(self, goga_project):
        """dockerfile: 123 → ValueError."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: img:tag
dockerfile: 123
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match="dockerfile must be a string"):
            load_config()

    def test_load_config_dockerfile_without_image(self, goga_project):
        """dockerfile set with image absent → both None-able independently."""
        _write_goga_yml(
            goga_project,
            """\
language: python
dockerfile: Dockerfile
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
""",
        )
        config = load_config()
        assert config.image is None
        assert config.dockerfile == "Dockerfile"
