# tests/goga/config/test_loader.py — contract and logic tests for load_project_config

import dataclasses
import inspect
import re

import goga.config as goga_config_mod
import pytest
import yaml
from goga.config import (
    CodemanifestConfig,
    LintConfig,
    PipelineConfig,
    ProjectConfig,
    TaskExecutorConfig,
    TopicsConfig,
    load_project_config,
)
from goga.config.project.config import DepConfig
from goga.config.project.loader import (
    _parse_codemanifest,
    _parse_depcfg,
    _parse_dockerfile,
    _parse_lint,
    _parse_tools,
    _parse_topics,
    _parse_topics_field,
    _parse_usages,
    _validate_usages_root,
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
  prompts_dir: "/custom/prompts"
  agents_dir: "/custom/agents"
  codex_review: true
  review_executor:
    base_ref: origin/1.2.x
    patience: 3
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
        """load_project_config is importable from goga.config."""
        assert hasattr(goga_config_mod, "load_project_config")
        assert callable(goga_config_mod.load_project_config)

    def test_load_config_is_callable_no_args(self):
        """load_project_config accepts no arguments."""
        sig = inspect.signature(load_project_config)
        assert list(sig.parameters.keys()) == []

    def test_load_config_returns_config(self):
        """load_project_config returns a ProjectConfig instance (annotation)."""
        ret = inspect.signature(load_project_config).return_annotation
        assert ret is ProjectConfig

    def test_load_config_returns_config_instance(self, goga_project):
        """load_project_config actually returns a ProjectConfig instance at runtime."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        result = load_project_config()
        assert isinstance(result, ProjectConfig)


# --- Positive tests ---


class TestLoadConfigPositive:
    def test_load_config_minimal_valid_yaml(self, goga_project):
        """Minimal .goga/config.yml with language+image+pipeline+build.task_executor.agent."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_project_config()
        assert config.lang == "python"
        assert config.image == "qarium/foo:1.0"
        assert config.build.task_executor.agent == "claude"
        assert config.build.task_executor.env == {}
        assert config.commands == {}
        assert config.build.worktree is None

    def test_load_config_pipeline_defaults(self, goga_project):
        """pipeline.env defaults to empty when not specified."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_project_config()
        assert config.pipeline.agent == "claude"
        assert config.pipeline.env == {}

    def test_load_config_full_yaml(self, goga_project):
        """.goga/config.yml with ALL fields populated."""
        _write_goga_yml(goga_project, FULL_YAML)
        config = load_project_config()
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
        assert config.build.review_executor.base_ref == "origin/1.2.x"
        assert config.build.review_executor.patience == 3
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
        config = load_project_config()
        assert config.build.task_executor.agent == "custom:/path/to/script"
        assert config.build.task_executor.env == {"K": "v"}

    def test_load_config_happy_path(self, goga_project):
        """Happy path with language, env, worktree, commands."""
        _write_goga_yml(goga_project, HAPPY_YAML)
        config = load_project_config()
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
        config = load_project_config()
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
        config = load_project_config()
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
        config = load_project_config()
        assert config.pipeline.proxy == "http://corp:3128"
        assert config.pipeline.hosts == {"foo.local": "127.0.0.1", "bar.local": "10.0.0.2"}

    def test_load_config_pipeline_proxy_hosts_absent_defaults(self, goga_project):
        """Missing pipeline.proxy/hosts default to None and empty dict."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_project_config()
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
        config = load_project_config()
        assert config.build.proxy == "http://build-proxy:8080"
        assert config.build.hosts == {"svc.local": "192.168.1.1"}

    def test_load_config_build_proxy_hosts_absent_defaults(self, goga_project):
        """Missing build.proxy/hosts default to None and empty dict."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_project_config()
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
        config = load_project_config()
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
        config = load_project_config()
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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()


# --- Schema-break tests ---


class TestLoadConfigSchemaBreak:
    def test_load_config_minimal_valid_returns_config_with_image_and_pipeline(self, goga_project):
        """Minimal valid config exposes top-level image + pipeline + build.task_executor."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_project_config()
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
            load_project_config()

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
        config = load_project_config()
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
        config = load_project_config()
        assert config.image is None

    def test_load_config_pipeline_agent_empty_resolves_none(self, goga_project):
        """pipeline.agent empty string resolves to None (optional field)."""
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
        config = load_project_config()
        assert config.pipeline is not None
        assert config.pipeline.agent is None

    def test_load_config_pipeline_agent_missing_resolves_none(self, goga_project):
        """pipeline block without agent resolves agent to None (optional field)."""
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
        config = load_project_config()
        assert config.pipeline is not None
        assert config.pipeline.agent is None

    def test_load_config_pipeline_agent_bool_raises(self, goga_project):
        """pipeline.agent: true (bool, not string) → structural type error (ValueError)."""
        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: true
build:
  task_executor:
    agent: claude
""",
        )
        with pytest.raises(ValueError, match=r"pipeline\.agent must be a string"):
            load_project_config()

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
            load_project_config()


# --- Optional sections tests (pipeline/build absent → None) ---


class TestLoadConfigOptionalSections:
    def test_load_config_minimal_only_language(self, goga_project):
        """ProjectConfig with only language → all other sections None / empty."""
        _write_goga_yml(
            goga_project,
            """\
language: python
""",
        )
        config = load_project_config()
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
        config = load_project_config()
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
        config = load_project_config()
        assert config.build is None

    def test_load_config_empty_pipeline_mapping_parses_none_agent(self, goga_project):
        """pipeline: {} → parses to PipelineConfig with agent=None (agent optional)."""
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
        config = load_project_config()
        assert config.pipeline is not None
        assert config.pipeline.agent is None
        assert config.pipeline.env == {}

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
            load_project_config()


# --- Negative tests ---


class TestLoadConfigNegative:
    def test_load_config_file_not_found(self, goga_project):
        """No .goga/config.yml in directory."""
        with pytest.raises(FileNotFoundError, match=r"\.goga/config\.yml"):
            load_project_config()

    def test_load_config_empty_file(self, goga_project):
        """0-byte .goga/config.yml."""
        _write_goga_yml(goga_project, "")
        with pytest.raises(FileNotFoundError, match=r"\.goga/config\.yml"):
            load_project_config()

    def test_load_config_not_a_mapping(self, goga_project):
        """YAML list content."""
        _write_goga_yml(goga_project, "- item1\n- item2\n")
        with pytest.raises(ValueError, match="mapping"):
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
        config = load_project_config()
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
            load_project_config()

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
            load_project_config()

    def test_load_config_missing_agent_resolves_none(self, goga_project):
        """task_executor: {} (no agent key) → agent resolves to None (optional)."""
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
        config = load_project_config()
        assert config.build is not None
        assert config.build.task_executor.agent is None

    def test_load_config_empty_agent_resolves_none(self, goga_project):
        """agent: '' (empty string) → resolves to None (optional)."""
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
        config = load_project_config()
        assert config.build is not None
        assert config.build.task_executor.agent is None

    def test_load_config_whitespace_agent_resolves_none(self, goga_project):
        """agent: '   ' (whitespace-only string) → resolves to None (optional)."""
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
        config = load_project_config()
        assert config.build is not None
        assert config.build.task_executor.agent is None

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
            load_project_config()

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
            load_project_config()

    def test_load_config_agent_bool_raises(self, goga_project):
        """agent: true (bool, not string) → structural type error (ValueError)."""
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
        with pytest.raises(ValueError, match=r"build\.task_executor\.agent must be a string"):
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()


# --- Edge case tests ---


class TestLoadConfigEdgeCases:
    def test_load_config_commands_optional(self, goga_project):
        """.goga/config.yml without commands section."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_project_config()
        assert config.commands == {}

    def test_load_config_frozen_immutability(self, goga_project):
        """ProjectConfig objects are frozen — mutation raises FrozenInstanceError."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_project_config()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.lang = "go"

    def test_load_config_invalid_yaml_syntax(self, goga_project):
        """Bad YAML syntax."""
        _write_goga_yml(
            goga_project,
            "language: python\npipeline:\n  agent: claude\nbuild:\n  task_executor:\n    agent: [unclosed\n",
        )
        with pytest.raises(yaml.YAMLError):
            load_project_config()


# --- Contract tests for _parse_codemanifest ---


class TestParseCodemanifestContract:
    def test_parse_codemanifest_exists(self):
        """_parse_codemanifest is importable from goga.config.project.loader."""
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


# --- Integration tests: load_project_config with codemanifest ---


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
        config = load_project_config()
        assert config.codemanifest is not None
        assert config.codemanifest.usages == {"lib": ".specs/lib.md", "api": ".specs/api.md"}
        assert config.codemanifest.annotations == "Use lib for core logic"

    def test_load_config_without_codemanifest_section(self, goga_project):
        """.goga/config.yml without codemanifest → codemanifest is None."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_project_config()
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
        config = load_project_config()
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
        config = load_project_config()
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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
        config = load_project_config()
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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
            load_project_config()

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
        config = load_project_config()
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
        config = load_project_config()
        assert config.codemanifest is None


# --- Contract tests for ProjectConfig.dockerfile + _parse_dockerfile ---


class TestConfigDockerfileContract:
    def test_config_has_dockerfile_field(self):
        """ProjectConfig declares a `dockerfile` field."""
        field_names = {f.name for f in dataclasses.fields(ProjectConfig)}
        assert "dockerfile" in field_names

    def test_config_dockerfile_field_positioned_after_image(self):
        """dockerfile is declared immediately after image (field order)."""
        field_names = [f.name for f in dataclasses.fields(ProjectConfig)]
        assert field_names.index("dockerfile") == field_names.index("image") + 1

    def test_config_dockerfile_annotation_optional_str(self):
        """dockerfile field type is str | None."""
        dockerfile_field = {f.name: f for f in dataclasses.fields(ProjectConfig)}["dockerfile"]
        assert dockerfile_field.type == str | None

    def test_load_config_still_callable(self):
        """load_project_config remains callable from goga.config."""
        assert callable(load_project_config)

    def test_parse_dockerfile_exists(self):
        """_parse_dockerfile is importable from goga.config.project.loader."""
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


# --- Integration tests: load_project_config with dockerfile ---


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
        config = load_project_config()
        assert config.image == "img:tag"
        assert config.dockerfile == "Dockerfile"

    def test_load_config_dockerfile_defaults_none_when_absent(self, goga_project):
        """No dockerfile key → config.dockerfile is None."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_project_config()
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
        config = load_project_config()
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
            load_project_config()

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
        config = load_project_config()
        assert config.image is None
        assert config.dockerfile == "Dockerfile"


# --- Contract tests for _parse_tools ---


class TestParseToolsContract:
    def test_parse_tools_exists(self):
        """_parse_tools is importable from goga.config.project.loader."""
        assert callable(_parse_tools)

    def test_parse_tools_signature(self):
        """_parse_tools accepts a single dict parameter (parity with _parse_codemanifest)."""
        sig = inspect.signature(_parse_tools)
        params = list(sig.parameters.keys())
        assert params == ["data"]

    def test_parse_tools_return_annotation(self):
        """_parse_tools returns dict[str, str] | None."""
        ret = inspect.signature(_parse_tools).return_annotation
        assert ret == dict[str, str] | None


# --- Logic tests for _parse_tools ---


class TestParseToolsPositive:
    def test_parse_tools_absent_returns_none(self):
        """No tools key → None."""
        assert _parse_tools({}) is None

    def test_parse_tools_null_returns_none(self):
        """tools: null → None."""
        assert _parse_tools({"tools": None}) is None

    def test_parse_tools_empty_mapping_returns_empty_dict(self):
        """tools: {} → empty dict."""
        assert _parse_tools({"tools": {}}) == {}

    def test_parse_tools_stored_verbatim_no_semantic_validation(self):
        """Operator-prefixed, malformed numerics, and pre-release forms pass verbatim."""
        data = {
            "tools": {
                "valid": "1.0.x",
                "operator_prefixed": "==1.0",
                "bare_two_segment_concrete_pin": "1.0",
                "weird": "foo",
            }
        }
        result = _parse_tools(data)
        assert result == {
            "valid": "1.0.x",
            "operator_prefixed": "==1.0",
            "bare_two_segment_concrete_pin": "1.0",
            "weird": "foo",
        }

    def test_parse_tools_returns_plain_dict_copy(self):
        """Result is a plain dict copy — not the original mapping object."""
        original = {"afm": "1.0.x"}
        data = {"tools": original}
        result = _parse_tools(data)
        assert result == original
        assert result is not original
        assert type(result) is dict

    def test_parse_tools_preserves_insertion_order(self):
        """Insertion order of keys is preserved."""
        data = {"tools": {"go": "1.0.1", "afm": "1.0.x", "ralphex": "1.x"}}
        result = _parse_tools(data)
        assert list(result.keys()) == ["go", "afm", "ralphex"]


class TestParseToolsNegative:
    def test_parse_tools_non_mapping_int_raises(self):
        """tools: 5 → ValueError (not a mapping)."""
        with pytest.raises(ValueError, match=r"'tools' must be a mapping"):
            _parse_tools({"tools": 5})

    def test_parse_tools_non_mapping_list_raises(self):
        """tools: [a, b] → ValueError (not a mapping)."""
        with pytest.raises(ValueError, match=r"'tools' must be a mapping"):
            _parse_tools({"tools": ["a", "b"]})

    def test_parse_tools_non_mapping_string_raises(self):
        """tools: 'string' → ValueError (not a mapping)."""
        with pytest.raises(ValueError, match=r"'tools' must be a mapping"):
            _parse_tools({"tools": "string"})

    def test_parse_tools_null_value_raises(self):
        """tools: {viewer: null} → ValueError (non-string value)."""
        with pytest.raises(ValueError, match=r"'tools' must have string keys and values"):
            _parse_tools({"tools": {"viewer": None}})

    def test_parse_tools_non_string_value_int_raises(self):
        """tools: {viewer: 5} → ValueError (non-string value)."""
        with pytest.raises(ValueError, match=r"'tools' must have string keys and values"):
            _parse_tools({"tools": {"viewer": 5}})

    def test_parse_tools_non_string_value_bool_raises(self):
        """tools: {viewer: true} → ValueError (non-string value)."""
        with pytest.raises(ValueError, match=r"'tools' must have string keys and values"):
            _parse_tools({"tools": {"viewer": True}})

    def test_parse_tools_non_string_value_float_raises(self):
        """tools: {viewer: 1.0} (YAML parses 1.0 as a float) → ValueError.

        The most probable user mistake — writing the version unquoted — is
        rejected structurally by the loader and never reaches resolve_version.
        """
        with pytest.raises(ValueError, match=r"'tools' must have string keys and values"):
            _parse_tools({"tools": {"viewer": 1.0}})

    def test_parse_tools_non_string_key_raises(self):
        """tools: {123: 1.0.x} → ValueError (non-string key)."""
        with pytest.raises(ValueError, match=r"'tools' must have string keys and values"):
            _parse_tools({"tools": {123: "1.0.x"}})

    def test_parse_tools_mixed_null_and_valid_raises(self):
        """{afm: 1.0.x, viewer: null, ralphex: 1.x} → ValueError on viewer."""
        with pytest.raises(ValueError, match=r"'tools' must have string keys and values"):
            _parse_tools({"tools": {"afm": "1.0.x", "viewer": None, "ralphex": "1.x"}})


# --- Integration tests: load_project_config with tools ---


class TestLoadConfigTools:
    def test_load_config_tools_stored_verbatim(self, goga_project):
        """tools mapping with mixed valid/invalid forms — all pass verbatim (no semantic validation)."""
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
tools:
  valid: 1.0.x
  operator_prefixed: "==1.0"
  bare_two_segment_concrete_pin: "1.0"
  weird: foo
""",
        )
        config = load_project_config()
        assert config.tools == {
            "valid": "1.0.x",
            "operator_prefixed": "==1.0",
            "bare_two_segment_concrete_pin": "1.0",
            "weird": "foo",
        }

    def test_load_config_tools_absent_returns_none(self, goga_project):
        """YAML without tools → cfg.tools is None."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_project_config()
        assert config.tools is None

    def test_load_config_tools_null_returns_none(self, goga_project):
        """tools: null → cfg.tools is None."""
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
tools: null
""",
        )
        config = load_project_config()
        assert config.tools is None

    def test_load_config_tools_empty_mapping_returns_empty_dict(self, goga_project):
        """tools: {} → cfg.tools == {}."""
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
tools: {}
""",
        )
        config = load_project_config()
        assert config.tools == {}

    def test_load_config_tools_non_mapping_raises(self, goga_project):
        """tools: 5 → ValueError match 'tools.*mapping'."""
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
tools: 5
""",
        )
        with pytest.raises(ValueError, match=r"tools.*mapping"):
            load_project_config()

    def test_load_config_tools_null_value_raises(self, goga_project):
        """tools: {viewer:} (YAML-null individual) → ValueError match 'string'."""
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
tools:
  viewer:
