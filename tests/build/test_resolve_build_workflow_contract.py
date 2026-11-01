"""Contract-surface lock of ``resolve_build_workflow`` — facade and API shape."""

from __future__ import annotations

import inspect

import goga.build


class TestContract:
    """Contract-surface lock: facade accessibility and API shape."""

    def test_importable_from_facade(self) -> None:
        from goga.build import resolve_build_workflow

        assert callable(resolve_build_workflow)

    def test_in_facade_all(self) -> None:
        assert "resolve_build_workflow" in goga.build.__all__

    def test_signature_matches_contract(self) -> None:
        from goga.build import resolve_build_workflow

        signature = inspect.signature(resolve_build_workflow)

        assert list(signature.parameters) == [
            "workflow_cli",
            "workflow_env",
            "cli_profile",
            "env_profile",
            "home_profiles",
        ]

        assert signature.parameters["workflow_cli"].default is inspect.Parameter.empty
        assert signature.parameters["workflow_env"].default is inspect.Parameter.empty
        assert signature.parameters["cli_profile"].default is None
        assert signature.parameters["env_profile"].default is None
        assert signature.parameters["home_profiles"].default is None

    def test_parameter_annotations_match_contract(self) -> None:
        from goga.build import resolve_build_workflow

        signature = inspect.signature(resolve_build_workflow)

        assert signature.parameters["workflow_cli"].annotation == "str | None"
        assert signature.parameters["workflow_env"].annotation == "str | None"
        assert signature.parameters["cli_profile"].annotation == "str | None"
        assert signature.parameters["env_profile"].annotation == "str | None"
        assert signature.parameters["home_profiles"].annotation == "dict[str, dict[str, Any]] | None"

    def test_return_annotation_matches_contract(self) -> None:
        from goga.build import resolve_build_workflow

        signature = inspect.signature(resolve_build_workflow)

        assert signature.return_annotation == "LoadedWorkflow | None"
