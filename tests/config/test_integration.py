# tests/goga/config/test_integration.py — integration tests for config loading flow

import dataclasses

import pytest
from goga.config import (
    AdditionalReviewConfig,
    BuildConfig,
    CodemanifestConfig,
    PipelineConfig,
    ProjectConfig,
    ReviewConfig,
    load_project_config,
)

FULL_YAML = """\
language: rust
image: rust-builder:1.0
pipeline:
  agent: claude
build:
  agent: gemini
  env:
    RUST_BACKTRACE: "1"
    CARGO_HOME: /opt/cargo
  session_timeout: "45m"
  idle_timeout: "2h"
  wait: "10m"
  max_iterations: 20
  prompts_dir: "/etc/goga/prompts"
  agents_dir: "/etc/goga/agents"
  review:
    skip: false
    agent: codex
    env:
      REVIEW_STRICT: "2"
    roles:
      - quality
    base_ref: origin/1.2.x
    strategy: full
    finalize: "Final review pass."
    session_timeout: "50m"
    additional:
      agent: cursor
      patience: 5
      max_iterations: 12
commands:
  build: cargo build --release
  test: cargo test
"""

MINIMAL_YAML = """\
language: python
pipeline:
  agent: claude
build:
  agent: claude
"""

AGENT_PYTHON_YAML = """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: codex
build:
  agent: codex
  env:
    PYTHONPATH: /src
  max_iterations: 15
"""

# Retired keys still present in a migrated-late config — silently ignored.
RETIRED_KEYS_YAML = """\
language: python
pipeline:
  agent: claude
build:
  worktree: true
  skip_finalize: false
  codex_review: true
  task_executor:
    agent: gemini
    env:
      FOO: bar
  review_executor:
    agent: codex
    base_ref: origin/1.2.x
  agent: claude
"""