""",
        )
        with pytest.raises(ValueError, match="string"):
            load_project_config()

    def test_load_config_tools_non_string_value_raises(self, goga_project):
        """tools: {viewer: 5} → ValueError (non-string value)."""
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
tools:
  viewer: 5
""",
        )
        with pytest.raises(ValueError, match="tools"):
            load_project_config()

    def test_load_config_tools_non_string_value_float_raises(self, goga_project):
        """tools: {viewer: 1.0} (YAML float) → ValueError.

        Writing the version unquoted is the most likely user mistake; the
        loader rejects it structurally before resolve_version ever sees it.
        """
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
tools:
  viewer: 1.0
""",
        )
        with pytest.raises(ValueError, match="string"):
            load_project_config()

    def test_load_config_tools_mixed_null_and_valid_raises(self, goga_project):
        """{afm: 1.0.x, viewer: null, ralphex: 1.x} → ValueError match 'string'."""
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
tools:
  afm: 1.0.x
  viewer: null
  ralphex: 1.x
""",
        )
        with pytest.raises(ValueError, match="string"):
            load_project_config()

    def test_load_config_backward_compatible_without_tools(self, goga_project):
        """Existing config without tools → cfg.tools is None, other fields unchanged."""
        _write_goga_yml(goga_project, HAPPY_YAML)
        config = load_project_config()
        assert config.tools is None
        # Other fields unchanged
        assert config.lang == "python"
        assert config.image == "qarium/foo:1.0"
        assert config.pipeline.agent == "claude"
        assert config.build.task_executor.agent == "claude"
        assert config.build.task_executor.env == {"KEY": "value"}
        assert config.build.worktree is True
        assert config.commands == {"foo": "bar"}

    def test_load_config_tools_alongside_codemanifest(self, goga_project):
        """tools + codemanifest both present — both parsed independently."""
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
  annotations: "notes"
