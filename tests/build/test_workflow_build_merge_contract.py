"""Contract-surface lock of ``merge_workflow_build`` — facade and API shape."""

from __future__ import annotations

import inspect

import goga.build


class TestContract:
    """Contract-surface lock: facade accessibility and API shape."""

    def test_importable_from_facade(self) -> None:
        from goga.build import merge_workflow_build

        assert callable(merge_workflow_build)

    def test_in_facade_all(self) -> None:
        assert "merge_workflow_build" in goga.build.__all__

    def test_signature_matches_contract(self) -> None:
        from goga.build import merge_workflow_build

        signature = inspect.signature(merge_workflow_build)

        assert list(signature.parameters) == ["config", "build_block"]

        assert signature.parameters["config"].default is inspect.Parameter.empty
        assert signature.parameters["build_block"].default is inspect.Parameter.empty

    def test_parameter_annotations_match_contract(self) -> None:
        from goga.build import merge_workflow_build

        signature = inspect.signature(merge_workflow_build)

        assert signature.parameters["config"].annotation == "BuildConfig"
        assert signature.parameters["build_block"].annotation == "WorkflowBuild"

    def test_return_annotation_matches_contract(self) -> None:
        from goga.build import merge_workflow_build

        signature = inspect.signature(merge_workflow_build)

        assert signature.return_annotation == "BuildConfig"