class TestFullConfigLoadingFlow:
    """End-to-end: YAML file → load_project_config() → complete ProjectConfig object graph."""

    def test_full_object_graph_from_yaml(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(FULL_YAML)

        config = load_project_config()

        # Top-level
        assert isinstance(config, ProjectConfig)
        assert config.language == "rust"
        assert config.image == "rust-builder:1.0"
        assert config.codemanifest is None
        assert config.commands == {
            "build": "cargo build --release",
            "test": "cargo test",
        }

        # BuildConfig level (two-part root)
        assert isinstance(config.build, BuildConfig)
        assert not hasattr(config.build, "image")
        assert not hasattr(config.build, "worktree")
        assert not hasattr(config.build, "task_executor")
        assert config.build.agent == "gemini"
        assert config.build.env == {
            "RUST_BACKTRACE": "1",
            "CARGO_HOME": "/opt/cargo",
        }
        assert config.build.session_timeout == "45m"
        assert config.build.idle_timeout == "2h"
        assert config.build.wait == "10m"
        assert config.build.max_iterations == 20
        assert config.build.prompts_dir == "/etc/goga/prompts"
        assert config.build.agents_dir == "/etc/goga/agents"

        # ReviewConfig level (the review part)
        assert isinstance(config.build.review, ReviewConfig)
        assert config.build.review.skip is False
        assert config.build.review.agent == "codex"
        assert config.build.review.env == {"REVIEW_STRICT": "2"}
        assert config.build.review.roles == ["quality"]
        assert config.build.review.base_ref == "origin/1.2.x"
        assert config.build.review.strategy == "full"
        assert config.build.review.finalize == "Final review pass."
        assert config.build.review.session_timeout == "50m"
        assert config.build.review.additional == AdditionalReviewConfig(
            agent="cursor",
            patience=5,
            max_iterations=12,
        )

        # PipelineConfig level
        assert isinstance(config.pipeline, PipelineConfig)
        assert config.pipeline.agent == "claude"
        assert config.pipeline.env == {}

    def test_minimal_yaml_produces_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(MINIMAL_YAML)

        config = load_project_config()

        assert config.language == "python"
        assert config.image is None
        assert config.commands == {}
        assert config.codemanifest is None
        assert config.build.agent == "claude"
        assert config.build.env == {}
        assert not hasattr(config.build, "image")
        assert config.build.max_iterations is None
        assert config.build.session_timeout is None
        assert config.build.idle_timeout is None
        assert config.build.wait is None
        assert config.build.prompts_dir is None
        assert config.build.agents_dir is None
        assert config.build.review is None
        assert config.pipeline.agent == "claude"
        assert config.pipeline.env == {}

    def test_partial_build_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(AGENT_PYTHON_YAML)

        config = load_project_config()

        assert config.language == "python"
        assert config.image == "qarium/foo:1.0"
        assert config.build.agent == "codex"
        assert config.build.env == {"PYTHONPATH": "/src"}
        assert config.codemanifest is None
        assert config.build.max_iterations == 15
        assert config.build.session_timeout is None
        assert config.pipeline.agent == "codex"

    def test_retired_keys_silently_ignored(self, tmp_path, monkeypatch):
        """A config still carrying the retired keys loads without error; they are not extracted.

        The retired-key silence semantics are covered in detail by the loader
        tests (test_load_project_config_ignores_retired_keys); this pins the
        same behavior at the full-flow level.
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(RETIRED_KEYS_YAML)

        config = load_project_config()

        assert config.build.agent == "claude"
        assert config.build.env == {}
        assert config.build.review is None
        assert not hasattr(config.build, "task_executor")
        assert not hasattr(config.build, "review_executor")
        assert not hasattr(config.build, "worktree")
        assert not hasattr(config.build, "skip_finalize")
        assert not hasattr(config.build, "codex_review")


class TestConfigImmutability:
    """ProjectConfig, BuildConfig, ReviewConfig are frozen dataclasses — fields cannot be reassigned."""

    def test_pipeline_is_frozen(self):
        pc = PipelineConfig(agent="claude")
        with pytest.raises(dataclasses.FrozenInstanceError):  # type: ignore[attr-defined]
            pc.agent = "codex"

    def test_build_config_is_frozen(self):
        bc = BuildConfig(agent="claude")
        with pytest.raises(dataclasses.FrozenInstanceError):  # type: ignore[attr-defined]
            bc.agent = "codex"

    def test_review_config_is_frozen(self):
        review = ReviewConfig(agent="claude")
        with pytest.raises(dataclasses.FrozenInstanceError):  # type: ignore[attr-defined]
            review.agent = "codex"

    def test_additional_review_config_is_frozen(self):
        additional = AdditionalReviewConfig(agent="claude")
        with pytest.raises(dataclasses.FrozenInstanceError):  # type: ignore[attr-defined]
            additional.agent = "codex"

    def test_config_is_frozen(self):
        bc = BuildConfig(agent="claude")
        pc = PipelineConfig(agent="claude")
        cfg = ProjectConfig(image=None, dockerfile=None, build=bc, pipeline=pc, language="python")
        with pytest.raises(dataclasses.FrozenInstanceError):  # type: ignore[attr-defined]
            cfg.language = "go"

    def test_codemanifest_config_is_frozen(self):
        cc = CodemanifestConfig(usages={"lib": ".specs/lib.md"})
        with pytest.raises(dataclasses.FrozenInstanceError):  # type: ignore[attr-defined]
            cc.usages = {"x": "y"}

    def test_env_dict_mutation_does_not_raise(self):
        """Frozen only prevents attribute reassignment, not inner-mutable dict mutation."""
        bc = BuildConfig(agent="claude", env={"K": "v"})
        bc.env["NEW"] = "val"  # dict content is mutable
        assert bc.env == {"K": "v", "NEW": "val"}

    def test_commands_dict_mutation_does_not_raise(self):
        bc = BuildConfig(agent="claude")
        pc = PipelineConfig(agent="claude")
        cfg = ProjectConfig(image=None, dockerfile=None, build=bc, pipeline=pc, commands={"a": "1"}, language="python")
        cfg.commands["b"] = "2"  # dict content is mutable
        assert cfg.commands == {"a": "1", "b": "2"}


class TestSequentialLoadConfigCalls:
    """Multiple load_project_config calls with different .goga/config.yml contents return independent Configs."""

    def test_sequential_calls_produce_independent_configs(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        # First call — minimal config
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(MINIMAL_YAML)
        config1 = load_project_config()
        assert config1.language == "python"
        assert config1.build.agent == "claude"

        # Second call — different config
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(AGENT_PYTHON_YAML)
        config2 = load_project_config()
        assert config2.language == "python"
        assert config2.build.agent == "codex"

        # Verify independence: config1 is unaffected
        assert config1.language == "python"
        assert config1.build.agent == "claude"
        assert config2.language == "python"
        assert config2.build.agent == "codex"

    def test_load_after_missing_file_returns_new_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        # First call — valid file
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(MINIMAL_YAML)
        config1 = load_project_config()
        assert config1.build.agent == "claude"

        # Remove file, second call should fail
        (tmp_path / ".goga" / "config.yml").unlink()
        with pytest.raises(FileNotFoundError):
            load_project_config()