tools:
  afm: 1.0.x
""",
        )
        config = load_project_config()
        assert config.tools == {"afm": "1.0.x"}
        assert config.codemanifest is not None
        assert config.codemanifest.annotations == "notes"


# --- Contract tests for _parse_usages ---


class TestParseUsagesContract:
    def test_parse_usages_exists(self):
        """_parse_usages is importable from goga.config.project.loader."""
        assert callable(_parse_usages)

    def test_parse_usages_signature(self):
        """_parse_usages accepts a single `raw` parameter (the parsed usages node)."""
        sig = inspect.signature(_parse_usages)
        params = list(sig.parameters.keys())
        assert params == ["raw"]

    def test_parse_usages_return_annotation(self):
        """_parse_usages returns dict[str, dict[str, DepConfig]] | None."""
        ret = inspect.signature(_parse_usages).return_annotation
        assert ret == dict[str, dict[str, DepConfig]] | None


# --- Logic tests for _parse_usages (direct) ---


class TestParseUsagesLogic:
    def test_parse_usages_none_returns_none(self):
        """Absent (None passed in) → None."""
        assert _parse_usages(None) is None

    def test_parse_usages_empty_mapping_returns_empty_dict(self):
        """Present-but-empty → empty dict."""
        assert _parse_usages({}) == {}

    def test_parse_usages_builds_depcfg_dict_preserving_order(self):
        """group→dep→DepConfig structure built; ref absent → None; order preserved."""
        result = _parse_usages(
            {
                "libs": {
                    "click": {"git": "https://x/click.git", "ref": "main"},
                    "another": {"git": "https://x/another.git"},
                }
            }
        )
        assert isinstance(result, dict)
        assert list(result.keys()) == ["libs"]
        assert list(result["libs"].keys()) == ["click", "another"]
        assert isinstance(result["libs"]["click"], DepConfig)
        assert result["libs"]["click"].git == "https://x/click.git"
        assert result["libs"]["click"].ref == "main"
        assert result["libs"]["another"].git == "https://x/another.git"
        assert result["libs"]["another"].ref is None

    def test_parse_usages_strips_git_whitespace(self):
        """git is stripped before constructing DepConfig."""
        result = _parse_usages({"libs": {"click": {"git": "  https://x/click.git  "}}})
        assert result["libs"]["click"].git == "https://x/click.git"

    def test_parse_usages_non_mapping_raises_value_error(self):
        """raw scalar (int) → ValueError."""
        with pytest.raises(ValueError, match=r"'usages' must be a mapping"):
            _parse_usages(5)

    def test_parse_usages_non_mapping_list_raises_value_error(self):
        """raw list → ValueError."""
        with pytest.raises(ValueError, match=r"'usages' must be a mapping"):
            _parse_usages(["a", "b"])

    def test_parse_usages_group_non_mapping_raises_value_error(self):
        """group value not a mapping → ValueError."""
        with pytest.raises(ValueError, match=r"usages\.libs must be a mapping"):
            _parse_usages({"libs": 5})

    def test_parse_usages_dep_non_mapping_raises_value_error(self):
        """dep value not a mapping → ValueError."""
        with pytest.raises(ValueError, match=r"usages\.libs\.click must be a mapping"):
            _parse_usages({"libs": {"click": 5}})

    def test_parse_usages_dep_git_missing_raises_keyerror(self):
        """dep without git → KeyError."""
        with pytest.raises(KeyError, match=r"usages\.libs\.click\.git is required"):
            _parse_usages({"libs": {"click": {"ref": "main"}}})

    def test_parse_usages_dep_git_null_raises_keyerror(self):
        """dep with git: null → KeyError (treated as missing)."""
        with pytest.raises(KeyError, match=r"usages\.libs\.click\.git is required"):
            _parse_usages({"libs": {"click": {"git": None}}})

    @pytest.mark.parametrize("bad_git", ["", "   ", 5, True, 1.0, []])
    def test_parse_usages_dep_git_invalid_raises_valueerror(self, bad_git):
        """git empty / non-string → ValueError."""
        with pytest.raises(ValueError, match=r"usages\.libs\.click\.git must be a non-empty string"):
            _parse_usages({"libs": {"click": {"git": bad_git}}})

    def test_parse_usages_dep_ref_non_str_raises_value_error(self):
        """ref present but non-string → ValueError."""
        with pytest.raises(ValueError, match=r"usages\.libs\.click\.ref must be a string"):
            _parse_usages({"libs": {"click": {"git": "https://x/click.git", "ref": 5}}})

    def test_parse_usages_dep_ref_null_treated_as_none(self):
        """ref: null → None (clone default branch)."""
        result = _parse_usages({"libs": {"click": {"git": "https://x/click.git", "ref": None}}})
        assert result["libs"]["click"].ref is None

    def test_parse_usages_non_string_group_key_raises_value_error(self):
        """Non-string group name (int key) → ValueError."""
        with pytest.raises(ValueError, match=r"'usages' must have string group names"):
            _parse_usages({123: {"click": {"git": "https://x/click.git"}}})

    def test_parse_usages_non_string_dep_key_raises_value_error(self):
        """Non-string dep name (int key) → ValueError."""
        with pytest.raises(ValueError, match=r"usages\.libs must have string dep names"):
            _parse_usages({"libs": {123: {"git": "https://x/click.git"}}})

    @pytest.mark.parametrize("bad_group", ["..", ".", "", "a/b", "a\\b"])
    def test_parse_usages_unsafe_group_segment_raises_value_error(self, bad_group):
        """group key that could escape the target root (traversal/separator/empty) → ValueError."""
        with pytest.raises(ValueError, match=r"'usages' group name must be a plain name"):
            _parse_usages({bad_group: {"click": {"git": "https://x/click.git"}}})

    @pytest.mark.parametrize("bad_dep", ["..", ".", "", "a/b", "a\\b"])
    def test_parse_usages_unsafe_dep_segment_raises_value_error(self, bad_dep):
        """dep key that could escape the target root (traversal/separator/empty) → ValueError."""
        with pytest.raises(ValueError, match=r"usages\.libs dep name must be a plain name"):
            _parse_usages({"libs": {bad_dep: {"git": "https://x/click.git"}}})

    def test_parse_usages_dep_ref_empty_raises_value_error(self):
        """ref: '' → ValueError at load time (not a cryptic ``git checkout ""`` failure)."""
        with pytest.raises(ValueError, match=r"usages\.libs\.click\.ref must be a non-empty string"):
            _parse_usages({"libs": {"click": {"git": "https://x/click.git", "ref": ""}}})

    def test_parse_usages_dep_ref_whitespace_only_raises_value_error(self):
        """ref: '   ' → ValueError (stripped, then empty)."""
        with pytest.raises(ValueError, match=r"usages\.libs\.click\.ref must be a non-empty string"):
            _parse_usages({"libs": {"click": {"git": "https://x/click.git", "ref": "   "}}})

    def test_parse_usages_dep_ref_whitespace_stripped(self):
        """ref with surrounding whitespace is stripped (mirrors git handling)."""
        result = _parse_usages({"libs": {"click": {"git": "https://x/click.git", "ref": "  main  "}}})
        assert result["libs"]["click"].ref == "main"


# --- Integration tests: load_project_config with usages ---


class TestLoadConfigUsages:
    def test_load_usages_absent_returns_none(self, goga_project):
        """Config without a usages section → config.usages is None."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_project_config()
        assert config.usages is None

    def test_load_usages_yaml_null_returns_none(self, goga_project):
        """usages: (YAML-null) → config.usages is None."""
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
usages:
""",
        )
        config = load_project_config()
        assert config.usages is None

    def test_load_usages_present_but_empty_returns_empty_dict(self, goga_project):
        """usages: {} → config.usages == {} (present-but-empty, distinct from None)."""
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
usages: {}
""",
        )
        config = load_project_config()
        assert config.usages == {}

    def test_load_usages_present_builds_depcfg_dict(self, goga_project):
        """usages.libs.click (git+ref) and usages.libs.another (git only) → DepConfig dict."""
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
usages:
  libs:
    click:
      git: https://x/click.git
      ref: main
    another:
      git: https://x/another.git
