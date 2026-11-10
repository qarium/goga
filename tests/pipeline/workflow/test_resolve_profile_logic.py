"""Logic tests for the ``resolve_profile`` routine.

Covers behavior beyond the contract surface: the project-wins precedence, the
name-grammar path-traversal guard, the strict malformed-file failure with no
home fall-through, and the missing-everywhere wording naming both locations.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from goga.pipeline.workflow import ProfileSource, resolve_profile


class TestResolveProfileLogic:
    """Logic tests — lookup ordering and strictness of ``resolve_profile``."""

    def test_resolve_profile_project_wins_over_home(self, project_root: Path, home_bundle: dict) -> None:
        """Positive: the same name in both locations resolves from the project file.

        The committed content carries different data than the bundle entry, so
        the winning source is observable in ``data``.
        """
        profiles_dir = project_root / ".goga" / "profiles"
        (profiles_dir / "mixa.yml").write_text("worker:\n  agent: claude\n")

        profile = resolve_profile("mixa", profiles_dir, home_bundle)

        assert profile.name == "mixa"
        assert profile.source is ProfileSource.PROJECT
        assert profile.data == {"worker": {"agent": "claude"}}

    def test_resolve_profile_home_bundle_entry_resolves(self, project_root: Path, home_bundle: dict) -> None:
        """Positive: a name absent from the project resolves from the home bundle."""
        profile = resolve_profile("mixa", project_root / ".goga" / "profiles", home_bundle)

        assert profile.source is ProfileSource.HOME
        assert profile.data is home_bundle["mixa"]

    def test_resolve_profile_rejects_traversal_names(self, project_root: Path) -> None:
        """Negative: grammar violations raise strictly, naming the profile.

        ``../secrets``, ``..``, ``a/b``, and ``.hidden`` all fail the
        ``[A-Za-z0-9][A-Za-z0-9._-]*`` grammar (first char must be
        alphanumeric; no ``/`` in the charset) — the path-traversal guard.
        """
        profiles_dir = project_root / ".goga" / "profiles"

        for bad_name in ("../secrets", "..", "a/b", ".hidden"):
            with pytest.raises(ValueError, match=f"invalid profile name: {re.escape(bad_name)}"):
                resolve_profile(bad_name, profiles_dir, {})

    def test_resolve_profile_empty_name_rejected(self, project_root: Path) -> None:
        """Negative: the empty string fails the grammar."""
        with pytest.raises(ValueError, match="invalid profile name"):
            resolve_profile("", project_root / ".goga" / "profiles", {})

    def test_resolve_profile_grammar_allows_dots_hyphens_underscores(self, project_root: Path) -> None:
        """Positive: a name carrying dots, hyphens, and underscores resolves."""
        profiles_dir = project_root / ".goga" / "profiles"
        (profiles_dir / "Release.2.1-hard.yml").write_text("a: 1\n")

        profile = resolve_profile("Release.2.1-hard", profiles_dir, {})

        assert profile.source is ProfileSource.PROJECT

    def test_resolve_profile_missing_everywhere_names_both_locations(
        self, project_root: Path, home_bundle: dict
    ) -> None:
        """Negative: a name in neither location raises naming it, the project dir, and home."""
        profiles_dir = project_root / ".goga" / "profiles"

        # The message names the profile, the project directory, and the home
        # lookup wording — one regex covers the three fragments in order.
        pattern = rf"ghost.*{re.escape(str(profiles_dir))}.*home"

        with pytest.raises(ValueError, match=pattern):
            resolve_profile("ghost", profiles_dir, home_bundle)

    def test_resolve_profile_malformed_project_file_strict_names_profile_and_path(
        self, project_root: Path, home_bundle: dict
    ) -> None:
        """Negative: a malformed project file raises naming the profile and path — never the bundle.

        Both defect classes — a non-mapping root (``- a``) and invalid YAML
        (``: : :``) — are strict failures; the home bundle carrying the same
        name is never consulted as a fallback.
        """
        profiles_dir = project_root / ".goga" / "profiles"
        (profiles_dir / "mixa.yml").write_text("- a\n")
        (profiles_dir / "zeta.yml").write_text(": : :\n")

        for name, path in (("mixa", "mixa.yml"), ("zeta", "zeta.yml")):
            # Both defect classes name the profile and the offending path.
            pattern = rf"{name}.*{re.escape(str(profiles_dir / path))}"

            with pytest.raises(ValueError, match=pattern):
                resolve_profile(name, profiles_dir, home_bundle)

    def test_resolve_profile_data_carried_verbatim(self, project_root: Path) -> None:
        """The parsed project content arrives as the rendering context, verbatim."""
        profiles_dir = project_root / ".goga" / "profiles"
        content = "worker:\n  agent: codex\n  model: sonnet\nhardening: true\n"
        (profiles_dir / "mixa.yml").write_text(content)

        profile = resolve_profile("mixa", profiles_dir, {})

        assert profile.data == {"worker": {"agent": "codex", "model": "sonnet"}, "hardening": True}

    def test_resolve_profile_non_string_key_is_strict_failure(self, project_root: Path) -> None:
        """Negative: a non-string top-level key is a strict failure naming the
        profile and path — the rendering context is keyword arguments, so a
        non-str key would crash the render with a raw TypeError instead."""
        profiles_dir = project_root / ".goga" / "profiles"
        (profiles_dir / "mixa.yml").write_text("1: value\nworker:\n  agent: codex\n")

        with pytest.raises(ValueError, match=r"profile mixa must have string keys"):
            resolve_profile("mixa", profiles_dir, {})

    def test_resolve_profile_module_reads_no_environment(self) -> None:
        """The module is pure — its source never touches ``os.environ`` or ``getenv``."""
        import inspect

        source = Path(inspect.getsourcefile(resolve_profile)).read_text()  # type: ignore[arg-type]

        assert "os.environ" not in source
        assert "getenv" not in source
