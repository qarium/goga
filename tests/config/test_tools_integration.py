# tests/goga/config/test_tools_integration.py — end-to-end integration tests for tools extraction

from goga.config import (
    BuildConfig,
    CodemanifestConfig,
    Config,
    PipelineConfig,
    TaskExecutorConfig,
    load_config,
)


def _write_config(path, content: str) -> None:
    """Write a .goga/config.yml file under the given project root."""
    goga_dir = path / ".goga"
    goga_dir.mkdir(exist_ok=True)
    (goga_dir / "config.yml").write_text(content)


# Realistic config exercising every loader section, including tools.
FULL_WITH_TOOLS_YAML = """\
language: go
image: goga:latest
dockerfile: Dockerfile
pipeline:
  agent: codex
  env:
    PIPELINE_OPT: "1"
build:
  task_executor:
    agent: gemini
    env:
      FOO: bar
  worktree: false
  skip_finalize: true
  session_timeout: "30m"
commands:
  test: go test ./...
  build: go build ./...
codemanifest:
  usages:
    lib: .specs/lib.md
  annotations: "Use lib for core logic"
tools:
  afm: 1.0.x
  ralphex: 1.x
  go: 1.0.1
"""

# Same as above but without the tools section.
FULL_WITHOUT_TOOLS_YAML = """\
language: go
image: goga:latest
dockerfile: Dockerfile
pipeline:
  agent: codex
  env:
    PIPELINE_OPT: "1"
build:
  task_executor:
    agent: gemini
    env:
      FOO: bar
  worktree: false
  skip_finalize: true
  session_timeout: "30m"
commands:
  test: go test ./...
  build: go build ./...
codemanifest:
  usages:
    lib: .specs/lib.md
  annotations: "Use lib for core logic"
"""


class TestToolsExtractionIntegration:
    """End-to-end: realistic .goga/config.yml → load_config() → cfg.tools populated."""

    def test_full_config_with_tools_populated(self, tmp_path, monkeypatch):
        """Realistic config with all sections (incl. tools) → cfg.tools parsed verbatim."""
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, FULL_WITH_TOOLS_YAML)

        config = load_config()

        # Sanity: full object graph still intact alongside the new field.
        assert isinstance(config, Config)
        assert config.lang == "go"
        assert config.image == "goga:latest"
        assert config.dockerfile == "Dockerfile"
        assert isinstance(config.pipeline, PipelineConfig)
        assert config.pipeline.agent == "codex"
        assert isinstance(config.build, BuildConfig)
        assert isinstance(config.build.task_executor, TaskExecutorConfig)
        assert config.build.task_executor.agent == "gemini"
        assert config.commands == {"test": "go test ./...", "build": "go build ./..."}
        assert isinstance(config.codemanifest, CodemanifestConfig)
        assert config.codemanifest.annotations == "Use lib for core logic"

        # tools: raw mapping, structural-only — values pass verbatim (no semantic check).
        assert config.tools == {
            "afm": "1.0.x",
            "ralphex": "1.x",
            "go": "1.0.1",
        }
        assert type(config.tools) is dict

    def test_full_config_without_tools_is_none_other_fields_untouched(self, tmp_path, monkeypatch):
        """Config with all sections BUT tools → cfg.tools is None, other fields unchanged."""
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, FULL_WITHOUT_TOOLS_YAML)

        config = load_config()

        # The absent tools key resolves to None (backward-compatible default).
        assert config.tools is None

        # Every other section is parsed exactly as it would be without this feature.
        assert config.lang == "go"
        assert config.image == "goga:latest"
        assert config.dockerfile == "Dockerfile"
        assert config.pipeline.agent == "codex"
        assert config.pipeline.env == {"PIPELINE_OPT": "1"}
        assert config.build.task_executor.agent == "gemini"
        assert config.build.task_executor.env == {"FOO": "bar"}
        assert config.build.worktree is False
        assert config.build.skip_finalize is True
        assert config.build.session_timeout == "30m"
        assert config.commands == {"test": "go test ./...", "build": "go build ./..."}
        assert config.codemanifest is not None
        assert config.codemanifest.usages == {"lib": ".specs/lib.md"}
        assert config.codemanifest.annotations == "Use lib for core logic"

    def test_tools_as_root_level_sibling_preserves_insertion_order(self, tmp_path, monkeypatch):
        """tools: as a root-level sibling → YAML insertion order preserved (dict iteration)."""
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            """\
language: python
image: qarium/foo:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
tools:
  viewer: latest
  afm: 1.0.x
  ralphex: 1.x
  go: 1.0.1
codemanifest:
  annotations: "notes"
""",
        )

        config = load_config()

        # tools sits between build and codemanifest as a root-level sibling.
        assert config.tools is not None
        # YAML mapping insertion order must be preserved end-to-end through safe_load + dict copy.
        assert list(config.tools.keys()) == ["viewer", "afm", "ralphex", "go"]
        assert list(config.tools.items()) == [
            ("viewer", "latest"),
            ("afm", "1.0.x"),
            ("ralphex", "1.x"),
            ("go", "1.0.1"),
        ]

    def test_empty_tools_mapping_yields_empty_dict(self, tmp_path, monkeypatch):
        """tools: {} present but empty → cfg.tools == {} (not None)."""
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
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

        config = load_config()
        assert config.tools == {}
        # Distinguishes "present-but-empty" from "absent" — empty dict is falsy but not None.
        assert config.tools is not None