""",
        )
        config = load_project_config()
        assert config.usages is not None
        assert list(config.usages.keys()) == ["libs"]
        assert list(config.usages["libs"].keys()) == ["click", "another"]
        assert isinstance(config.usages["libs"]["click"], DepConfig)
        assert config.usages["libs"]["click"].git == "https://x/click.git"
        assert config.usages["libs"]["click"].ref == "main"
        assert config.usages["libs"]["another"].git == "https://x/another.git"
        assert config.usages["libs"]["another"].ref is None

    def test_load_usages_multiple_groups_preserve_structure(self, goga_project):
        """Multiple groups → dict structure preserved with insertion order."""
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
usages:
  libs:
    click:
      git: https://x/click.git
  tools:
    afm:
      git: https://x/afm.git
      ref: v1.0.0
""",
        )
        config = load_project_config()
        assert list(config.usages.keys()) == ["libs", "tools"]
        assert config.usages["tools"]["afm"].ref == "v1.0.0"

    def test_load_usages_non_mapping_raises_value_error(self, goga_project):
        """usages: 5 → ValueError."""
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
usages: 5
""",
        )
        with pytest.raises(ValueError, match=r"'usages' must be a mapping"):
            load_project_config()

    def test_load_usages_group_non_mapping_raises_value_error(self, goga_project):
        """usages.libs: 5 → ValueError."""
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
usages:
  libs: 5
""",
        )
        with pytest.raises(ValueError, match=r"usages\.libs must be a mapping"):
            load_project_config()

    def test_load_usages_dep_non_mapping_raises_value_error(self, goga_project):
        """usages.libs.click: 5 → ValueError."""
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
usages:
  libs:
    click: 5
""",
        )
        with pytest.raises(ValueError, match=r"usages\.libs\.click must be a mapping"):
            load_project_config()

    def test_load_usages_traversal_group_rejected(self, goga_project):
        """usages group '..' (path traversal) → ValueError at load time (security)."""
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
usages:
  "..":
    victim:
      git: https://x/victim.git
""",
        )
        with pytest.raises(ValueError, match=r"'usages' group name must be a plain name"):
            load_project_config()

    def test_load_usages_dep_git_missing_raises_keyerror(self, goga_project):
        """dep without git → KeyError."""
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
usages:
  libs:
    click:
      ref: main
""",
        )
        with pytest.raises(KeyError, match=r"usages\.libs\.click\.git is required"):
            load_project_config()

    @pytest.mark.parametrize("yaml_value", ['""', "5"])
    def test_load_usages_dep_git_invalid_raises_valueerror(self, goga_project, yaml_value):
        """git: "" and git: 5 → ValueError."""
        _write_goga_yml(
            goga_project,
            f"""\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
usages:
  libs:
    click:
      git: {yaml_value}
""",
        )
        with pytest.raises(ValueError, match=r"usages\.libs\.click\.git must be a non-empty string"):
            load_project_config()

    def test_load_usages_dep_ref_non_str_raises_value_error(self, goga_project):
        """git valid, ref: 5 → ValueError."""
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
usages:
  libs:
    click:
      git: https://x/click.git
      ref: 5
""",
        )
        with pytest.raises(ValueError, match=r"usages\.libs\.click\.ref must be a string"):
            load_project_config()

    def test_load_usages_non_string_group_key_raises_value_error(self, goga_project):
        """Non-string group name (numeric key) → ValueError at load time."""
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
usages:
  123:
    click:
      git: https://x/click.git
""",
        )
        with pytest.raises(ValueError, match=r"'usages' must have string group names"):
            load_project_config()

    def test_load_usages_non_string_dep_key_raises_value_error(self, goga_project):
        """Non-string dep name (numeric key) → ValueError at load time."""
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
usages:
  libs:
    123:
      git: https://x/click.git
""",
        )
        with pytest.raises(ValueError, match=r"usages\.libs must have string dep names"):
            load_project_config()

    def test_load_usages_alongside_tools(self, goga_project):
        """usages + tools both present — both parsed independently."""
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
tools:
  afm: 1.0.x
usages:
  libs:
    click:
      git: https://x/click.git
