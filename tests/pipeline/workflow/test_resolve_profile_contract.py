"""Contract tests for the ``resolve_profile`` routine.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the
three-parameter signature (``name``, ``project_dir``, ``home_profiles`` — no
defaults), and the ``ResolvedProfile`` return contract. These tests pin the
contract surface — behavior lives in the logic test module.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_type_hints

from goga.pipeline.workflow import ResolvedProfile, resolve_profile


class TestResolveProfileContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_resolve_profile_importable_from_facade(self) -> None:
        """resolve_profile is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.resolve_profile is resolve_profile
        assert "resolve_profile" in facade.__all__

    def test_resolve_profile_signature_declares_three_parameters(self) -> None:
        """The signature declares exactly name, project_dir, home_profiles — no defaults."""
        parameters = inspect.signature(resolve_profile).parameters

        assert list(parameters) == ["name", "project_dir", "home_profiles"]
        assert all(parameter.default is inspect.Parameter.empty for parameter in parameters.values())

    def test_resolve_profile_return_annotation_is_resolved_profile(self) -> None:
        """The return annotation is ``ResolvedProfile``."""
        hints = get_type_hints(resolve_profile)

        assert hints["return"] is ResolvedProfile

    def test_resolve_profile_returns_resolved_profile_for_project_file(self, tmp_path: Path) -> None:
        """resolve_profile returns a ResolvedProfile built from the project profile file."""
        (tmp_path / "mixa.yml").write_text("worker:\n  agent: codex\n")

        profile = resolve_profile("mixa", tmp_path, {})

        assert isinstance(profile, ResolvedProfile)
