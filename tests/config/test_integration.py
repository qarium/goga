# tests/goga/config/test_integration.py — integration tests for config loading flow

import dataclasses

import pytest
from goga.config import BuildConfig, CodemanifestConfig, Config, TaskExecutor, load_config

FULL_YAML = """\
language: rust
build:
  task_executor:
    agent: gemini
    env:
      RUST_BACKTRACE: "1"
      CARGO_HOME: /opt/cargo
  image: rust-builder:1.0
  worktree: true
  skip_finalize: false
  session_timeout: "45m"
  idle_timeout: "2h"
  wait: "10m"
  max_iterations: 20
  review_patience: 5
  prompts_dir: "/etc/goga/prompts"
  agents_dir: "/etc/goga/agents"
  codex_review: false
commands:
  build: cargo build --release
  test: cargo test
"""

MINIMAL_YAML = """\
language: python
build:
  task_executor:
    agent: claude
"""

AGENT_PYTHON_YAML = """\
language: python
build:
  task_executor:
    agent: codex
    env:
      PYTHONPATH: /src
  worktree: false
  max_iterations: 15
"""


class TestFullConfigLoadingFlow:
    """End-to-end: YAML file → load_config() → complete Config object graph."""

    def test_full_object_graph_from_yaml(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(FULL_YAML)

        config = load_config()

        # Top-level
        assert isinstance(config, Config)
        assert config.lang == "rust"
        assert config.codemanifest is None
        assert config.commands == {
            "build": "cargo build --release",
            "test": "cargo test",
        }

        # BuildConfig level
        assert isinstance(config.build, BuildConfig)
        assert config.build.image == "rust-builder:1.0"
        assert config.build.worktree is True
        assert config.build.skip_finalize is False
        assert config.build.session_timeout == "45m"
        assert config.build.idle_timeout == "2h"
        assert config.build.wait == "10m"
        assert config.build.max_iterations == 20
        assert config.build.review_patience == 5
        assert config.build.prompts_dir == "/etc/goga/prompts"
        assert config.build.agents_dir == "/etc/goga/agents"
        assert config.build.codex_review is False

        # TaskExecutor level
        assert isinstance(config.build.task_executor, TaskExecutor)
        assert config.build.task_executor.agent == "gemini"
        assert config.build.task_executor.env == {
            "RUST_BACKTRACE": "1",
            "CARGO_HOME": "/opt/cargo",
        }

    def test_minimal_yaml_produces_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(MINIMAL_YAML)

        config = load_config()

        assert config.lang == "python"
        assert config.commands == {}
        assert config.codemanifest is None
        assert config.build.worktree is None
        assert config.build.image is None
        assert config.build.skip_finalize is None
        assert config.build.session_timeout is None
        assert config.build.idle_timeout is None
        assert config.build.wait is None
        assert config.build.max_iterations is None
        assert config.build.review_patience is None
        assert config.build.prompts_dir is None
        assert config.build.agents_dir is None
        assert config.build.codex_review is None
        assert config.build.task_executor.agent == "claude"
        assert config.build.task_executor.env == {}

    def test_partial_build_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(AGENT_PYTHON_YAML)

        config = load_config()

        assert config.lang == "python"
        assert config.build.task_executor.agent == "codex"
        assert config.build.task_executor.env == {"PYTHONPATH": "/src"}
        assert config.codemanifest is None
        assert config.build.worktree is False
        assert config.build.max_iterations == 15
        assert config.build.skip_finalize is None
        assert config.build.session_timeout is None


class TestConfigImmutability:
    """Config, BuildConfig, TaskExecutor are frozen dataclasses — fields cannot be reassigned."""

    def test_task_executor_is_frozen(self):
        te = TaskExecutor(agent="claude")
        with pytest.raises(dataclasses.FrozenInstanceError):  # type: ignore[attr-defined]
            te.agent = "codex"

    def test_build_config_is_frozen(self):
        te = TaskExecutor(agent="claude")
        bc = BuildConfig(task_executor=te, image="goga:latest")
        with pytest.raises(dataclasses.FrozenInstanceError):  # type: ignore[attr-defined]
            bc.worktree = True

    def test_config_is_frozen(self):
        te = TaskExecutor(agent="claude")
        bc = BuildConfig(task_executor=te, image="goga:latest")
        cfg = Config(build=bc, lang="python")
        with pytest.raises(dataclasses.FrozenInstanceError):  # type: ignore[attr-defined]
            cfg.lang = "go"

    def test_codemanifest_config_is_frozen(self):
        cc = CodemanifestConfig(usages={"lib": ".specs/lib.md"})
        with pytest.raises(dataclasses.FrozenInstanceError):  # type: ignore[attr-defined]
            cc.usages = {"x": "y"}

    def test_env_dict_mutation_does_not_raise(self):
        """Frozen only prevents attribute reassignment, not inner-mutable dict mutation."""
        te = TaskExecutor(agent="claude", env={"K": "v"})
        te.env["NEW"] = "val"  # dict content is mutable
        assert te.env == {"K": "v", "NEW": "val"}

    def test_commands_dict_mutation_does_not_raise(self):
        te = TaskExecutor(agent="claude")
        bc = BuildConfig(task_executor=te, image="goga:latest")
        cfg = Config(build=bc, commands={"a": "1"}, lang="python")
        cfg.commands["b"] = "2"  # dict content is mutable
        assert cfg.commands == {"a": "1", "b": "2"}


class TestSequentialLoadConfigCalls:
    """Multiple load_config calls with different .goga/config.yml contents return independent Configs."""

    def test_sequential_calls_produce_independent_configs(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        # First call — minimal config
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(MINIMAL_YAML)
        config1 = load_config()
        assert config1.lang == "python"
        assert config1.build.task_executor.agent == "claude"

        # Second call — different config
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(AGENT_PYTHON_YAML)
        config2 = load_config()
        assert config2.lang == "python"
        assert config2.build.task_executor.agent == "codex"

        # Verify independence: config1 is unaffected
        assert config1.lang == "python"
        assert config1.build.task_executor.agent == "claude"
        assert config2.lang == "python"
        assert config2.build.task_executor.agent == "codex"

    def test_load_after_missing_file_returns_new_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        # First call — valid file
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(MINIMAL_YAML)
        config1 = load_config()
        assert config1.build.task_executor.agent == "claude"

        # Remove file, second call should fail
        (tmp_path / ".goga" / "config.yml").unlink()
        with pytest.raises(FileNotFoundError):
            load_config()