""",
        )
        config = load_project_config()
        assert config.tools == {"afm": "1.0.x"}
        assert config.usages is not None
        assert config.usages["libs"]["click"].git == "https://x/click.git"

    def test_load_usages_backward_compatible_without_usages(self, goga_project):
        """Existing config without usages → cfg.usages is None, other fields unchanged."""
        _write_goga_yml(goga_project, HAPPY_YAML)
        config = load_project_config()
        assert config.usages is None
        assert config.lang == "python"
        assert config.image == "qarium/foo:1.0"
        assert config.pipeline.agent == "claude"
        assert config.build.task_executor.agent == "claude"
        assert config.build.task_executor.env == {"KEY": "value"}
        assert config.build.worktree is True
        assert config.commands == {"foo": "bar"}


# --- Contract + logic tests for DepConfig.root ---


class TestDepConfigRootContract:
    def test_depcfg_root_param_in_signature_after_ref(self):
        """DepConfig declares `root` after `ref`, in (git, ref, root) order."""
        params = list(inspect.signature(DepConfig).parameters)
        assert params == ["git", "ref", "root"]

    def test_depcfg_root_default_is_none(self):
        """`root` defaults to None (explicit absence — walk from clone root)."""
        assert inspect.signature(DepConfig).parameters["root"].default is None

    def test_depcfg_root_explicit_value_and_ref_unset(self):
        """DepConfig(git=..., root="docs").root == "docs" and .ref is None."""
        dep = DepConfig(git="u", root="docs")
        assert dep.root == "docs"
        assert dep.ref is None

    def test_depcfg_back_compat_without_root(self):
        """DepConfig(git=..., ref="m") remains valid and .root is None."""
        dep = DepConfig(git="u", ref="m")
        assert dep.root is None
        assert dep.ref == "m"

    def test_depcfg_frozen_root_immutable(self):
        """DepConfig is frozen — assigning d.root raises FrozenInstanceError."""
        dep = DepConfig(git="u", root="docs")
        with pytest.raises(dataclasses.FrozenInstanceError):
            dep.root = "other"


class TestDepConfigRootLogic:
    def test_depcfg_root_defaults_none_when_not_provided(self):
        """Default value of `root` is None."""
        assert DepConfig(git="u").root is None

    def test_depcfg_root_none_explicit(self):
        """Explicit root=None is accepted and stored verbatim."""
        assert DepConfig(git="u", root=None).root is None

    def test_depcfg_root_explicit_value_stored_verbatim(self):
        """A non-None root is stored verbatim (no normalization here)."""
        assert DepConfig(git="u", root="docs/sub").root == "docs/sub"

    def test_depcfg_root_kw_only(self):
        """root is kw_only — positional construction beyond git/ref is rejected."""
        with pytest.raises(TypeError):
            DepConfig("u", "m", "docs")  # type: ignore[misc]

    def test_depcfg_back_compat_existing_call_sites(self):
        """Existing DepConfig(git=..., ref=...) / DepConfig(git=...) forms stay valid."""
        assert DepConfig(git="u", ref="m").root is None
        assert DepConfig(git="u").root is None

    def test_depcfg_root_frozen_independent_of_other_fields(self):
        """Mutating root raises (frozen dataclass) regardless of other fields."""
        dep = DepConfig(git="u", ref="m", root="docs")
        with pytest.raises(dataclasses.FrozenInstanceError):
            dep.root = None


# --- Contract tests for _validate_usages_root ---


class TestValidateUsagesRootContract:
    def test_validate_usages_root_exists(self):
        """_validate_usages_root is importable from goga.config.project.loader."""
        assert callable(_validate_usages_root)

    def test_validate_usages_root_signature(self):
        """_validate_usages_root accepts a single `root` str parameter."""
        sig = inspect.signature(_validate_usages_root)
        params = list(sig.parameters.keys())
        assert params == ["root"]

    def test_validate_usages_root_return_annotation(self):
        """_validate_usages_root returns None."""
        ret = inspect.signature(_validate_usages_root).return_annotation
        assert ret is None


# --- Logic tests for _validate_usages_root ---


class TestValidateUsagesRootLogic:
    @pytest.mark.parametrize("root", ["docs/sub", "folder"])
    def test_validate_usages_root_valid_does_not_raise(self, root):
        """A valid relative (possibly multi-segment) root passes structural validation."""
        _validate_usages_root(root)  # no exception raised

    @pytest.mark.parametrize("root", ["..", "../x", "a/../b", "x/.."])
    def test_validate_usages_root_traversal_raises(self, root):
        """A root with a '..' segment (path escape) raises ValueError."""
        with pytest.raises(ValueError, match=r"\.\."):
            _validate_usages_root(root)

    @pytest.mark.parametrize("root", ["/etc", "/abs/path", "//host/share", "//host"])
    def test_validate_usages_root_absolute_raises(self, root):
        """An absolute root (leading '/' or UNC '//host/share') raises ValueError."""
        with pytest.raises(ValueError, match=r"relative path|absolute"):
            _validate_usages_root(root)


# --- Logic tests for _parse_depcfg root branch ---


class TestParseDepcfgRoot:
    """Direct _parse_depcfg exercise of the `root` field parsing/normalization.

    These isolate the critical divergence from `ref`: an empty/separator-only
    `root` normalizes to None (NOT a ValueError), whereas an empty `ref` raises.
    """

    def _depcfg(self, dep_data):
        return _parse_depcfg("libs", "click", dep_data)

    def test_parse_depcfg_root_absent_is_none(self):
        """No root key → .root is None."""
        dep = self._depcfg({"git": "https://x/click.git"})
        assert dep.root is None

    def test_parse_depcfg_root_valid_multi_segment(self):
        """A valid multi-segment root is stored in canonical form."""
        dep = self._depcfg({"git": "https://x/click.git", "root": "docs/sub"})
        assert dep.root == "docs/sub"

    @pytest.mark.parametrize("root", ["", "   ", "/", "  /  "])
    def test_parse_depcfg_root_empty_or_separator_normalized_to_none(self, root):
        """Empty/whitespace/separator-only root → None (NOT an error; diverges from ref)."""
        dep = self._depcfg({"git": "https://x/click.git", "root": root})
        assert dep.root is None

    def test_parse_depcfg_root_trailing_separator_normalized(self):
        """A trailing separator is insignificant — 'folder/' → 'folder'."""
        dep = self._depcfg({"git": "https://x/click.git", "root": "folder/"})
        assert dep.root == "folder"

    def test_parse_depcfg_root_non_string_raises(self):
        """root: 123 (non-string) → ValueError."""
        with pytest.raises(ValueError, match=r"root must be a string"):
            self._depcfg({"git": "https://x/click.git", "root": 123})

    @pytest.mark.parametrize("root", ["..", "../x", "a/../b", "x/.."])
    def test_parse_depcfg_root_traversal_raises(self, root):
        """A traversal root raises ValueError (path escape)."""
        with pytest.raises(ValueError, match=r"\.\."):
            self._depcfg({"git": "https://x/click.git", "root": root})

    @pytest.mark.parametrize("root", ["/etc", "//host/share"])
    def test_parse_depcfg_root_absolute_raises(self, root):
        """An absolute root raises ValueError."""
        with pytest.raises(ValueError, match=r"relative path|absolute"):
            self._depcfg({"git": "https://x/click.git", "root": root})

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("docs\\sub", "docs/sub"), ("folder\\deep\\path", "folder/deep/path")],
    )
    def test_parse_depcfg_root_backslash_normalized_to_forward_slash(self, raw, expected):
        """A Windows-style backslash root is normalized to forward slashes (canonical form)."""
        dep = self._depcfg({"git": "https://x/click.git", "root": raw})
        assert dep.root == expected

    @pytest.mark.parametrize("root", ["..\\x", "a\\..\\b", "x\\.."])
    def test_parse_depcfg_root_backslash_traversal_raises(self, root):
        """A backslash traversal root (``..\\\\x``) raises — only caught via the backslash normalization.

        Without the ``replace('\\\\', '/')`` step this would slip past the ``..``
        segment check, so the normalization is load-bearing for safety.
        """
        with pytest.raises(ValueError, match=r"\.\."):
            self._depcfg({"git": "https://x/click.git", "root": root})

    def test_parse_depcfg_root_empty_does_not_raise_unlike_ref(self):
        """root: '' → None, while ref: '' → ValueError (the deliberate divergence)."""
        assert self._depcfg({"git": "https://x/click.git", "root": ""}).root is None
        with pytest.raises(ValueError, match=r"ref must be a non-empty string"):
            self._depcfg({"git": "https://x/click.git", "ref": ""})


# --- Integration tests: _parse_usages / load_project_config with root ---


class TestLoadUsagesRoot:
    def test_parse_usages_root_carried_into_depcfg(self):
        """A usages dep declaring root builds a DepConfig carrying .root (direct parse)."""
        result = _parse_usages({"libs": {"click": {"git": "https://x/c.git", "root": "docs/sub"}}})
        assert result["libs"]["click"].root == "docs/sub"

    def test_parse_usages_root_absent_defaults_none(self):
        """A usages dep without root → .root is None (direct parse)."""
        result = _parse_usages({"libs": {"click": {"git": "https://x/c.git"}}})
        assert result["libs"]["click"].root is None

    def test_parse_usages_root_empty_normalized_to_none(self):
        """A usages dep with root: '' → .root is None (direct parse; not an error)."""
        result = _parse_usages({"libs": {"click": {"git": "https://x/c.git", "root": ""}}})
        assert result["libs"]["click"].root is None

    def test_load_usages_with_root_end_to_end(self, goga_project):
        """A usages dep declaring root: docs is parsed end-to-end into DepConfig.root."""
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
usages:
  libs:
    click:
      git: https://x/click.git
      root: docs
""",
        )
        config = load_project_config()
        assert config.usages is not None
        assert config.usages["libs"]["click"].root == "docs"

    def test_load_usages_root_empty_normalized_to_none(self, goga_project):
        """root: '' (empty) normalizes to None at the config boundary (not an error)."""
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
usages:
  libs:
    click:
      git: https://x/click.git
      root: ''
""",
        )
        config = load_project_config()
        assert config.usages is not None
        assert config.usages["libs"]["click"].root is None

    def test_load_usages_root_multi_segment_end_to_end(self, goga_project):
        """A multi-segment root: docs/sub is parsed verbatim end-to-end."""
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
usages:
  libs:
    click:
      git: https://x/click.git
      root: docs/sub
""",
        )
        config = load_project_config()
        assert config.usages is not None
        assert config.usages["libs"]["click"].root == "docs/sub"

    @pytest.mark.parametrize(
        ("root_yaml", "match"),
        [
            ("..", r"\.\."),
            ("/etc", r"relative path|absolute"),
            ("5", r"root must be a string"),
        ],
    )
    def test_load_usages_invalid_root_raises_value_error(self, goga_project, root_yaml, match):
        """An invalid root (traversal / absolute / non-string) fails end-to-end at load time.

        Mirrors the existing ``ref`` error-path pattern (e.g. non-string ``ref``
        raises through ``load_project_config``), which ``root`` previously lacked.
        """
        _write_goga_yml(
            goga_project,
            f"""\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
usages:
  libs:
    click:
      git: https://x/click.git
      root: {root_yaml}
""",
        )
        with pytest.raises(ValueError, match=match):
            load_project_config()


# --- Contract tests for _parse_lint ---


class TestParseLintContract:
    def test_parse_lint_exists(self):
        """_parse_lint is importable from goga.config.project.loader."""
        assert callable(_parse_lint)

    def test_parse_lint_signature(self):
        """_parse_lint accepts a single dict parameter (parity with _parse_codemanifest)."""
        sig = inspect.signature(_parse_lint)
        params = list(sig.parameters.keys())
        assert params == ["data"]

    def test_parse_lint_return_annotation(self):
        """_parse_lint returns LintConfig | None."""
        ret = inspect.signature(_parse_lint).return_annotation
        assert ret == LintConfig | None

    def test_projectconfig_has_lint_field(self):
        """ProjectConfig declares a `lint` field."""
        field_names = {f.name for f in dataclasses.fields(ProjectConfig)}
        assert "lint" in field_names

    def test_projectconfig_lint_is_last_field(self):
        """lint is the last field before the trailing topics (backward-compatible append)."""
        field_names = [f.name for f in dataclasses.fields(ProjectConfig)]
        assert field_names[-2] == "lint"
        assert field_names[-1] == "topics"

    def test_projectconfig_lint_annotation_optional_lintconfig(self):
        """lint field type is LintConfig | None."""
        lint_field = {f.name: f for f in dataclasses.fields(ProjectConfig)}["lint"]
        assert lint_field.type == LintConfig | None

    def test_projectconfig_lint_defaults_none(self):
        """lint defaults to None (backward compatible — section absent)."""
        assert {f.name: f for f in dataclasses.fields(ProjectConfig)}["lint"].default is None


