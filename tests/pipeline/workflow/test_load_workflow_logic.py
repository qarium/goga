"""Logic tests for the ``load_workflow`` routine.

Covers behavior beyond the contract surface: the whole chain over real
project trees — the active-profile render, the plain-file identity, the
raw-text default peek (literal, quoted, commented, templated), activation
through every channel, and the strict failure pass-throughs (OSError,
undefined nested access, structural errors).
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from goga.pipeline.workflow import (
    ProfileSource,
    WorkflowSyntaxError,
    load_workflow,
    parse_workflow,
)
from jinja2 import UndefinedError


class TestLoadWorkflowLogic:
    """Logic tests — the chain over real files under the ``project_root`` fixture."""

    def test_load_workflow_renders_with_active_project_profile(self, project_root: Path) -> None:
        """Positive: the env channel activates the project profile; the whole file renders with it.

        The workflow interpolates both an agent value and an env value from
        the profile's ``worker`` mapping — the rendered document carries the
        resolved strings, and the loaded profile reports name and source.
        """
        profiles_dir = project_root / ".goga" / "profiles"
        (profiles_dir / "mixa.yml").write_text("worker:\n  agent: codex\n  model: sonnet\n")

        workflow_path = project_root / ".goga" / "workflows" / "hard.yml"
        workflow_path.write_text(
            "stages:\n  build:\n    agent: '{{ worker.agent }}'\n    env:\n      MODEL: '{{ worker.model }}'\n"
        )

        loaded = load_workflow(workflow_path, None, "mixa", {})

        assert loaded.profile is not None
        assert loaded.profile.name == "mixa"
        assert loaded.profile.source is ProfileSource.PROJECT
        assert loaded.document.stages["build"].agent == "codex"
        assert loaded.document.stages["build"].env == {"MODEL": "sonnet"}

    def test_load_workflow_plain_file_renders_to_itself(self, project_root: Path) -> None:
        """Positive: a template-free file with no activation loads its direct parse."""
        workflow_path = project_root / ".goga" / "workflows" / "plain.yml"
        text = "stages:\n  build:\n    agent: claude\n"
        workflow_path.write_text(text)

        loaded = load_workflow(workflow_path, None, None, None)

        assert loaded.profile is None
        assert loaded.document == parse_workflow(text)

    def test_load_workflow_templated_default_does_not_participate(self, project_root: Path) -> None:
        """Edge: a Jinja-templated ``profile:`` default never activates.

        The peek sees the markers and yields no default, so the render runs
        with an empty context and the body's ``default()`` guard supplies the
        fallback — no activation, no strict error (the design intent, with a
        body that is safe under the standard ``Undefined`` semantics).
        """
        workflow_path = project_root / ".goga" / "workflows" / "guarded.yml"
        workflow_path.write_text(
            "profile: '{{ profile_name }}'\nstages:\n  build:\n    agent: '{{ profile_name | default(\"claude\") }}'\n"
        )

        loaded = load_workflow(workflow_path, None, None, {})

        assert loaded.profile is None
        assert loaded.document.profile is None
        assert loaded.document.stages["build"].agent == "claude"

    def test_load_workflow_nested_missing_key_raises_undefined_error_unwrapped(self, project_root: Path) -> None:
        """Edge: the whole-file render applies even to the default line itself.

        Nested access on a missing key fails at render time (standard Jinja
        semantics per the jinja2 practice) — a templated default whose value
        would crash under an empty context propagates the ``UndefinedError``
        unwrapped; the chain never hides or pre-evaluates it.
        """
        workflow_path = project_root / ".goga" / "workflows" / "nested.yml"
        workflow_path.write_text("profile: '{{ worker.profile }}'\nstages:\n  build:\n    agent: claude\n")

        with pytest.raises(UndefinedError, match="worker"):
            load_workflow(workflow_path, None, None, {})

    def test_load_workflow_oserror_propagates_unchanged(self, project_root: Path) -> None:
        """Edge: a missing workflow-file raises the bare ``FileNotFoundError``.

        The chain adds no existence guard and never wraps the read error —
        the caller owns path guards.
        """
        missing = project_root / ".goga" / "workflows" / "missing.yml"

        with pytest.raises(FileNotFoundError):
            load_workflow(missing)


class TestLoadWorkflowPeekLogic:
    """Logic tests — the raw-text default peek observed through the chain."""

    def test_load_workflow_literal_default_activates_project_profile(self, project_root: Path) -> None:
        """Positive: a plain ``profile:`` line activates without any channel."""
        profiles_dir = project_root / ".goga" / "profiles"
        (profiles_dir / "mixa.yml").write_text("worker:\n  agent: codex\n")

        workflow_path = project_root / ".goga" / "workflows" / "defaulted.yml"
        workflow_path.write_text("profile: mixa\nstages:\n  build:\n    agent: claude\n")

        loaded = load_workflow(workflow_path, None, None, {})

        assert loaded.profile is not None
        assert loaded.profile.source is ProfileSource.PROJECT

    @pytest.mark.parametrize(
        "line",
        [
            'profile: "team-default"\n',
            "profile: 'team-default'\n",
            "profile: team-default  # the committed default\n",
        ],
        ids=["double-quoted", "single-quoted", "trailing-comment"],
    )
    def test_load_workflow_quoted_and_commented_defaults_activate(self, project_root: Path, line: str) -> None:
        """Edge: quotes and trailing comments strip off the peeked default."""
        profiles_dir = project_root / ".goga" / "profiles"
        (profiles_dir / "team-default.yml").write_text("a: 1\n")

        workflow_path = project_root / ".goga" / "workflows" / "dressed.yml"
        workflow_path.write_text(line + "stages:\n  build:\n    agent: claude\n")

        loaded = load_workflow(workflow_path, None, None, {})

        assert loaded.profile is not None
        assert loaded.profile.name == "team-default"

    @pytest.mark.parametrize(
        "line",
        ['profile: ""\n', "profile: '   '\n"],
        ids=["empty-quoted", "whitespace-quoted"],
    )
    def test_load_workflow_blank_defaults_never_activate(self, project_root: Path, line: str) -> None:
        """Edge: empty and whitespace-only quoted values count as unset — no activation.

        The quoted forms parse as strings, so the grammar's empty-rule maps
        them to ``None`` and the file loads cleanly with no active profile.
        """
        workflow_path = project_root / ".goga" / "workflows" / "blank.yml"
        workflow_path.write_text(line + "stages:\n  build:\n    agent: claude\n")

        loaded = load_workflow(workflow_path, None, None, {})

        assert loaded.profile is None
        assert loaded.document.profile is None

    @pytest.mark.parametrize(
        "line",
        [
            'profile: "team # default"\n',
            "profile: 'team # default'\n",
        ],
        ids=["double-quoted-hash", "single-quoted-hash"],
    )
    def test_load_workflow_hash_inside_quotes_keeps_the_name_whole(self, project_root: Path, line: str) -> None:
        """Edge: a ``#`` inside the quoted default value is NOT a comment.
        The grammar rejects the name either way — but the peek hands the
        resolver the WHOLE authored value, so the error names it instead of
        a hash-truncated fragment with a dangling quote."""
        workflow_path = project_root / ".goga" / "workflows" / "hashed.yml"
        workflow_path.write_text(line + "stages:\n  build:\n    agent: claude\n")

        with pytest.raises(ValueError, match=r"invalid profile name: team # default$"):
            load_workflow(workflow_path, None, None, {})

    def test_load_workflow_valueless_profile_line_fails_the_grammar(self, project_root: Path) -> None:
        """Negative: a bare ``profile:`` line is a structural defect, not an activation.

        The peek reads the valueless line as unset (no profile resolves), and
        the rendered text still reaches the standard grammar — YAML parses
        the bare key as null, and the non-str rule fails the file.
        """
        workflow_path = project_root / ".goga" / "workflows" / "bare.yml"
        workflow_path.write_text("profile:\nstages:\n  build:\n    agent: claude\n")

        with pytest.raises(WorkflowSyntaxError, match=r"non-str value in workflow\.profile"):
            load_workflow(workflow_path, None, None, {})

    def test_load_workflow_indented_profile_line_is_not_peeked(self, project_root: Path) -> None:
        """Edge: the peek anchors at column 0 — an indented ``profile:`` line is nested content.

        The ``profile: nested`` line lives inside the top-level prompt block
        scalar; a column-anchored peek skips it, the file parses cleanly, and
        no profile activates.
        """
        workflow_path = project_root / ".goga" / "workflows" / "indented.yml"
        workflow_path.write_text("prompt: |\n  profile: nested\nstages:\n  build:\n    agent: claude\n")

        loaded = load_workflow(workflow_path, None, None, {})

        assert loaded.profile is None
        assert loaded.document.profile is None


class TestLoadWorkflowChannelLogic:
    """Logic tests — activation channels and lookup locations through the chain."""

    def test_load_workflow_cli_beats_env_and_default(self, project_root: Path) -> None:
        """Positive: the CLI channel wins over the env channel and the workflow default."""
        profiles_dir = project_root / ".goga" / "profiles"
        (profiles_dir / "cli.yml").write_text("a: 1\n")
        (profiles_dir / "from-env.yml").write_text("a: 2\n")
        (profiles_dir / "from-default.yml").write_text("a: 3\n")

        workflow_path = project_root / ".goga" / "workflows" / "channels.yml"
        workflow_path.write_text("profile: from-default\nstages:\n  build:\n    agent: claude\n")

        loaded = load_workflow(workflow_path, "cli", "from-env", {})

        assert loaded.profile is not None
        assert loaded.profile.name == "cli"

    def test_load_workflow_env_channel_beats_workflow_default(self, project_root: Path) -> None:
        """Positive: the env channel wins over the workflow's literal default."""
        profiles_dir = project_root / ".goga" / "profiles"
        (profiles_dir / "from-env.yml").write_text("a: 2\n")
        (profiles_dir / "from-default.yml").write_text("a: 3\n")

        workflow_path = project_root / ".goga" / "workflows" / "channels.yml"
        workflow_path.write_text("profile: from-default\nstages:\n  build:\n    agent: claude\n")

        loaded = load_workflow(workflow_path, None, "from-env", {})

        assert loaded.profile is not None
        assert loaded.profile.name == "from-env"

    def test_load_workflow_home_bundle_entry_renders(self, project_root: Path, home_bundle: dict) -> None:
        """Positive: a bundle-only name resolves from the home bundle and drives the render."""
        workflow_path = project_root / ".goga" / "workflows" / "personal.yml"
        workflow_path.write_text("stages:\n  build:\n    agent: '{{ worker.agent }}'\n")

        loaded = load_workflow(workflow_path, "mixa", None, home_bundle)

        assert loaded.profile is not None
        assert loaded.profile.source is ProfileSource.HOME
        assert loaded.document.stages["build"].agent == "codex"

    def test_load_workflow_missing_profile_error_propagates(self, project_root: Path) -> None:
        """Negative: an activated but unresolvable profile fails strictly through the chain."""
        workflow_path = project_root / ".goga" / "workflows" / "ghost.yml"
        workflow_path.write_text("stages:\n  build:\n    agent: claude\n")

        with pytest.raises(ValueError, match="ghost"):
            load_workflow(workflow_path, "ghost", None, {})

    def test_load_workflow_structural_error_propagates(self, project_root: Path) -> None:
        """Negative: a rendered document failing the grammar raises the standard error.

        Rendering never bypasses validation — the unknown top-level key of
        the rendered text surfaces the unchanged structural message.
        """
        workflow_path = project_root / ".goga" / "workflows" / "broken.yml"
        workflow_path.write_text("bogus: 1\nstages:\n  build:\n    agent: claude\n")

        with pytest.raises(WorkflowSyntaxError, match="unknown key in workflow: bogus"):
            load_workflow(workflow_path, None, None, {})


class TestLoadWorkflowPurityLogic:
    """Logic tests — the structural purity constraints of the chain module."""

    def test_load_workflow_module_is_pure(self) -> None:
        """The module reads no environment and adds no existence guard.

        The activation channels arrive as parameters (no ``os.environ`` /
        ``getenv``), and the path guards belong to the caller (no
        ``.exists()`` probe inside the chain).
        """
        from goga.pipeline.workflow import load_workflow as module

        source = inspect.getsource(module)

        assert "os.environ" not in source
        assert "getenv" not in source
        assert ".exists()" not in source
