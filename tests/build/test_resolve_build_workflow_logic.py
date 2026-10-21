"""Logic tests of ``resolve_build_workflow`` — selection folds and strict failures."""

from __future__ import annotations

from pathlib import Path

import pytest
from goga.build import resolve_build_workflow
from goga.pipeline.workflow import ProfileSource


@pytest.fixture
def seeded_project(project_root: Path) -> Path:
    """Seed the fake project with two workflows and two project profiles.

    ``hard.yml`` carries the literal ``profile: mixa`` default; ``custom.yml``
    is profile-free — the pair distinguishes the CLI/env selection axes from
    the profile activation channels.
    """
    workflows = project_root / ".goga" / "workflows"
    (workflows / "hard.yml").write_text("profile: mixa\nstages:\n  build:\n    agent: claude\n")
    (workflows / "custom.yml").write_text("stages:\n  test:\n    agent: codex\n")

    profiles = project_root / ".goga" / "profiles"
    (profiles / "mixa.yml").write_text("worker:\n  agent: codex\n  model: sonnet\n")
    (profiles / "alt.yml").write_text("worker:\n  agent: gemini\n  model: o4\n")

    return project_root


class TestResolveBuildWorkflow:
    def test_env_fallback_and_empty_strings(self, seeded_project: Path) -> None:
        loaded = resolve_build_workflow(None, "hard")

        assert loaded is not None
        assert sorted(loaded.document.stages) == ["build"]

        cli_wins = resolve_build_workflow("custom", "hard")

        assert cli_wins is not None
        assert sorted(cli_wins.document.stages) == ["test"]

        empty_cli_falls_to_env = resolve_build_workflow("", "hard")

        assert empty_cli_falls_to_env is not None
        assert sorted(empty_cli_falls_to_env.document.stages) == ["build"]

        assert resolve_build_workflow("", "") is None
        assert resolve_build_workflow(None, "") is None
        assert resolve_build_workflow(None, None) is None

    def test_activation_ignored_entirely_without_workflow(self, seeded_project: Path) -> None:
        assert resolve_build_workflow(None, None, "mixa", "mixa", {"mixa": {"worker": {}}}) is None

    def test_escape_raises_invalid_workflow_name(self, seeded_project: Path) -> None:
        with pytest.raises(ValueError, match="invalid workflow name"):
            resolve_build_workflow("../secrets", None)

        with pytest.raises(ValueError, match="invalid workflow name"):
            resolve_build_workflow("/etc/passwd", None)

    def test_missing_file_names_workflow_and_directory(self, seeded_project: Path) -> None:
        with pytest.raises(ValueError, match="nope") as excinfo:
            resolve_build_workflow("nope", None)

        assert ".goga/workflows" in str(excinfo.value)

    def test_profile_channels_flow_into_the_chain(self, seeded_project: Path) -> None:
        default_only = resolve_build_workflow("hard", None)

        assert default_only is not None
        assert default_only.profile is not None
        assert default_only.profile.name == "mixa"
        assert default_only.profile.source is ProfileSource.PROJECT

        cli_channel = resolve_build_workflow("hard", None, cli_profile="alt")

        assert cli_channel is not None
        assert cli_channel.profile is not None
        assert cli_channel.profile.name == "alt"

        env_channel = resolve_build_workflow("hard", None, env_profile="alt")

        assert env_channel is not None
        assert env_channel.profile is not None
        assert env_channel.profile.name == "alt"

        cli_beats_env = resolve_build_workflow("hard", None, "alt", "mixa")

        assert cli_beats_env is not None
        assert cli_beats_env.profile is not None
        assert cli_beats_env.profile.name == "alt"

    def test_home_bundle_serves_home_only_profile(self, seeded_project: Path, home_bundle: dict) -> None:
        loaded = resolve_build_workflow("hard", None, cli_profile="homeonly", home_profiles=home_bundle)

        assert loaded is not None
        assert loaded.profile is not None
        assert loaded.profile.name == "homeonly"
        assert loaded.profile.source is ProfileSource.HOME