# --- Logic tests for _parse_lint (direct) ---


class TestParseLintPositive:
    def test_parse_lint_without_section_returns_none(self):
        """No lint section → returns None."""
        assert _parse_lint({"language": "python"}) is None

    def test_parse_lint_null_section_returns_none(self):
        """lint: null → returns None."""
        assert _parse_lint({"lint": None}) is None

    def test_parse_lint_builds_lintconfig_with_ignore(self):
        """lint.ignore list is stored verbatim (incl. trailing slash)."""
        result = _parse_lint({"lint": {"ignore": [".venv/", "build/dist"]}})
        assert isinstance(result, LintConfig)
        assert result.ignore == [".venv/", "build/dist"]

    def test_parse_lint_ignore_absent_defaults_empty(self):
        """lint: {} (no ignore key) → LintConfig(ignore=[])."""
        result = _parse_lint({"lint": {}})
        assert isinstance(result, LintConfig)
        assert result.ignore == []

    def test_parse_lint_ignore_null_defaults_empty(self):
        """lint: { ignore: null } → LintConfig(ignore=[])."""
        result = _parse_lint({"lint": {"ignore": None}})
        assert isinstance(result, LintConfig)
        assert result.ignore == []

    def test_parse_lint_empty_ignore_section(self):
        """lint: { ignore: [] } → LintConfig(ignore=[])."""
        result = _parse_lint({"lint": {"ignore": []}})
        assert isinstance(result, LintConfig)
        assert result.ignore == []

    def test_parse_lint_stores_verbatim_no_normalization(self):
        """Trailing slash and glob characters are preserved verbatim (no normalization)."""
        result = _parse_lint({"lint": {"ignore": [".venv/", "*"]}})
        assert result.ignore == [".venv/", "*"]

    def test_parse_lint_returns_plain_list_copy(self):
        """The returned ignore list is a copy — not the original list object."""
        original = [".venv/"]
        result = _parse_lint({"lint": {"ignore": original}})
        assert result.ignore == original
        assert result.ignore is not original


class TestParseLintNegative:
    @pytest.mark.parametrize("bad_section", ["not-a-mapping", 5, ["a", "b"]])
    def test_parse_lint_rejects_non_mapping_section(self, bad_section):
        """lint section that is not a mapping (str/int/list) → ValueError."""
        with pytest.raises(ValueError, match=r"'lint' must be a mapping"):
            _parse_lint({"lint": bad_section})

    def test_parse_lint_rejects_non_list_ignore(self):
        """lint: { ignore: not-a-list } → ValueError."""
        with pytest.raises(ValueError, match=r"lint\.ignore must be a list"):
            _parse_lint({"lint": {"ignore": "not-a-list"}})

    @pytest.mark.parametrize("bad_element", [5, True])
    def test_parse_lint_rejects_non_string_element(self, bad_element):
        """lint.ignore element that is not a string (int/bool) → ValueError."""
        with pytest.raises(ValueError, match=r"only strings"):
            _parse_lint({"lint": {"ignore": [bad_element]}})


# --- Integration tests: load_project_config with lint ---


class TestLoadConfigLint:
    def test_load_config_returns_lint_accessor(self, goga_project):
        """Minimal valid config exposes the cfg.lint accessor — initially None."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_project_config()
        assert config.lint is None

    def test_parse_lint_returns_none_when_section_absent(self, goga_project):
        """Config with only language → cfg.lint is None."""
        _write_goga_yml(goga_project, "language: python\n")
        config = load_project_config()
        assert config.lint is None

    def test_parse_lint_builds_lintconfig_with_ignore(self, goga_project):
        """lint.ignore list is parsed verbatim into cfg.lint.ignore (incl. trailing slash)."""
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
lint:
  ignore:
    - .venv/
    - build/dist
""",
        )
        config = load_project_config()
        assert config.lint is not None
        assert isinstance(config.lint, LintConfig)
        assert config.lint.ignore == [".venv/", "build/dist"]

    def test_parse_lint_empty_ignore_section(self, goga_project):
        """lint: { ignore: [] } → cfg.lint is present with ignore == []."""
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
lint:
  ignore: []
""",
        )
        config = load_project_config()
        assert config.lint is not None
        assert config.lint.ignore == []

    def test_parse_lint_rejects_non_mapping_section(self, goga_project):
        """lint: not-a-mapping → ValueError match 'lint.*mapping'."""
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
lint: not-a-mapping
""",
        )
        with pytest.raises(ValueError, match=r"lint.*mapping"):
            load_project_config()

    def test_parse_lint_rejects_non_list_ignore(self, goga_project):
        """lint: { ignore: not-a-list } → ValueError match 'lint.ignore.*list'."""
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
lint:
  ignore: not-a-list
""",
        )
        with pytest.raises(ValueError, match=r"lint\.ignore.*list"):
            load_project_config()

    def test_parse_lint_rejects_non_string_element(self, goga_project):
        """lint: { ignore: ['.venv/', 5] } → ValueError match 'only strings'."""
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
lint:
  ignore:
    - .venv/
    - 5
""",
        )
        with pytest.raises(ValueError, match=r"only strings"):
            load_project_config()

    def test_parse_lint_null_section_returns_none(self, goga_project):
        """lint: null → cfg.lint is None."""
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
lint: null
""",
        )
        config = load_project_config()
        assert config.lint is None

    def test_parse_lint_backward_compatible_without_section(self, goga_project):
        """Existing config without lint → cfg.lint is None, other fields unchanged."""
        _write_goga_yml(goga_project, HAPPY_YAML)
        config = load_project_config()
        assert config.lint is None
        assert config.lang == "python"
        assert config.image == "qarium/foo:1.0"
        assert config.pipeline.agent == "claude"
        assert config.build.task_executor.agent == "claude"
        assert config.build.task_executor.env == {"KEY": "value"}
        assert config.build.worktree is True
        assert config.commands == {"foo": "bar"}


# --- Contract tests for ReviewExecutorConfig + build.review_executor (step 6.5) ---


class TestReviewExecutorConfigContract:
    def test_review_executor_config_importable_from_project_cell(self):
        """ReviewExecutorConfig is importable from goga.config.project and in __all__."""
        import goga.config.project as project_mod
        from goga.config.project.config import ReviewExecutorConfig

        assert hasattr(project_mod, "ReviewExecutorConfig")
        assert "ReviewExecutorConfig" in project_mod.__all__
        assert project_mod.ReviewExecutorConfig is ReviewExecutorConfig

    def test_review_executor_config_is_frozen_kw_only_dataclass(self):
        """ReviewExecutorConfig is a frozen kw_only dataclass with six fields."""
        from goga.config.project.config import ReviewExecutorConfig

        assert dataclasses.is_dataclass(ReviewExecutorConfig)
        params = {f.name: f for f in dataclasses.fields(ReviewExecutorConfig)}
        assert set(params) == {"skip", "agent", "roles", "env", "base_ref", "patience"}
        assert params["skip"].default is None
        assert params["agent"].default is None
        assert params["roles"].default is None
        assert params["env"].default is dataclasses.MISSING
        assert params["env"].default_factory is dict
        assert params["base_ref"].default is None
        assert params["patience"].default is None

    def test_review_executor_config_reexport_from_facade_alive(self):
        """goga.config re-exports the same class object as the project cell."""
        import goga.config as facade
        from goga.config.project.config import ReviewExecutorConfig

        assert facade.ReviewExecutorConfig is ReviewExecutorConfig

    def test_build_config_accepts_review_executor_kwarg(self):
        """BuildConfig accepts the review_executor kw-arg and defaults it to None."""
        from goga.config.project.config import BuildConfig, ReviewExecutorConfig

        defaults = BuildConfig(task_executor=TaskExecutorConfig(agent="claude"))
        assert defaults.review_executor is None

        review = ReviewExecutorConfig(skip=True, agent="codex", roles=["quality"])
        configured = BuildConfig(task_executor=TaskExecutorConfig(agent="claude"), review_executor=review)
        assert configured.review_executor is review

    def test_load_project_config_signature_unchanged(self):
        """load_project_config still takes no arguments (signature unchanged)."""
        sig = inspect.signature(load_project_config)
        assert list(sig.parameters.keys()) == []
        assert sig.return_annotation is ProjectConfig


# --- Logic tests for build.review_executor parsing (loader step 6.5) ---


class TestLoadConfigReviewExecutor:
    def test_loader_parses_review_executor_full_section(self, goga_project):
        """build.review_executor with all fields → ReviewExecutorConfig verbatim."""
        from goga.config.project.config import ReviewExecutorConfig

        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
build:
  task_executor:
    agent: claude
  review_executor:
    skip: false
    agent: codex
    roles:
      - quality
      - testing
    env:
      ANTHROPIC_MODEL: reviewer-model
      REVIEW_STRICT: "2"
""",
        )
        config = load_project_config()
        assert config.build.review_executor == ReviewExecutorConfig(
            skip=False,
            agent="codex",
            roles=["quality", "testing"],
            env={"ANTHROPIC_MODEL": "reviewer-model", "REVIEW_STRICT": "2"},
        )

    def test_loader_review_executor_not_mapping_raises(self, goga_project):
        """review_executor: 5 → ValueError mentioning 'must be a mapping'."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
  review_executor: 5
""",
        )
        with pytest.raises(ValueError, match=r"review_executor must be a mapping"):
            load_project_config()

    @pytest.mark.parametrize(
        ("yaml_snippet", "match"),
        [
            ('skip: "yes"', r"review_executor\.skip must be a bool"),
            ("skip: 1", r"review_executor\.skip must be a bool"),
            ("agent: 7", r"review_executor\.agent must be a string"),
            ("roles: quality", r"review_executor\.roles must be a list of strings"),
            ("roles:\n      - 1", r"review_executor\.roles must be a list of strings"),
        ],
        ids=["skip-string", "skip-yaml-int", "agent-int", "roles-string", "roles-int-element"],
    )
    def test_loader_review_executor_field_type_errors(self, goga_project, yaml_snippet, match):
        """Each structurally invalid field value raises ValueError naming the field."""
        _write_goga_yml(
            goga_project,
            f"""\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    {yaml_snippet}
""",
        )
        with pytest.raises(ValueError, match=match):
            load_project_config()

    @pytest.mark.parametrize(
        ("yaml_snippet", "expected"),
        [
            ("", None),
            ("review_executor:\n", None),
            ("review_executor: {}\n", "empty-instance"),
        ],
        ids=["absent", "yaml-null", "empty-mapping"],
    )
    def test_loader_review_executor_absent_and_null(self, goga_project, yaml_snippet, expected):
        """Absent/null section → None; empty mapping → all-fields-None instance."""
        from goga.config.project.config import ReviewExecutorConfig

        section = yaml_snippet
        _write_goga_yml(
            goga_project,
            f"""\
language: python
build:
  task_executor:
    agent: claude
  {section}""",
        )
        config = load_project_config()

        if expected is None:
            assert config.build.review_executor is None
        else:
            assert config.build.review_executor == ReviewExecutorConfig(skip=None, agent=None, roles=None)

    def test_loader_empty_roles_passthrough(self, goga_project):
        """roles: [] → .roles == [] (empty list, NOT normalized to None)."""
        from goga.config.project.config import ReviewExecutorConfig

        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    roles: []