class TestToolsAlongsideOtherSections:
    """tools coexists with other optional root-level sections without interference."""

    def test_tools_alongside_codemanifest_and_commands(self, tmp_path, monkeypatch):
        """All three optional mapping sections parsed independently and correctly."""
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            """\
language: python
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
commands:
  fmt: black .
codemanifest:
  usages:
    api: .specs/api.md
  annotations: "API layer"
tools:
  afm: 1.0.x
  viewer: latest
""",
        )

        config = load_config()

        assert config.commands == {"fmt": "black ."}
        assert config.codemanifest is not None
        assert config.codemanifest.usages == {"api": ".specs/api.md"}
        assert config.codemanifest.annotations == "API layer"
        assert config.tools == {"afm": "1.0.x", "viewer": "latest"}

    def test_tools_with_only_language_section(self, tmp_path, monkeypatch):
        """tools present even in a near-minimal config → parsed without requiring other sections."""
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            """\
language: python
tools:
  afm: 1.0.x
""",
        )

        config = load_config()
        assert config.lang == "python"
        assert config.image is None
        assert config.pipeline is None
        assert config.build is None
        assert config.commands == {}
        assert config.codemanifest is None
        assert config.tools == {"afm": "1.0.x"}


class TestToolsExtractionRegression:
    """Regressions: adding tools does not alter the parsed shape of sibling sections."""

    def test_tools_field_is_independent_of_other_fields(self, tmp_path, monkeypatch):
        """Adding/removing tools leaves language/image/pipeline/build untouched."""
        monkeypatch.chdir(tmp_path)

        _write_config(tmp_path, FULL_WITHOUT_TOOLS_YAML)
        without = load_config()

        _write_config(tmp_path, FULL_WITH_TOOLS_YAML)
        with_tools = load_config()

        # Shared sections are identical between the two configs.
        assert with_tools.lang == without.lang
        assert with_tools.image == without.image
        assert with_tools.dockerfile == without.dockerfile
        assert with_tools.pipeline == without.pipeline
        assert with_tools.build == without.build
        assert with_tools.commands == without.commands
        assert with_tools.codemanifest == without.codemanifest

        # Only the tools field differs.
        assert without.tools is None
        assert with_tools.tools is not None

    def test_tools_null_treated_as_absent(self, tmp_path, monkeypatch):
        """tools: null → cfg.tools is None (consistent with codemanifest/pipeline null semantics)."""
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            """\
language: python
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
tools: null
""",
        )

        config = load_config()
        assert config.tools is None
