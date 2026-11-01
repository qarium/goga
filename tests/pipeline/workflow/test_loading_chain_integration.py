"""Cross-entity integration tests of the workflow loading chain.

The cell-local contract/logic pairs verify the chain entities in isolation
(the peek, the activation fold, the profile lookup, the render, the parse).
This module composes them end-to-end through the cell facade the way the
consumers (``goga/pipeline.resolve_workflow``, ``goga/build.resolve_build_workflow``)
will call it, over real project trees:

- the profile-driven whole-file render — ``{{ }}`` interpolation AND the
  ``{% for k, v in worker.env.items() %}`` env-iteration pattern of the jinja2
  practice producing a parseable document (design data flows 2+3);
- activation through every channel — CLI, env, and the workflow literal
  default each activate the same profile; quoted/commented defaults activate;
  the channels beat the default;
- the template-free identity invariant — ``LoadedWorkflow.document`` equals
  the direct ``parse_workflow(text)`` of the same file, pinning that the chain
  changes nothing when no profile is active.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from goga.pipeline.workflow import (
    ProfileSource,
    load_home_profiles,
    load_workflow,
    parse_workflow,
)

# The profile content of the render scenario — a nested ``worker`` mapping
# whose ``env`` sub-mapping feeds the iteration pattern. The values are
# quoted in the profile so the template's ``"{{ v }}"`` quoting round-trips
# them as strings through the YAML re-parse.
_RENDER_PROFILE = 'worker:\n  agent: codex\n  model: sonnet\n  env:\n    A: "1"\n    B: "2"\n'

# The workflow of the render scenario — the agent interpolates directly while
# the env map materializes through the practice's mapping-iteration pattern
# (trim_blocks + lstrip_blocks keep the block tags from breaking the YAML).
_RENDER_WORKFLOW = (
    "profile: mixa\n"
    "stages:\n"
    "  build:\n"
    "    agent: '{{ worker.agent }}'\n"
    "    env:\n"
    "      {% for k, v in worker.env.items() %}\n"
    '      {{ k }}: "{{ v }}"\n'
    "      {% endfor %}\n"
)


class TestLoadingChainRenderIntegration:
    """Integration — the profile-driven whole-file render through the facade."""

    def test_profile_driven_whole_file_render_builds_stage_and_env(self, project_root: Path) -> None:
        """The active project profile renders both the interpolation and the env iteration.

        The workflow interpolates the stage agent with ``{{ worker.agent }}``
        and produces the whole env map with the ``{% for k, v in
        worker.env.items() %}`` pattern; loading through the facade returns a
        document whose stage agent and env map carry the rendered values, and
        the loaded profile reports the project source (design data flows 2+3).
        """
        (project_root / ".goga" / "profiles" / "mixa.yml").write_text(_RENDER_PROFILE)

        workflow_path = project_root / ".goga" / "workflows" / "hard.yml"
        workflow_path.write_text(_RENDER_WORKFLOW)

        loaded = load_workflow(workflow_path, None, "mixa", {})

        assert loaded.profile is not None
        assert loaded.profile.name == "mixa"
        assert loaded.profile.source is ProfileSource.PROJECT
        assert loaded.document.stages["build"].agent == "codex"
        assert loaded.document.stages["build"].env == {"A": "1", "B": "2"}


class TestLoadingChainActivationIntegration:
    """Integration — every activation channel drives the same chain."""

    @pytest.mark.parametrize(
        ("cli_profile", "env_profile"),
        [("mixa", None), (None, "mixa"), (None, None)],
        ids=["cli-channel", "env-channel", "workflow-default"],
    )
    def test_every_channel_activates_the_same_profile(
        self, project_root: Path, cli_profile: str | None, env_profile: str | None
    ) -> None:
        """The CLI channel, the env channel, and the workflow default activate the same profile.

        The workflow carries the literal ``profile: mixa`` default and the
        project holds the profile file; each activation route resolves the
        same profile and renders the same document with it.
        """
        (project_root / ".goga" / "profiles" / "mixa.yml").write_text(_RENDER_PROFILE)

        workflow_path = project_root / ".goga" / "workflows" / "hard.yml"
        workflow_path.write_text(_RENDER_WORKFLOW)

        loaded = load_workflow(workflow_path, cli_profile, env_profile, {})

        assert loaded.profile is not None
        assert loaded.profile.name == "mixa"
        assert loaded.profile.source is ProfileSource.PROJECT
        assert loaded.document.stages["build"].agent == "codex"
        assert loaded.document.stages["build"].env == {"A": "1", "B": "2"}

    @pytest.mark.parametrize(
        "line",
        ['profile: "mixa"\n', "profile: 'mixa'\n", "profile: mixa  # the committed default\n"],
        ids=["double-quoted", "single-quoted", "trailing-comment"],
    )
    def test_quoted_and_commented_defaults_activate(self, project_root: Path, line: str) -> None:
        """A quoted or trailing-commented ``profile:`` default activates like a bare one.

        The peek strips the quotes and the comment, so each dressed form
        resolves the same profile without any channel input.
        """
        profiles_dir = project_root / ".goga" / "profiles"
        profiles_dir.joinpath("mixa.yml").write_text(_RENDER_PROFILE)

        workflow_path = project_root / ".goga" / "workflows" / "dressed.yml"
        workflow_path.write_text(line + "stages:\n  build:\n    agent: '{{ worker.agent }}'\n")

        loaded = load_workflow(workflow_path, None, None, {})

        assert loaded.profile is not None
        assert loaded.profile.name == "mixa"
        assert loaded.document.stages["build"].agent == "codex"

    def test_channels_beat_the_workflow_default(self, project_root: Path) -> None:
        """Both channels outrank the workflow's literal default.

        With the default pointing at ``mixa`` and both channels pointing at
        ``override``, each channel run activates ``override`` and renders with
        its data instead — precedence, not mere presence, is exercised.
        """
        profiles_dir = project_root / ".goga" / "profiles"
        profiles_dir.joinpath("mixa.yml").write_text(_RENDER_PROFILE)
        profiles_dir.joinpath("override.yml").write_text('worker:\n  agent: gemini\n  env:\n    A: "9"\n')

        workflow_path = project_root / ".goga" / "workflows" / "hard.yml"
        workflow_path.write_text(_RENDER_WORKFLOW)

        from_cli = load_workflow(workflow_path, "override", None, {})
        from_env = load_workflow(workflow_path, None, "override", {})

        assert from_cli.profile is not None
        assert from_cli.profile.name == "override"
        assert from_cli.document.stages["build"].agent == "gemini"
        assert from_env.profile is not None
        assert from_env.profile.name == "override"
        assert from_env.document.stages["build"].agent == "gemini"

    def test_home_bundle_entry_activates_without_project_profile(
        self, project_root: Path, tmp_path: Path, home_bundle: dict
    ) -> None:
        """A bundle-only name flows from ``load_home_profiles`` into the render.

        The home tree carries the profile while the project does not; the
        collected bundle handed to the chain resolves the HOME source and the
        document renders with the bundle data (the host half of data flow 1).
        """
        home_dir = tmp_path / "home" / ".goga" / "profiles"
        home_dir.mkdir(parents=True)
        (home_dir / "mixa.yml").write_text("worker:\n  agent: codex\n  model: sonnet\n")

        bundle = load_home_profiles(home_dir)
        assert bundle == home_bundle

        workflow_path = project_root / ".goga" / "workflows" / "personal.yml"
        workflow_path.write_text("stages:\n  build:\n    agent: '{{ worker.agent }}'\n")

        loaded = load_workflow(workflow_path, "mixa", None, bundle)

        assert loaded.profile is not None
        assert loaded.profile.source is ProfileSource.HOME
        assert loaded.document.stages["build"].agent == "codex"


class TestLoadingChainIdentityIntegration:
    """Integration — the template-free identity invariant across the whole chain."""

    def test_template_free_file_equals_pre_feature_parse(self, project_root: Path) -> None:
        """A template-free file loads to exactly the direct ``parse_workflow`` result.

        With no profile activation the chain renders with an empty context —
        a template-free text renders to itself — so the loaded document equals
        the pre-feature direct parse of the same text byte-for-byte semantics.
        """
        text = (
            "prompt: ship it\n"
            "stages:\n"
            "  build:\n"
            "    agent: claude\n"
            "    env:\n"
            "      K: v\n"
            "extend:\n"
            "  extra:\n"
            "    after: [build]\n"
        )
        workflow_path = project_root / ".goga" / "workflows" / "plain.yml"
        workflow_path.write_text(text)

        loaded = load_workflow(workflow_path, None, None, {})

        assert loaded.profile is None
        assert loaded.document == parse_workflow(text)