""",
        )
        config = load_project_config()
        assert config.build.review_executor == ReviewExecutorConfig(skip=None, agent=None, roles=[])
        assert config.build.review_executor.roles == []

    def test_loader_parses_review_executor_env_mapping(self, goga_project):
        """review_executor.env str:str mapping → stored verbatim as dict[str, str]."""
        from goga.config.project.config import ReviewExecutorConfig

        _write_goga_yml(
            goga_project,
            """\
language: python
image: qarium/foo:1.0
build:
  task_executor:
    agent: claude
  review_executor:
    skip: false
    agent: codex
    roles:
      - quality
    env:
      ANTHROPIC_MODEL: reviewer-model
      REVIEW_STRICT: "2"
""",
        )
        config = load_project_config()
        assert config.build.review_executor.env == {"ANTHROPIC_MODEL": "reviewer-model", "REVIEW_STRICT": "2"}
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in config.build.review_executor.env.items())
        assert config.build.review_executor == ReviewExecutorConfig(
            skip=False,
            agent="codex",
            roles=["quality"],
            env={"ANTHROPIC_MODEL": "reviewer-model", "REVIEW_STRICT": "2"},
        )

    def test_review_executor_config_declared_fields_include_env(self):
        """Declared fields are skip, agent, roles, env, base_ref, patience; env is
        a factory-defaulted dict[str, str]."""
        from goga.config.project.config import ReviewExecutorConfig

        names = [f.name for f in dataclasses.fields(ReviewExecutorConfig)]
        assert names == ["skip", "agent", "roles", "env", "base_ref", "patience"]
        assert ReviewExecutorConfig.__dataclass_fields__["env"].type == dict[str, str]
        env_field = {f.name: f for f in dataclasses.fields(ReviewExecutorConfig)}["env"]
        assert env_field.default is dataclasses.MISSING
        assert env_field.default_factory is dict
        assert ReviewExecutorConfig(skip=None, agent=None, roles=None).env == {}

    def test_loader_review_executor_env_not_mapping_raises(self, goga_project):
        """review_executor.env: 5 → ValueError mentioning 'must be a mapping'."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    env: 5
""",
        )
        with pytest.raises(ValueError, match=r"review_executor\.env must be a mapping"):
            load_project_config()

    @pytest.mark.parametrize(
        "env_snippet",
        [
            "env:\n      1: x",
            "env:\n      A: 5",
            "env:\n      A: true",
        ],
        ids=["int-key", "int-value", "bool-value"],
    )
    def test_loader_review_executor_env_non_string_key_or_value_raises(self, goga_project, env_snippet):
        """Non-string env keys/values → ValueError 'must have string keys and values'."""
        _write_goga_yml(
            goga_project,
            f"""\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    {env_snippet}
""",
        )
        with pytest.raises(ValueError, match=r"review_executor\.env must have string keys and values"):
            load_project_config()

    @pytest.mark.parametrize(
        ("env_snippet", "env_id"),
        [
            ("", "absent"),
            ("env:\n", "yaml-null"),
            ("env: {}\n", "empty-mapping"),
        ],
    )
    def test_loader_review_executor_env_absent_null_empty_all_empty_dict(self, goga_project, env_snippet, env_id):
        """Absent, YAML-null and empty-mapping env all resolve to {} with no error."""
        _write_goga_yml(
            goga_project,
            f"""\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    skip: null
    {env_snippet}""",
        )
        config = load_project_config()
        assert config.build.review_executor is not None, env_id
        assert config.build.review_executor.env == {}, env_id

    def test_review_executor_base_ref_parsed_verbatim(self, goga_project):
        """review_executor.base_ref string is stored verbatim as a str."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    agent: claude
    base_ref: origin/1.2.x
""",
        )
        config = load_project_config()
        assert config.build.review_executor.base_ref == "origin/1.2.x"
        assert isinstance(config.build.review_executor.base_ref, str)

    def test_review_executor_base_ref_padded_stripped(self, goga_project):
        """review_executor.base_ref with surrounding whitespace is stored stripped.

        Exact equality — an implementation that only nulls the whitespace-only
        case without assigning the stripped value fails.
        """
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    base_ref: "  origin/1.2.x  "
""",
        )
        config = load_project_config()
        assert config.build.review_executor.base_ref == "origin/1.2.x"

    def test_review_executor_patience_int_parsed(self, goga_project):
        """review_executor.patience YAML int is stored verbatim as an int."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    patience: 3
""",
        )
        config = load_project_config()
        assert config.build.review_executor.patience == 3
        assert isinstance(config.build.review_executor.patience, int)

    def test_review_executor_base_ref_non_string_raises(self, goga_project):
        """review_executor.base_ref: 12 → ValueError with the exact contract message."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    base_ref: 12
""",
        )
        with pytest.raises(ValueError, match=r"review_executor\.base_ref must be a string"):
            load_project_config()

    @pytest.mark.parametrize(
        "patience_snippet",
        ['patience: "3"', "patience: 3.5"],
        ids=["quoted-string", "float"],
    )
    def test_review_executor_patience_non_int_raises(self, goga_project, patience_snippet):
        """A non-int patience (str, float) raises ValueError with the exact message."""
        _write_goga_yml(
            goga_project,
            f"""\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    {patience_snippet}
""",
        )
        with pytest.raises(ValueError, match=r"review_executor\.patience must be an int"):
            load_project_config()

    def test_review_executor_patience_yaml_bool_rejected(self, goga_project):
        """patience: true → ValueError — guards the bool-before-int check order."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    patience: true
""",
        )
        with pytest.raises(ValueError, match=r"review_executor\.patience must be an int"):
            load_project_config()

    def test_legacy_build_review_patience_key_not_parsed(self, goga_project):
        """A legacy build.review_patience key is silently ignored — no field, no error."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
  review_patience: 5
""",
        )
        config = load_project_config()
        assert not hasattr(config.build, "review_patience")

    @pytest.mark.parametrize(
        "base_ref_snippet",
        ["", "base_ref: null\n", 'base_ref: ""\n', 'base_ref: "   "\n'],
        ids=["absent", "yaml-null", "empty-string", "whitespace-only"],
    )
    def test_review_executor_base_ref_unset_variants_resolve_none(self, goga_project, base_ref_snippet):
        """Absent, YAML-null, empty and whitespace-only base_ref all resolve to None."""
        _write_goga_yml(
            goga_project,
            f"""\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    agent: claude
    {base_ref_snippet}""",
        )
        config = load_project_config()
        assert config.build.review_executor is not None
        assert config.build.review_executor.base_ref is None

    @pytest.mark.parametrize(
        "patience_snippet",
        ["agent: claude\n", "agent: claude\n    patience: null\n"],
        ids=["absent", "yaml-null"],
    )
    def test_review_executor_patience_unset_variants_resolve_none(self, goga_project, patience_snippet):
        """Absent and YAML-null patience both resolve to None.

        The absent-section variant is pinned by test_loader_review_executor_absent_and_null."""
        _write_goga_yml(
            goga_project,
            f"""\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    {patience_snippet}""",
        )
        config = load_project_config()
        assert config.build.review_executor is not None
        assert config.build.review_executor.patience is None

    @pytest.mark.parametrize(
        ("patience_literal", "patience_id"),
        [("0", "zero"), ("-1", "negative")],
    )
    def test_review_executor_patience_zero_and_negative_verbatim(self, goga_project, patience_literal, patience_id):
        """patience 0 and -1 are stored verbatim — structural typing, no range check."""
        _write_goga_yml(
            goga_project,
            f"""\
language: python
build:
  task_executor:
    agent: claude
  review_executor:
    patience: {patience_literal}
""",
        )
        config = load_project_config()
        assert config.build.review_executor.patience == int(patience_literal), patience_id


