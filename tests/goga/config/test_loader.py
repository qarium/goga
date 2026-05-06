# tests/goga/config/test_loader.py — contract and logic tests for load_config

import dataclasses
import inspect

import goga.config as goga_config_mod
import pytest
import yaml
from goga.config import CodemanifestConfig, Config, load_config
from goga.config.loader import _parse_codemanifest

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
        """.goga.yml with full codemanifest section."""
        _write_goga_yml(
            goga_project,
            """\
language: python
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
        """.goga.yml without codemanifest → codemanifest is None."""
        _write_goga_yml(goga_project, MINIMAL_YAML)
        config = load_config()
        assert config.codemanifest is None

    def test_load_config_codemanifest_empty_section(self, goga_project):
        """codemanifest: {} → defaults."""
        _write_goga_yml(
            goga_project,
            """\
language: python
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


class TestLoadConfigCodemanifestIntegration:
    def test_load_config_full_yaml_with_codemanifest(self, goga_project):
        """FULL_YAML + codemanifest section — verify ALL Config fields."""
        _write_goga_yml(
            goga_project,
            """\
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
codemanifest:
  usages:
    lib: .specs/lib.md
    api: .specs/api.md
  annotations: "Use lib for core logic"
""",
        )
        config = load_config()
        # Verify all non-codemanifest fields match FULL_YAML expectations
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
        # Verify codemanifest fields
        assert config.codemanifest is not None
        assert config.codemanifest.usages == {"lib": ".specs/lib.md", "api": ".specs/api.md"}
        assert config.codemanifest.annotations == "Use lib for core logic"

    def test_load_config_codemanifest_null_returns_none(self, goga_project):
        """codemanifest: null → config.codemanifest is None."""
        _write_goga_yml(
            goga_project,
            """\
language: python
build:
  task_executor:
    agent: claude
codemanifest: null
""",
        )
        config = load_config()
        assert config.codemanifest is None
