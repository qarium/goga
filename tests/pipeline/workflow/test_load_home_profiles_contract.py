"""Contract tests for the ``load_home_profiles`` routine.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the
single-parameter signature (``home_dir`` — no default), and the
``dict[str, dict[str, Any]]`` return contract. These tests pin the contract
surface — behavior lives in the logic test module.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, get_type_hints

from goga.pipeline.workflow import load_home_profiles


class TestLoadHomeProfilesContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_load_home_profiles_importable_from_facade(self) -> None:
        """load_home_profiles is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.load_home_profiles is load_home_profiles
        assert "load_home_profiles" in facade.__all__

    def test_load_home_profiles_signature_declares_single_directory_parameter(self) -> None:
        """The signature declares exactly home_dir — no default."""
        parameters = inspect.signature(load_home_profiles).parameters

        assert list(parameters) == ["home_dir"]
        assert all(parameter.default is inspect.Parameter.empty for parameter in parameters.values())

    def test_load_home_profiles_return_annotation_is_nested_mapping(self) -> None:
        """The return annotation is the name → content bundle mapping."""
        hints = get_type_hints(load_home_profiles)

        assert hints["return"] == dict[str, dict[str, Any]]

    def test_load_home_profiles_returns_bundle_for_flat_directory(self, tmp_path: Path) -> None:
        """load_home_profiles returns the name → content mapping of the flat *.yml files."""
        (tmp_path / "mixa.yml").write_text("worker:\n  agent: codex\n")

        bundle = load_home_profiles(tmp_path)

        assert bundle == {"mixa": {"worker": {"agent": "codex"}}}