# --- Contract + logic tests for TopicsConfig + the topics section (loader step 10) ---


class TestParseTopicsContract:
    def test_parse_topics_exists(self):
        """_parse_topics is importable from goga.config.project.loader."""
        assert callable(_parse_topics)

    def test_parse_topics_signature(self):
        """_parse_topics accepts a single dict parameter (parity with _parse_lint)."""
        sig = inspect.signature(_parse_topics)
        assert list(sig.parameters.keys()) == ["data"]

    def test_parse_topics_return_annotation(self):
        """_parse_topics returns TopicsConfig | None."""
        ret = inspect.signature(_parse_topics).return_annotation
        assert ret == TopicsConfig | None

    def test_parse_topics_field_signature(self):
        """_parse_topics_field takes (value, key) positionally."""
        sig = inspect.signature(_parse_topics_field)
        assert list(sig.parameters.keys()) == ["value", "key"]

    def test_projectconfig_topics_is_last_field(self):
        """topics is the last declared field of ProjectConfig (backward-compatible append)."""
        field_names = [f.name for f in dataclasses.fields(ProjectConfig)]
        assert field_names[-1] == "topics"

    def test_projectconfig_topics_defaults_none(self):
        """topics defaults to None (backward compatible — section absent)."""
        assert {f.name: f for f in dataclasses.fields(ProjectConfig)}["topics"].default is None


class TestParseTopicsLogic:
    def test_parse_topics_without_section_returns_none(self):
        """No topics section → returns None."""
        assert _parse_topics({"language": "python"}) is None

    def test_parse_topics_null_section_returns_none(self):
        """topics: null → returns None."""
        assert _parse_topics({"topics": None}) is None

    def test_parse_topics_empty_mapping_yields_instance(self):
        """topics: {} → TopicsConfig(base_ref=None, publish_commit=None) — an instance, not None."""
        result = _parse_topics({"topics": {}})
        assert isinstance(result, TopicsConfig)
        assert result == TopicsConfig(base_ref=None, publish_commit=None)

    def test_parse_topics_unknown_keys_are_ignored(self):
        """Unknown keys inside the mapping are ignored (cell-wide stance)."""
        result = _parse_topics({"topics": {"base_ref": "origin/main", "future_key": 5}})
        assert result == TopicsConfig(base_ref="origin/main", publish_commit=None)

    @pytest.mark.parametrize("bad_section", ["not-a-mapping", 5, ["a", "b"]])
    def test_parse_topics_rejects_non_mapping_section(self, bad_section):
        """topics section that is not a mapping (str/int/list) → ValueError."""
        with pytest.raises(ValueError, match=r"'topics' must be a mapping"):
            _parse_topics({"topics": bad_section})

    def test_parse_topics_field_null_returns_none(self):
        """A YAML-null field value → None."""
        assert _parse_topics_field(None, "topics.base_ref") is None

    def test_parse_topics_field_strips_to_none(self):
        """An empty or whitespace-only string → None (the loader's empty-to-None rule)."""
        assert _parse_topics_field("", "topics.base_ref") is None
        assert _parse_topics_field("   ", "topics.publish_commit") is None

    def test_parse_topics_field_strips_surrounding_whitespace(self):
        """Surrounding whitespace is stripped; the remainder is stored verbatim."""
        assert _parse_topics_field("  origin/main  ", "topics.base_ref") == "origin/main"

    def test_parse_topics_field_rejects_non_string(self):
        """A present non-string field is a structural type error."""
        with pytest.raises(ValueError, match=r"topics\.base_ref must be a string"):
            _parse_topics_field(5, "topics.base_ref")


class TestLoadConfigTopics:
    def test_topics_section_absent_yields_none(self, goga_project):
        """Config with only language → cfg.topics is None, lang parsed, build None."""
        _write_goga_yml(goga_project, "language: python\n")
        config = load_project_config()
        assert config.topics is None
        assert config.lang == "python"
        assert config.build is None

    def test_topics_section_null_yields_none(self, goga_project):
        """topics: null → cfg.topics is None."""
        _write_goga_yml(goga_project, "language: python\ntopics: null\n")
        config = load_project_config()
        assert config.topics is None

    def test_topics_section_parsed_verbatim(self, goga_project):
        """Both fields stored verbatim — {slug} braces survive, no grammar check."""
        _write_goga_yml(
            goga_project,
            "language: python\ntopics:\n  base_ref: origin/release-1.3\n"
            '  publish_commit: "chore: {slug}"\n',
        )
        config = load_project_config()
        assert config.topics == TopicsConfig(base_ref="origin/release-1.3", publish_commit="chore: {slug}")

    def test_topics_section_not_mapping_raises_value_error(self, goga_project):
        """topics: 5 → ValueError with the exact message (not AttributeError)."""
        _write_goga_yml(goga_project, "language: python\ntopics: 5\n")
        with pytest.raises(ValueError, match=r"^'topics' must be a mapping in \.goga/config\.yml$"):
            load_project_config()

    @pytest.mark.parametrize(
        ("bad_yaml", "message"),
        [
            ("topics:\n  base_ref: 5\n", "topics.base_ref must be a string in .goga/config.yml"),
            ("topics:\n  publish_commit:\n    - 1\n", "topics.publish_commit must be a string in .goga/config.yml"),
        ],
    )
    def test_topics_field_not_string_raises_value_error(self, goga_project, bad_yaml, message):
        """A non-string topics field is a structural type error with the dotted key."""
        _write_goga_yml(goga_project, f"language: python\n{bad_yaml}")
        with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
            load_project_config()

    @pytest.mark.parametrize(
        ("base_ref_yaml", "field_id"),
        [
            ("base_ref: null", "yaml-null"),
            ('base_ref: "  "', "whitespace"),
            ('base_ref: ""', "empty"),
        ],
    )
    def test_topics_base_ref_unset_forms_normalize_to_none(self, goga_project, base_ref_yaml, field_id):
        """base_ref absent/YAML-null/empty/whitespace → None; publish_commit stays verbatim."""
        _write_goga_yml(
            goga_project,
            f"language: python\ntopics:\n  {base_ref_yaml}\n  publish_commit: \"chore: {{slug}}\"\n",
        )
        config = load_project_config()
        assert config.topics is not None
        assert config.topics.base_ref is None, field_id
        assert config.topics.publish_commit == "chore: {slug}"

    def test_topics_section_empty_mapping_yields_topics_config(self, goga_project):
        """topics: {} → an instance with both fields None — "explicit absence" semantics."""
        _write_goga_yml(goga_project, "language: python\ntopics: {}\n")
        config = load_project_config()
        assert config.topics is not None
        assert isinstance(config.topics, TopicsConfig)
        assert config.topics == TopicsConfig(base_ref=None, publish_commit=None)

    def test_topics_section_alongside_other_sections(self, goga_project):
        """topics coexists with the full schema; sibling sections stay intact."""
        _write_goga_yml(
            goga_project,
            "language: python\nimage: qarium/foo:1.0\npipeline:\n  agent: claude\n"
            "build:\n  task_executor:\n    agent: claude\nlint:\n  ignore:\n    - .venv/\n"
            "topics:\n  base_ref: origin/main\n",
        )
        config = load_project_config()
        assert config.topics == TopicsConfig(base_ref="origin/main", publish_commit=None)
        assert config.lint is not None
        assert config.lint.ignore == [".venv/"]
        assert config.pipeline.agent == "claude"
